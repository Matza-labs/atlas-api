"""Integration tests for the FastAPI application."""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport

from atlas_api.main import app
from atlas_api.db import get_db_connection, get_db_pool

# Mock dependencies
async def mock_get_db_connection():
    yield AsyncMock()

async def mock_get_db_pool():
    return AsyncMock()

app.dependency_overrides[get_db_connection] = mock_get_db_connection
app.dependency_overrides[get_db_pool] = mock_get_db_pool

@pytest.fixture(autouse=True)
def mock_db_lifespan():
    with patch("atlas_api.main.init_db"), patch("atlas_api.main.get_db_pool", return_value=AsyncMock()):
        yield

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "atlas-api"
        assert data["status"] in ["up", "degraded"]

@pytest.mark.asyncio
async def test_missing_tenant_header():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/graphs/")
        assert response.status_code == 401
        assert "X-Tenant-Id header is required" in response.json()["detail"]

@pytest.mark.asyncio
async def test_get_graphs_unauthorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/graphs/123-abc")
        assert response.status_code == 401

@pytest.mark.asyncio
async def test_get_graphs_authorized():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # DB connection is mocked, so an empty list or mock data would be returned if not raised.
        # Let's mock the cursor fetch logic
        response = await client.get("/api/v1/graphs/", headers={"X-Tenant-Id": "tenant-1"})
        assert response.status_code == 200
        assert isinstance(response.json(), list)
