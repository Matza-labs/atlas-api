"""Proposal API routes — CRUD for refactor proposals.

Endpoints:
    POST   /api/v1/proposals      — create a new proposal
    GET    /api/v1/proposals      — list proposals (with status filter)
    GET    /api/v1/proposals/{id} — get full proposal detail
    PATCH  /api/v1/proposals/{id} — approve/reject/modify
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from atlas_api.auth import get_current_user, require_role

router = APIRouter(prefix="/api/v1/proposals", tags=["proposals"])

# In-memory store (MVP — would be PostgreSQL in production)
_proposals: dict[str, dict[str, Any]] = {}


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


@router.post("", status_code=201)
async def create_proposal(
    req: CreateProposalRequest,
    authorization: str = Header(...),
) -> dict[str, Any]:
    user = get_current_user(authorization)
    require_role(user, "auditor")
    """Create a new refactor proposal."""
    from uuid import uuid4

    proposal_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()

    proposal = {
        "id": proposal_id,
        "graph_id": req.graph_id,
        "plan_id": req.plan_id,
        "title": req.title,
        "description": req.description,
        "author": req.author,
        "status": "draft",
        "suggestion_count": req.suggestion_count,
        "diff_preview": req.diff_preview,
        "comments": [],
        "created_at": now,
        "updated_at": now,
    }
    _proposals[proposal_id] = proposal
    return proposal


@router.get("")
async def list_proposals(
    status: str | None = None,
    authorization: str = Header(...),
) -> list[dict[str, Any]]:
    get_current_user(authorization)  # any authenticated user can list
    """List all proposals, optionally filtered by status."""
    proposals = list(_proposals.values())
    if status:
        proposals = [p for p in proposals if p["status"] == status]
    return proposals


@router.get("/{proposal_id}")
async def get_proposal(
    proposal_id: str,
    authorization: str = Header(...),
) -> dict[str, Any]:
    get_current_user(authorization)
    """Get a single proposal by ID."""
    if proposal_id not in _proposals:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return _proposals[proposal_id]


@router.patch("/{proposal_id}")
async def update_proposal(
    proposal_id: str,
    req: UpdateProposalRequest,
    authorization: str = Header(...),
) -> dict[str, Any]:
    user = get_current_user(authorization)
    require_role(user, "auditor")
    """Update a proposal's status (approve/reject)."""
    if proposal_id not in _proposals:
        raise HTTPException(status_code=404, detail="Proposal not found")

    proposal = _proposals[proposal_id]

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
        proposal["status"] = req.status

    if req.comment:
        proposal["comments"].append({
            "author": req.reviewer or "system",
            "text": req.comment,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    proposal["updated_at"] = datetime.now(timezone.utc).isoformat()
    return proposal
