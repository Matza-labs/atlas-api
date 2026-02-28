"""Tests for webhook endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from tests.conftest import admin_headers


def _make_mock_conn(fetchall_return=None):
    """Build a mock AsyncConnection whose cursor context manager works correctly."""
    mock_cursor = AsyncMock()
    mock_cursor.execute = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=fetchall_return or [])
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=False)

    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor)
    mock_conn.commit = AsyncMock()
    return mock_conn, mock_cursor


def _get_app_with_db(mock_conn):
    """Return the FastAPI app with get_db_connection overridden."""
    from atlas_api.main import app
    from atlas_api.db import get_db_connection

    async def _override():
        yield mock_conn

    app.dependency_overrides[get_db_connection] = _override
    return app


@pytest.mark.asyncio
async def test_github_webhook_accepted():
    mock_conn, _ = _make_mock_conn()
    app = _get_app_with_db(mock_conn)

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=AsyncMock()), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/webhooks/github",
                json={
                    "ref": "refs/heads/main",
                    "repository": {"full_name": "acme/backend"},
                    "sender": {"login": "yoad"},
                },
                headers={"X-GitHub-Event": "push"},
            )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "accepted"
    assert "acme/backend" in data["message"]
    assert data["event_id"] is not None


@pytest.mark.asyncio
async def test_github_webhook_inserts_into_db():
    mock_conn, mock_cursor = _make_mock_conn()
    app = _get_app_with_db(mock_conn)

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=AsyncMock()), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/v1/webhooks/github",
                json={"ref": "refs/heads/main", "repository": {"full_name": "acme/repo"}},
                headers={"X-GitHub-Event": "push"},
            )

    mock_cursor.execute.assert_called_once()
    call_sql = mock_cursor.execute.call_args[0][0]
    assert "INSERT INTO webhook_events" in call_sql
    mock_conn.commit.assert_called_once()


@pytest.mark.asyncio
async def test_gitlab_webhook_accepted():
    mock_conn, _ = _make_mock_conn()
    app = _get_app_with_db(mock_conn)

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=AsyncMock()), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/v1/webhooks/gitlab",
                json={
                    "object_kind": "push",
                    "ref": "refs/heads/main",
                    "project": {"path_with_namespace": "acme/api"},
                    "user_name": "yoad",
                },
            )

    assert resp.status_code == 202
    data = resp.json()
    assert "acme/api" in data["message"]


@pytest.mark.asyncio
async def test_gitlab_webhook_inserts_into_db():
    mock_conn, mock_cursor = _make_mock_conn()
    app = _get_app_with_db(mock_conn)

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=AsyncMock()), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(
                "/api/v1/webhooks/gitlab",
                json={
                    "object_kind": "push",
                    "project": {"path_with_namespace": "acme/api"},
                    "user_name": "yoad",
                },
            )

    mock_cursor.execute.assert_called_once()
    call_sql = mock_cursor.execute.call_args[0][0]
    assert "INSERT INTO webhook_events" in call_sql


@pytest.mark.asyncio
async def test_list_webhook_events_returns_db_rows():
    _now = datetime.now(timezone.utc)
    db_rows = [
        ("uuid-1", "github", "push", "acme/repo1", "refs/heads/main", "yoad", "", _now),
        ("uuid-2", "gitlab", "push", "acme/api", "refs/heads/dev", "alice", "", _now),
    ]
    mock_conn, _ = _make_mock_conn(fetchall_return=db_rows)
    app = _get_app_with_db(mock_conn)

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=AsyncMock()), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/webhooks/events", headers=admin_headers())

    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 2
    assert events[0]["id"] == "uuid-1"
    assert events[0]["platform"] == "github"
    assert events[1]["platform"] == "gitlab"


@pytest.mark.asyncio
async def test_list_webhook_events_empty():
    mock_conn, _ = _make_mock_conn(fetchall_return=[])
    app = _get_app_with_db(mock_conn)

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=AsyncMock()), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/webhooks/events", headers=admin_headers())

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_webhook_events_requires_auth():
    mock_conn, _ = _make_mock_conn()
    app = _get_app_with_db(mock_conn)

    with patch("atlas_api.main.init_db"), \
         patch("atlas_api.main.get_db_pool", return_value=AsyncMock()), \
         patch("atlas_api.main.create_tables", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/webhooks/events")

    assert resp.status_code == 422  # Missing required header


def test_notification_config_should_alert():
    from atlas_sdk.models.notifications import NotificationConfig
    config = NotificationConfig(
        graph_name="CI",
        target="https://hooks.slack.com/test",
        thresholds={"complexity_max": 50, "fragility_max": 60, "maturity_min": 30},
    )
    assert config.should_alert(40, 50, 40) is False
    assert config.should_alert(60, 50, 40) is True
    assert config.should_alert(40, 50, 20) is True


def test_notification_config_disabled():
    from atlas_sdk.models.notifications import NotificationConfig
    config = NotificationConfig(graph_name="CI", enabled=False)
    assert config.should_alert(100, 100, 0) is False
