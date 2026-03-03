"""Tests for the trends API — PostgreSQL-backed routes."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from tests.conftest import admin_headers


def _get_app_with_mock_db(mock_conn):
    from unittest.mock import patch

    mock_pool = AsyncMock()
    mock_pool.open = AsyncMock()
    mock_pool.close = AsyncMock()

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=mock_pool), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        from atlas_api.main import app
        from atlas_api.db import get_db_connection

        async def override_db():
            yield mock_conn

        app.dependency_overrides[get_db_connection] = override_db
        return app


def _make_mock_conn(fetchone_result=None, fetchall_result=None):
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=fetchone_result)
    cursor.fetchall = AsyncMock(return_value=fetchall_result or [])
    cursor.execute = AsyncMock()

    conn = MagicMock()
    conn.cursor = MagicMock(return_value=cursor)
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=False)
    conn.commit = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_create_snapshot():
    row = ("s-1", "My CI", "", 45.0, 60.0, 35.0, 12, 0, 0, "2026-01-01")
    conn = _make_mock_conn(fetchone_result=row)
    app = _get_app_with_mock_db(conn)
    hdrs = admin_headers()

    try:
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
    finally:
        from atlas_api.db import get_db_connection
        app.dependency_overrides.pop(get_db_connection, None)


@pytest.mark.asyncio
async def test_get_trends_no_data():
    conn = _make_mock_conn(fetchall_result=[])  # No rows
    app = _get_app_with_mock_db(conn)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/trends/NonExistent", headers=admin_headers())
            assert resp.status_code == 404
    finally:
        from atlas_api.db import get_db_connection
        app.dependency_overrides.pop(get_db_connection, None)
