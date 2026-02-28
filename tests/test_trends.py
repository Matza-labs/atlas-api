"""Tests for the trends API."""

import pytest
from httpx import AsyncClient, ASGITransport

from atlas_api.routes.trends import _snapshots
from tests.conftest import admin_headers


@pytest.fixture(autouse=True)
def clear_snapshots():
    _snapshots.clear()
    yield
    _snapshots.clear()


def _get_app():
    from unittest.mock import patch, AsyncMock
    mock_pool = AsyncMock()
    mock_pool.open = AsyncMock()
    mock_pool.close = AsyncMock()
    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=mock_pool):
        from atlas_api.main import app
        return app


@pytest.mark.asyncio
async def test_create_snapshot():
    app = _get_app()
    hdrs = admin_headers()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/snapshots", json={
            "graph_name": "My CI",
            "complexity_score": 45.0,
            "fragility_score": 60.0,
            "maturity_score": 35.0,
            "finding_count": 12,
        }, headers=hdrs)
        assert resp.status_code == 201
        data = resp.json()
        assert data["graph_name"] == "My CI"
        assert data["complexity_score"] == 45.0


@pytest.mark.asyncio
async def test_get_trends_no_data():
    app = _get_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/trends/NonExistent", headers=admin_headers())
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_trends_with_data():
    app = _get_app()
    hdrs = admin_headers()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create two snapshots to generate trends
        await client.post("/api/v1/snapshots", json={
            "graph_name": "CI Pipeline",
            "complexity_score": 50.0,
            "fragility_score": 60.0,
            "maturity_score": 30.0,
            "finding_count": 15,
        }, headers=hdrs)
        await client.post("/api/v1/snapshots", json={
            "graph_name": "CI Pipeline",
            "complexity_score": 40.0,
            "fragility_score": 45.0,
            "maturity_score": 50.0,
            "finding_count": 8,
        }, headers=hdrs)

        resp = await client.get("/api/v1/trends/CI Pipeline", headers=hdrs)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_snapshots"] == 2
        assert len(data["trends"]) == 3

        # Complexity went down = improved
        complexity_trend = next(t for t in data["trends"] if t["metric"] == "complexity")
        assert complexity_trend["direction"] == "improved"
        assert complexity_trend["delta"] == -10.0

        # Maturity went up = improved
        maturity_trend = next(t for t in data["trends"] if t["metric"] == "maturity")
        assert maturity_trend["direction"] == "improved"
        assert maturity_trend["delta"] == 20.0
