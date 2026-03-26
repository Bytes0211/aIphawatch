"""Shared test fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from alphawatch.api.main import create_app


@pytest.fixture
def app():
    """Create a fresh FastAPI app instance for testing."""
    return create_app()


@pytest.fixture
def client(app):
    """Synchronous test client."""
    return TestClient(app)


@pytest.fixture
async def async_client(app):
    """Async test client for async endpoint tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
