"""Tests for JWT authentication and RBAC."""

import time
import pytest

from atlas_api.auth import (
    User, AuthError,
    create_token, verify_token,
    register_api_key, verify_api_key, _api_keys,
    get_current_user, require_role,
)


@pytest.fixture(autouse=True)
def clear_api_keys():
    _api_keys.clear()
    yield
    _api_keys.clear()


class TestJWT:

    def test_create_and_verify_token(self):
        user = User(id="u1", username="yoad", role="admin")
        token = create_token(user)
        result = verify_token(token)

        assert result.id == "u1"
        assert result.username == "yoad"
        assert result.role == "admin"

    def test_invalid_signature_rejected(self):
        user = User(id="u1", username="yoad", role="viewer")
        token = create_token(user)
        # Tamper with the token
        parts = token.split(".")
        parts[2] = "invalid-signature"
        tampered = ".".join(parts)

        with pytest.raises(AuthError, match="Invalid token signature"):
            verify_token(tampered)

    def test_expired_token_rejected(self):
        user = User(id="u1", username="yoad", role="viewer")
        token = create_token(user, expiry=-10)  # already expired

        with pytest.raises(AuthError, match="Token expired"):
            verify_token(token)

    def test_invalid_format_rejected(self):
        with pytest.raises(AuthError, match="Invalid token format"):
            verify_token("not.a.valid.token.with.too.many.parts")


class TestAPIKey:

    def test_register_and_verify_api_key(self):
        user = User(id="ci1", username="ci-bot", role="auditor")
        register_api_key("atlas-key-123", user)
        result = verify_api_key("atlas-key-123")
        assert result.username == "ci-bot"

    def test_invalid_api_key_rejected(self):
        with pytest.raises(AuthError, match="Invalid API key"):
            verify_api_key("nonexistent-key")


class TestRBAC:

    def test_viewer_can_read(self):
        user = User(id="u1", username="viewer", role="viewer")
        assert user.can_read() is True
        assert user.can_write() is False
        assert user.can_manage() is False

    def test_auditor_can_write(self):
        user = User(id="u2", username="auditor", role="auditor")
        assert user.can_read() is True
        assert user.can_write() is True
        assert user.can_manage() is False

    def test_admin_can_manage(self):
        user = User(id="u3", username="admin", role="admin")
        assert user.can_read() is True
        assert user.can_write() is True
        assert user.can_manage() is True

    def test_require_role_passes(self):
        admin = User(id="u3", username="admin", role="admin")
        require_role(admin, "auditor")  # should not raise

    def test_require_role_fails(self):
        viewer = User(id="u1", username="viewer", role="viewer")
        with pytest.raises(AuthError, match="Insufficient permissions"):
            require_role(viewer, "admin")


class TestGetCurrentUser:

    def test_bearer_auth(self):
        user = User(id="u1", username="yoad", role="admin")
        token = create_token(user)
        result = get_current_user(f"Bearer {token}")
        assert result.username == "yoad"

    def test_apikey_auth(self):
        user = User(id="ci1", username="ci-bot", role="auditor")
        register_api_key("test-key", user)
        result = get_current_user("ApiKey test-key")
        assert result.username == "ci-bot"

    def test_missing_header(self):
        with pytest.raises(AuthError, match="Missing authorization"):
            get_current_user("")
