"""Tests for the proposals API."""

import pytest
from httpx import AsyncClient, ASGITransport

from atlas_api.routes.proposals import _proposals


@pytest.fixture(autouse=True)
def clear_proposals():
    _proposals.clear()
    yield
    _proposals.clear()


def _get_app():
    """Import app with mocked DB to avoid real PostgreSQL."""
    from unittest.mock import patch, AsyncMock, MagicMock

    mock_pool = AsyncMock()
    mock_pool.open = AsyncMock()
    mock_pool.close = AsyncMock()

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=mock_pool):
        from atlas_api.main import app
        return app


@pytest.mark.asyncio
async def test_create_proposal():
    app = _get_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/proposals", json={
            "graph_id": "g1",
            "plan_id": "p1",
            "title": "Add timeouts to all jobs",
            "author": "yoad",
            "suggestion_count": 3,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Add timeouts to all jobs"
        assert data["status"] == "draft"


@pytest.mark.asyncio
async def test_list_proposals():
    app = _get_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/api/v1/proposals", json={
            "graph_id": "g1", "plan_id": "p1", "title": "Fix 1"
        })
        await client.post("/api/v1/proposals", json={
            "graph_id": "g2", "plan_id": "p2", "title": "Fix 2"
        })
        resp = await client.get("/api/v1/proposals")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_approve_lifecycle():
    app = _get_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create
        resp = await client.post("/api/v1/proposals", json={
            "graph_id": "g1", "plan_id": "p1", "title": "Fix timeouts"
        })
        pid = resp.json()["id"]

        # Submit (draft → pending)
        resp = await client.patch(f"/api/v1/proposals/{pid}", json={
            "status": "pending"
        })
        assert resp.json()["status"] == "pending"

        # Approve (pending → approved)
        resp = await client.patch(f"/api/v1/proposals/{pid}", json={
            "status": "approved",
            "reviewer": "admin",
            "comment": "Looks good!"
        })
        assert resp.json()["status"] == "approved"
        assert len(resp.json()["comments"]) == 1


@pytest.mark.asyncio
async def test_invalid_transition():
    app = _get_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/proposals", json={
            "graph_id": "g1", "plan_id": "p1", "title": "Fix"
        })
        pid = resp.json()["id"]

        # Cannot go from draft → approved directly
        resp = await client.patch(f"/api/v1/proposals/{pid}", json={
            "status": "approved"
        })
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_404_not_found():
    app = _get_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/proposals/nonexistent")
        assert resp.status_code == 404
