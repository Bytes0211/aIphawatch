"""Tests for auth module."""

import pytest

from alphawatch.api.auth import AuthError, extract_bearer_token


class TestExtractBearerToken:
    """Test bearer token extraction from Authorization header."""

    def test_valid_bearer_token(self):
        token = extract_bearer_token("Bearer abc123")
        assert token == "abc123"

    def test_bearer_case_insensitive(self):
        token = extract_bearer_token("bearer abc123")
        assert token == "abc123"

    def test_missing_header_raises(self):
        with pytest.raises(AuthError, match="Missing Authorization header"):
            extract_bearer_token(None)

    def test_empty_header_raises(self):
        with pytest.raises(AuthError, match="Missing Authorization header"):
            extract_bearer_token("")

    def test_no_bearer_prefix_raises(self):
        with pytest.raises(AuthError, match="Bearer"):
            extract_bearer_token("Basic abc123")

    def test_missing_token_value_raises(self):
        with pytest.raises(AuthError, match="Bearer"):
            extract_bearer_token("Bearer")

    def test_too_many_parts_raises(self):
        with pytest.raises(AuthError, match="Bearer"):
            extract_bearer_token("Bearer abc 123")


class TestAuthError:
    """Test AuthError exception."""

    def test_default_status_code(self):
        err = AuthError("test")
        assert err.status_code == 401
        assert err.detail == "test"

    def test_custom_status_code(self):
        err = AuthError("forbidden", status_code=403)
        assert err.status_code == 403
