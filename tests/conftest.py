"""Shared test configuration for atlas-api tests.

Sets ATLAS_API_ENVIRONMENT=development before any module imports so that
the JWT auth module uses the dev fallback secret instead of requiring the
production env var.
"""

import os

# Must be set before atlas_api.auth is imported to enable the dev secret fallback.
os.environ.setdefault("ATLAS_API_ENVIRONMENT", "development")
# Disable rate limiting so tests can call endpoints freely.
os.environ.setdefault("ATLAS_API_RATE_LIMIT_ENABLED", "false")

import pytest


@pytest.fixture(autouse=True)
def reset_jwt_cache():
    """Clear the cached JWT secret between tests to avoid cross-test contamination."""
    import atlas_api.auth as _auth
    _auth._JWT_SECRET_CACHE = ""
    yield
    _auth._JWT_SECRET_CACHE = ""


def make_admin_token() -> str:
    """Create an admin Bearer token using the dev secret."""
    from atlas_api.auth import User, create_token
    user = User(id="test-admin", username="test-admin", role="admin")
    return create_token(user)


def admin_headers() -> dict:
    """Return Authorization headers for an admin user."""
    return {"authorization": f"Bearer {make_admin_token()}"}
