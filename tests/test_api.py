"""Integration tests for the FastAPI application."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from atlas_api.main import app
from atlas_api.db import get_db_connection, get_db_pool

# Mock dependencies — pool.connection() and conn.cursor() are synchronous methods
# in psycopg that return async context managers, so we use MagicMock (not AsyncMock)
# for the method itself and set __aenter__/__aexit__ on the returned object.
async def mock_get_db_connection():
    mock_cur = AsyncMock()
    mock_cur.fetchall = AsyncMock(return_value=[])
    mock_cur.fetchone = AsyncMock(return_value=None)
    cur_cm = MagicMock()
    cur_cm.__aenter__ = AsyncMock(return_value=mock_cur)
    cur_cm.__aexit__ = AsyncMock(return_value=False)
    mock_conn = MagicMock()
    mock_conn.cursor = MagicMock(return_value=cur_cm)
    mock_conn.execute = AsyncMock()
    yield mock_conn

async def mock_get_db_pool():
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    conn_cm = MagicMock()
    conn_cm.__aenter__ = AsyncMock(return_value=mock_conn)
    conn_cm.__aexit__ = AsyncMock(return_value=False)
    mock_pool = MagicMock()
    mock_pool.connection = MagicMock(return_value=conn_cm)
    return mock_pool

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
