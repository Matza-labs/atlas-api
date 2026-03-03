"""Tests for the proposals API — PostgreSQL-backed routes."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from tests.conftest import admin_headers

# Column descriptions matching the proposals table
_PROPOSAL_COLS = ["id", "graph_id", "plan_id", "title", "description",
                  "author", "status", "suggestion_count", "diff_preview",
                  "created_at", "updated_at"]


class _ColDesc:
    """Mimics psycopg cursor.description column descriptor."""
    def __init__(self, col_name):
        self.name = col_name


def _col_desc(names):
    """Mock cursor.description — list of objects with .name attribute."""
    return [_ColDesc(n) for n in names]


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


def _make_mock_conn(fetchone_result=None, fetchall_result=None, col_names=None):
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=fetchone_result)
    cursor.fetchall = AsyncMock(return_value=fetchall_result or [])
    cursor.execute = AsyncMock()
    if col_names:
        cursor.description = _col_desc(col_names)
    else:
        cursor.description = _col_desc(_PROPOSAL_COLS)

    conn = MagicMock()
    conn.cursor = MagicMock(return_value=cursor)
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=False)
    conn.commit = AsyncMock()
    return conn


@pytest.mark.asyncio
async def test_create_proposal():
    row = ("p-1", "g1", "p1", "Add timeouts", "", "yoad", "draft", 3, "", "2026-01-01", "2026-01-01")
    conn = _make_mock_conn(fetchone_result=row, fetchall_result=[])
    app = _get_app_with_mock_db(conn)
    hdrs = admin_headers()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/proposals", json={
                "graph_id": "g1",
                "plan_id": "p1",
                "title": "Add timeouts",
                "author": "yoad",
                "suggestion_count": 3,
            }, headers=hdrs)
            assert resp.status_code == 201
            data = resp.json()
            assert data["title"] == "Add timeouts"
            assert data["status"] == "draft"
    finally:
        from atlas_api.db import get_db_connection
        app.dependency_overrides.pop(get_db_connection, None)


@pytest.mark.asyncio
async def test_404_not_found():
    conn = _make_mock_conn(fetchone_result=None)
    app = _get_app_with_mock_db(conn)

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/proposals/nonexistent", headers=admin_headers())
            assert resp.status_code == 404
    finally:
        from atlas_api.db import get_db_connection
        app.dependency_overrides.pop(get_db_connection, None)
