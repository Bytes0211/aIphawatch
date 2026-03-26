"""Tests for API endpoints and middleware behavior."""

import pytest


class TestHealthEndpoint:
    """Test GET /health endpoint."""

    async def test_health_returns_200(self, async_client):
        resp = await async_client.get("/health")
        assert resp.status_code == 200

    async def test_health_returns_ok_status(self, async_client):
        resp = await async_client.get("/health")
        assert resp.json() == {"status": "ok"}

    async def test_health_no_auth_required(self, async_client):
        # No Authorization header — should still succeed
        resp = await async_client.get("/health")
        assert resp.status_code == 200


class TestMiddlewareAuth:
    """Test TenantMiddleware authentication enforcement."""

    async def test_unauthenticated_request_returns_401(self, async_client):
        resp = await async_client.get("/api/anything")
        assert resp.status_code == 401
        assert "Missing Authorization header" in resp.json()["detail"]

    async def test_bad_bearer_format_returns_401(self, async_client):
        resp = await async_client.get(
            "/api/anything",
            headers={"Authorization": "Basic abc123"},
        )
        assert resp.status_code == 401

    async def test_docs_endpoint_skips_auth(self, async_client):
        resp = await async_client.get("/docs")
        # FastAPI docs returns HTML, not 401
        assert resp.status_code == 200

    async def test_openapi_json_skips_auth(self, async_client):
        resp = await async_client.get("/openapi.json")
        assert resp.status_code == 200
        assert "paths" in resp.json()


class TestSchemas:
    """Test Pydantic schemas."""

    def test_current_user_schema(self):
        from alphawatch.schemas.auth import CurrentUser

        user = CurrentUser(tenant_id="t-1", user_id="u-1", role="analyst")
        assert user.tenant_id == "t-1"
        assert user.model_dump() == {
            "tenant_id": "t-1",
            "user_id": "u-1",
            "role": "analyst",
        }

    def test_health_response_default(self):
        from alphawatch.schemas.common import HealthResponse

        h = HealthResponse()
        assert h.status == "ok"

    def test_error_response(self):
        from alphawatch.schemas.common import ErrorResponse

        e = ErrorResponse(detail="something went wrong")
        assert e.detail == "something went wrong"
