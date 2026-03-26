"""Tests for FastAPI dependency functions."""

import pytest
from fastapi import HTTPException
from starlette.datastructures import State
from starlette.requests import Request

from alphawatch.api.dependencies import get_current_user, require_role
from alphawatch.schemas.auth import CurrentUser


def _make_request(tenant_id=None, user_id=None, role=None) -> Request:
    """Create a mock Request with state attributes."""
    scope = {"type": "http", "method": "GET", "path": "/test"}
    request = Request(scope)
    request._state = State()
    if tenant_id is not None:
        request.state.tenant_id = tenant_id
    if user_id is not None:
        request.state.user_id = user_id
    if role is not None:
        request.state.role = role
    return request


class TestGetCurrentUser:
    """Test get_current_user dependency."""

    def test_extracts_user_from_state(self):
        request = _make_request(
            tenant_id="t-123", user_id="u-456", role="analyst"
        )
        user = get_current_user(request)
        assert isinstance(user, CurrentUser)
        assert user.tenant_id == "t-123"
        assert user.user_id == "u-456"
        assert user.role == "analyst"

    def test_raises_401_when_missing_tenant_id(self):
        request = _make_request(user_id="u-456", role="analyst")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request)
        assert exc_info.value.status_code == 401

    def test_raises_401_when_missing_user_id(self):
        request = _make_request(tenant_id="t-123", role="analyst")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request)
        assert exc_info.value.status_code == 401

    def test_raises_401_when_missing_role(self):
        request = _make_request(tenant_id="t-123", user_id="u-456")
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request)
        assert exc_info.value.status_code == 401

    def test_raises_401_when_completely_empty(self):
        request = _make_request()
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(request)
        assert exc_info.value.status_code == 401


class TestRequireRole:
    """Test require_role dependency factory."""

    def test_allows_matching_role(self):
        user = CurrentUser(tenant_id="t-1", user_id="u-1", role="admin")
        check = require_role(["admin", "analyst"])
        result = check(user=user)
        assert result.role == "admin"

    def test_rejects_non_matching_role(self):
        user = CurrentUser(tenant_id="t-1", user_id="u-1", role="viewer")
        check = require_role(["admin"])
        with pytest.raises(HTTPException) as exc_info:
            check(user=user)
        assert exc_info.value.status_code == 403

    def test_allows_analyst_for_analyst_role(self):
        user = CurrentUser(tenant_id="t-1", user_id="u-1", role="analyst")
        check = require_role(["analyst"])
        result = check(user=user)
        assert result.role == "analyst"
