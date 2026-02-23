"""JWT authentication and RBAC for the PipelineAtlas API.

Provides:
- JWT token generation and validation
- API key support for CI integrations
- Role-based access control (admin, auditor, viewer)
- FastAPI dependency for protecting routes
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from base64 import urlsafe_b64decode, urlsafe_b64encode
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Default secret — MUST be overridden in production via env var
_JWT_SECRET = "atlas-dev-secret-change-in-production"
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRY_SECONDS = 3600  # 1 hour


class User(BaseModel):
    """An authenticated user with a role."""

    id: str
    username: str
    role: str = "viewer"  # admin, auditor, viewer
    email: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_auditor(self) -> bool:
        return self.role in ("admin", "auditor")

    def can_read(self) -> bool:
        return True  # all roles can read

    def can_write(self) -> bool:
        return self.role in ("admin", "auditor")

    def can_manage(self) -> bool:
        return self.role == "admin"


class AuthError(Exception):
    """Authentication or authorization failure."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        self.message = message
        self.status_code = status_code


# ── JWT helpers (pure Python, no external deps) ─────────────────────

def _b64_encode(data: bytes) -> str:
    return urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(data: str) -> bytes:
    padding = 4 - len(data) % 4
    return urlsafe_b64decode(data + "=" * padding)


def _hmac_sign(payload: str, secret: str) -> str:
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return _b64_encode(sig)


def create_token(user: User, secret: str = _JWT_SECRET, expiry: int = _JWT_EXPIRY_SECONDS) -> str:
    """Create a JWT token for a user."""
    header = _b64_encode(json.dumps({"alg": _JWT_ALGORITHM, "typ": "JWT"}).encode())
    payload_data = {
        "sub": user.id,
        "username": user.username,
        "role": user.role,
        "exp": int(time.time()) + expiry,
        "iat": int(time.time()),
    }
    payload = _b64_encode(json.dumps(payload_data).encode())
    signature = _hmac_sign(f"{header}.{payload}", secret)
    return f"{header}.{payload}.{signature}"


def verify_token(token: str, secret: str = _JWT_SECRET) -> User:
    """Verify a JWT token and return the User."""
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("Invalid token format")

    header_b64, payload_b64, signature = parts

    # Verify signature
    expected_sig = _hmac_sign(f"{header_b64}.{payload_b64}", secret)
    if not hmac.compare_digest(signature, expected_sig):
        raise AuthError("Invalid token signature")

    # Decode payload
    try:
        payload = json.loads(_b64_decode(payload_b64))
    except (json.JSONDecodeError, Exception) as e:
        raise AuthError(f"Invalid token payload: {e}")

    # Check expiry
    if payload.get("exp", 0) < time.time():
        raise AuthError("Token expired")

    return User(
        id=payload["sub"],
        username=payload["username"],
        role=payload.get("role", "viewer"),
    )


# ── API Key support ─────────────────────────────────────────────────

# In-memory API key store (PostgreSQL in production)
_api_keys: dict[str, User] = {}


def register_api_key(key: str, user: User) -> None:
    """Register an API key for CI integration."""
    _api_keys[key] = user


def verify_api_key(key: str) -> User:
    """Verify an API key and return the associated User."""
    if key not in _api_keys:
        raise AuthError("Invalid API key")
    return _api_keys[key]


# ── FastAPI auth dependency ─────────────────────────────────────────

def get_current_user(authorization: str) -> User:
    """Extract and verify user from Authorization header.

    Supports:
        Authorization: Bearer <jwt_token>
        Authorization: ApiKey <api_key>
    """
    if not authorization:
        raise AuthError("Missing authorization header")

    parts = authorization.split(" ", 1)
    if len(parts) != 2:
        raise AuthError("Invalid authorization format")

    scheme, credential = parts

    if scheme.lower() == "bearer":
        return verify_token(credential)
    elif scheme.lower() == "apikey":
        return verify_api_key(credential)
    else:
        raise AuthError(f"Unsupported auth scheme: {scheme}")


def require_role(user: User, required_role: str) -> None:
    """Check if user has the required role."""
    role_levels = {"viewer": 0, "auditor": 1, "admin": 2}
    user_level = role_levels.get(user.role, 0)
    required_level = role_levels.get(required_role, 0)

    if user_level < required_level:
        raise AuthError(
            f"Insufficient permissions: {user.role} cannot perform {required_role} actions",
            status_code=403,
        )
