"""Webhook API routes — receive CI platform events and trigger scans.

Endpoints:
    POST /api/v1/webhooks/github  — GitHub push/PR webhook
    POST /api/v1/webhooks/gitlab  — GitLab push webhook
    GET  /api/v1/webhooks/events  — list received webhook events
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

# In-memory event log
_webhook_events: list[dict[str, Any]] = []


class WebhookResponse(BaseModel):
    status: str
    message: str
    event_id: str | None = None


@router.post("/github", status_code=202)
async def github_webhook(request: Request) -> WebhookResponse:
    """Handle GitHub push/PR webhook events."""
    from uuid import uuid4

    body = await request.json()
    event_type = request.headers.get("X-GitHub-Event", "unknown")

    event = {
        "id": str(uuid4()),
        "platform": "github",
        "event_type": event_type,
        "repository": body.get("repository", {}).get("full_name", ""),
        "ref": body.get("ref", ""),
        "sender": body.get("sender", {}).get("login", ""),
        "received_at": datetime.now(timezone.utc).isoformat(),
        "action": body.get("action", ""),
    }
    _webhook_events.append(event)

    # In production: queue a scan request via Redis Streams
    return WebhookResponse(
        status="accepted",
        message=f"GitHub {event_type} event received for {event['repository']}",
        event_id=event["id"],
    )


@router.post("/gitlab", status_code=202)
async def gitlab_webhook(request: Request) -> WebhookResponse:
    """Handle GitLab push webhook events."""
    from uuid import uuid4

    body = await request.json()
    event_type = body.get("object_kind", "unknown")

    event = {
        "id": str(uuid4()),
        "platform": "gitlab",
        "event_type": event_type,
        "repository": body.get("project", {}).get("path_with_namespace", ""),
        "ref": body.get("ref", ""),
        "sender": body.get("user_name", ""),
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    _webhook_events.append(event)

    return WebhookResponse(
        status="accepted",
        message=f"GitLab {event_type} event received for {event['repository']}",
        event_id=event["id"],
    )


@router.get("/events")
async def list_events(limit: int = 20) -> list[dict[str, Any]]:
    """List recent webhook events."""
    return _webhook_events[-limit:]
