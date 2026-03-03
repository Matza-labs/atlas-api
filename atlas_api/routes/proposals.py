"""Proposal API routes — CRUD for refactor proposals (PostgreSQL-backed).

Endpoints:
    POST   /api/v1/proposals      — create a new proposal
    GET    /api/v1/proposals      — list proposals (with status filter)
    GET    /api/v1/proposals/{id} — get full proposal detail
    PATCH  /api/v1/proposals/{id} — approve/reject/modify
    POST   /api/v1/proposals/{id}/apply — auto-apply approved fixes
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from atlas_api.auth import get_current_user, require_role
from atlas_api.db import get_db_connection

router = APIRouter(prefix="/api/v1/proposals", tags=["proposals"])


class CreateProposalRequest(BaseModel):
    graph_id: str
    plan_id: str
    title: str
    description: str = ""
    author: str = ""
    suggestion_count: int = 0
    diff_preview: str = ""


class UpdateProposalRequest(BaseModel):
    status: str | None = None  # approved, rejected
    reviewer: str = ""
    comment: str = ""


async def _fetch_proposal(cur: Any, proposal_id: str) -> dict[str, Any] | None:
    """Fetch a single proposal with its comments."""
    await cur.execute("SELECT * FROM proposals WHERE id = %s", (proposal_id,))
    row = await cur.fetchone()
    if not row:
        return None
    cols = [d.name for d in cur.description]
    proposal = dict(zip(cols, row))

    await cur.execute(
        "SELECT author, text, created_at FROM proposal_comments WHERE proposal_id = %s ORDER BY created_at",
        (proposal_id,),
    )
    comment_rows = await cur.fetchall()
    proposal["comments"] = [
        {"author": r[0], "text": r[1], "created_at": r[2].isoformat() if r[2] else ""}
        for r in comment_rows
    ]
    # Convert timestamps
    for key in ("created_at", "updated_at"):
        if isinstance(proposal.get(key), datetime):
            proposal[key] = proposal[key].isoformat()
    return proposal


@router.post("", status_code=201)
async def create_proposal(
    req: CreateProposalRequest,
    authorization: str = Header(...),
    conn=Depends(get_db_connection),
) -> dict[str, Any]:
    """Create a new refactor proposal."""
    user = get_current_user(authorization)
    require_role(user, "auditor")

    from uuid import uuid4
    proposal_id = str(uuid4())
    now = datetime.now(timezone.utc)

    async with conn.cursor() as cur:
        await cur.execute(
            """INSERT INTO proposals (id, graph_id, plan_id, title, description, author, status, suggestion_count, diff_preview, created_at, updated_at)
               VALUES (%s, %s, %s, %s, %s, %s, 'draft', %s, %s, %s, %s)""",
            (proposal_id, req.graph_id, req.plan_id, req.title, req.description,
             req.author, req.suggestion_count, req.diff_preview, now, now),
        )
    await conn.commit()

    async with conn.cursor() as cur:
        return await _fetch_proposal(cur, proposal_id)  # type: ignore[return-value]


@router.get("")
async def list_proposals(
    status: str | None = None,
    authorization: str = Header(...),
    conn=Depends(get_db_connection),
) -> list[dict[str, Any]]:
    """List all proposals, optionally filtered by status."""
    get_current_user(authorization)

    async with conn.cursor() as cur:
        if status:
            await cur.execute("SELECT id FROM proposals WHERE status = %s ORDER BY created_at DESC", (status,))
        else:
            await cur.execute("SELECT id FROM proposals ORDER BY created_at DESC")
        ids = [r[0] for r in await cur.fetchall()]
        results = []
        for pid in ids:
            p = await _fetch_proposal(cur, pid)
            if p:
                results.append(p)
    return results


@router.get("/{proposal_id}")
async def get_proposal(
    proposal_id: str,
    authorization: str = Header(...),
    conn=Depends(get_db_connection),
) -> dict[str, Any]:
    """Get a single proposal by ID."""
    get_current_user(authorization)
    async with conn.cursor() as cur:
        proposal = await _fetch_proposal(cur, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return proposal


@router.patch("/{proposal_id}")
async def update_proposal(
    proposal_id: str,
    req: UpdateProposalRequest,
    authorization: str = Header(...),
    conn=Depends(get_db_connection),
) -> dict[str, Any]:
    """Update a proposal's status (approve/reject)."""
    user = get_current_user(authorization)
    require_role(user, "auditor")

    async with conn.cursor() as cur:
        proposal = await _fetch_proposal(cur, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    now = datetime.now(timezone.utc)

    if req.status:
        valid_transitions = {
            "draft": ["pending"],
            "pending": ["approved", "rejected"],
        }
        allowed = valid_transitions.get(proposal["status"], [])
        if req.status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from '{proposal['status']}' to '{req.status}'"
            )
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE proposals SET status = %s, updated_at = %s WHERE id = %s",
                (req.status, now, proposal_id),
            )

    if req.comment:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO proposal_comments (proposal_id, author, text, created_at) VALUES (%s, %s, %s, %s)",
                (proposal_id, req.reviewer or "system", req.comment, now),
            )

    async with conn.cursor() as cur:
        await cur.execute("UPDATE proposals SET updated_at = %s WHERE id = %s", (now, proposal_id))
    await conn.commit()

    async with conn.cursor() as cur:
        return await _fetch_proposal(cur, proposal_id)  # type: ignore[return-value]


@router.post("/{proposal_id}/apply")
async def apply_proposal(
    proposal_id: str,
    authorization: str = Header(...),
    conn=Depends(get_db_connection),
) -> dict[str, Any]:
    """Apply a proposal's refactor plan back to the CI system (simulated)."""
    user = get_current_user(authorization)
    require_role(user, "admin")

    async with conn.cursor() as cur:
        proposal = await _fetch_proposal(cur, proposal_id)
    if not proposal:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if proposal["status"] != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot apply proposal in '{proposal['status']}' state. Must be 'approved'."
        )

    now = datetime.now(timezone.utc)
    async with conn.cursor() as cur:
        await cur.execute(
            "UPDATE proposals SET status = 'applied', updated_at = %s WHERE id = %s",
            (now, proposal_id),
        )
        await cur.execute(
            "INSERT INTO proposal_comments (proposal_id, author, text, created_at) VALUES (%s, %s, %s, %s)",
            (proposal_id, "system", "Automated fixes successfully pushed to repository.", now),
        )
    await conn.commit()

    async with conn.cursor() as cur:
        return await _fetch_proposal(cur, proposal_id)  # type: ignore[return-value]
