"""Tests for GET /api/v1/reports/{graph_id} endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from tests.conftest import admin_headers


def _make_mock_conn(fetchone_return=None):
    """Build a mock AsyncConnection whose cursor works correctly."""
    mock_cursor = AsyncMock()
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchone = AsyncMock(return_value=fetchone_return)
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor)
    return mock_conn


def _get_app_with_db(mock_conn):
    from atlas_api.main import app
    from atlas_api.db import get_db_connection

    async def _override():
        yield mock_conn

    app.dependency_overrides[get_db_connection] = _override
    return app


@pytest.mark.asyncio
async def test_get_report_found():
    mock_conn = _make_mock_conn(fetchone_return=("my-pipeline", "github_actions"))
    app = _get_app_with_db(mock_conn)

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=AsyncMock()), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/reports/graph-abc-123",
                headers={"X-Tenant-Id": "tenant-1", **admin_headers()},
            )

    assert resp.status_code == 200
    data = resp.json()
    assert data["graph_id"] == "graph-abc-123"
    assert data["name"] == "my-pipeline"
    assert data["platform"] == "github_actions"
    assert "scores" in data
    assert "findings" in data


@pytest.mark.asyncio
async def test_get_report_not_found():
    mock_conn = _make_mock_conn(fetchone_return=None)
    app = _get_app_with_db(mock_conn)

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=AsyncMock()), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/reports/nonexistent-id",
                headers={"X-Tenant-Id": "tenant-1", **admin_headers()},
            )

    assert resp.status_code == 404
    assert "Graph not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_report_requires_tenant_header():
    mock_conn = _make_mock_conn()
    app = _get_app_with_db(mock_conn)

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=AsyncMock()), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/reports/graph-abc",
                headers=admin_headers(),  # No X-Tenant-Id
            )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_report_scores_structure():
    mock_conn = _make_mock_conn(fetchone_return=("pipeline-x", "jenkins"))
    app = _get_app_with_db(mock_conn)

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=AsyncMock()), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/reports/graph-xyz",
                headers={"X-Tenant-Id": "tenant-1", **admin_headers()},
            )

    data = resp.json()
    scores = data["scores"]
    assert "complexity_score" in scores
    assert "fragility_score" in scores
    assert "overall_health" in scores


@pytest.mark.asyncio
async def test_get_report_findings_structure():
    mock_conn = _make_mock_conn(fetchone_return=("pipeline-y", "gitlab"))
    app = _get_app_with_db(mock_conn)

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=AsyncMock()), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/reports/graph-yyy",
                headers={"X-Tenant-Id": "tenant-1", **admin_headers()},
            )

    data = resp.json()
    assert isinstance(data["findings"], list)
    if data["findings"]:
        finding = data["findings"][0]
        assert "rule_id" in finding
        assert "severity" in finding
