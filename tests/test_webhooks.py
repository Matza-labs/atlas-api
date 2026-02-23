"""Tests for webhook and notification system."""

import pytest
from httpx import AsyncClient, ASGITransport

from atlas_api.routes.webhooks import _webhook_events
from atlas_sdk.models.notifications import NotificationConfig, AlertEvent


@pytest.fixture(autouse=True)
def clear_events():
    _webhook_events.clear()
    yield
    _webhook_events.clear()


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
async def test_github_webhook():
    app = _get_app()
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


@pytest.mark.asyncio
async def test_gitlab_webhook():
    app = _get_app()
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
async def test_list_webhook_events():
    app = _get_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/webhooks/github",
            json={"repository": {"full_name": "repo1"}, "sender": {"login": "u"}},
            headers={"X-GitHub-Event": "push"},
        )
        await client.post(
            "/api/v1/webhooks/github",
            json={"repository": {"full_name": "repo2"}, "sender": {"login": "u"}},
            headers={"X-GitHub-Event": "pull_request"},
        )
        resp = await client.get("/api/v1/webhooks/events")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


def test_notification_config_should_alert():
    config = NotificationConfig(
        graph_name="CI",
        target="https://hooks.slack.com/test",
        thresholds={"complexity_max": 50, "fragility_max": 60, "maturity_min": 30},
    )
    # Should NOT alert — all within thresholds
    assert config.should_alert(40, 50, 40) is False
    # Should alert — complexity too high
    assert config.should_alert(60, 50, 40) is True
    # Should alert — maturity too low
    assert config.should_alert(40, 50, 20) is True


def test_notification_config_disabled():
    config = NotificationConfig(graph_name="CI", enabled=False)
    assert config.should_alert(100, 100, 0) is False
