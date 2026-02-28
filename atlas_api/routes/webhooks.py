"""Webhook API routes — receive CI platform events and trigger scans.

Endpoints:
    POST /api/v1/webhooks/github  — GitHub push/PR webhook (verified by HMAC signature)
    POST /api/v1/webhooks/gitlab  — GitLab push webhook (verified by secret token)
    GET  /api/v1/webhooks/events  — list received webhook events (requires auth)
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from psycopg import AsyncConnection
from pydantic import BaseModel

from atlas_api.auth import get_current_user
from atlas_api.db import get_db_connection
from atlas_api.limiter import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

# Webhook secrets from environment — MUST be set in production
_GITHUB_WEBHOOK_SECRET = os.environ.get("ATLAS_GITHUB_WEBHOOK_SECRET", "")
_GITLAB_WEBHOOK_SECRET = os.environ.get("ATLAS_GITLAB_WEBHOOK_SECRET", "")


class WebhookResponse(BaseModel):
    status: str
    message: str
    event_id: str | None = None


def _verify_github_signature(body: bytes, signature_header: str, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not secret:
        logger.warning("ATLAS_GITHUB_WEBHOOK_SECRET not set — skipping signature verification")
        return True  # Allow in dev; MUST be set in production
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _verify_gitlab_token(token_header: str, secret: str) -> bool:
    """Verify GitLab webhook secret token."""
    if not secret:
        logger.warning("ATLAS_GITLAB_WEBHOOK_SECRET not set — skipping token verification")
        return True  # Allow in dev; MUST be set in production
    if not token_header:
        return False
    return hmac.compare_digest(secret, token_header)


@router.post("/github", status_code=202, response_model=WebhookResponse)
@limiter.limit("500/hour")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(default=""),
    conn: AsyncConnection = Depends(get_db_connection),
) -> WebhookResponse:
    """Handle GitHub push/PR webhook events with HMAC-SHA256 signature verification."""
    from uuid import uuid4

    body = await request.body()

    if not _verify_github_signature(body, x_hub_signature_256, _GITHUB_WEBHOOK_SECRET):
        logger.warning("GitHub webhook signature verification failed")
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        import json
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = request.headers.get("X-GitHub-Event", "unknown")
    event_id = str(uuid4())
    repository = payload.get("repository", {}).get("full_name", "")
    ref = payload.get("ref", "")
    sender = payload.get("sender", {}).get("login", "")
    action = payload.get("action", "")
    received_at = datetime.now(timezone.utc)

    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO webhook_events
                    (id, platform, event_type, repository, ref, sender, action, received_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (event_id, "github", event_type, repository, ref, sender, action, received_at),
            )
        await conn.commit()
    except Exception:
        logger.exception("Failed to persist GitHub webhook event %s", event_id)

    logger.info("GitHub %s event from %s (id=%s)", event_type, repository, event_id)

    # In production: queue a scan request via Redis Streams
    return WebhookResponse(
        status="accepted",
        message=f"GitHub {event_type} event received for {repository}",
        event_id=event_id,
    )


@router.post("/gitlab", status_code=202, response_model=WebhookResponse)
@limiter.limit("500/hour")
async def gitlab_webhook(
    request: Request,
    x_gitlab_token: str = Header(default=""),
    conn: AsyncConnection = Depends(get_db_connection),
) -> WebhookResponse:
    """Handle GitLab push webhook events with secret token verification."""
    from uuid import uuid4

    if not _verify_gitlab_token(x_gitlab_token, _GITLAB_WEBHOOK_SECRET):
        logger.warning("GitLab webhook token verification failed")
        raise HTTPException(status_code=401, detail="Invalid webhook token")

    body = await request.body()
    try:
        import json
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = payload.get("object_kind", "unknown")
    event_id = str(uuid4())
    repository = payload.get("project", {}).get("path_with_namespace", "")
    ref = payload.get("ref", "")
    sender = payload.get("user_name", "")
    received_at = datetime.now(timezone.utc)

    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO webhook_events
                    (id, platform, event_type, repository, ref, sender, action, received_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (event_id, "gitlab", event_type, repository, ref, sender, "", received_at),
            )
        await conn.commit()
    except Exception:
        logger.exception("Failed to persist GitLab webhook event %s", event_id)

    logger.info("GitLab %s event from %s (id=%s)", event_type, repository, event_id)

    return WebhookResponse(
        status="accepted",
        message=f"GitLab {event_type} event received for {repository}",
        event_id=event_id,
    )


@router.get("/events")
async def list_events(
    limit: int = 20,
    authorization: str = Header(...),
    conn: AsyncConnection = Depends(get_db_connection),
) -> list[dict[str, Any]]:
    """List recent webhook events — requires authentication."""
    get_current_user(authorization)
    limit = min(limit, 200)

    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, platform, event_type, repository, ref, sender, action, received_at
                FROM webhook_events
                ORDER BY received_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = await cur.fetchall()

        return [
            {
                "id": r[0],
                "platform": r[1],
                "event_type": r[2],
                "repository": r[3],
                "ref": r[4],
                "sender": r[5],
                "action": r[6],
                "received_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]
    except Exception:
        logger.exception("Failed to fetch webhook events")
        return []
