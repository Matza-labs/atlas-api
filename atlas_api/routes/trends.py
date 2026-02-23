"""Trends API routes — time-series score tracking.

Endpoints:
    POST   /api/v1/snapshots          — store a scan snapshot
    GET    /api/v1/trends/{graph_name} — get trend data for a pipeline
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["trends"])

# In-memory store (MVP — PostgreSQL in production)
_snapshots: dict[str, list[dict[str, Any]]] = {}  # graph_name → [snapshots]


class CreateSnapshotRequest(BaseModel):
    graph_name: str
    graph_id: str = ""
    complexity_score: float = 0.0
    fragility_score: float = 0.0
    maturity_score: float = 0.0
    finding_count: int = 0
    node_count: int = 0
    edge_count: int = 0


@router.post("/snapshots", status_code=201)
async def create_snapshot(req: CreateSnapshotRequest) -> dict[str, Any]:
    """Store a scan snapshot."""
    from uuid import uuid4

    snapshot = {
        "id": str(uuid4()),
        "graph_name": req.graph_name,
        "graph_id": req.graph_id,
        "complexity_score": req.complexity_score,
        "fragility_score": req.fragility_score,
        "maturity_score": req.maturity_score,
        "finding_count": req.finding_count,
        "node_count": req.node_count,
        "edge_count": req.edge_count,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
    }

    if req.graph_name not in _snapshots:
        _snapshots[req.graph_name] = []
    _snapshots[req.graph_name].append(snapshot)

    return snapshot


@router.get("/trends/{graph_name}")
async def get_trends(graph_name: str) -> dict[str, Any]:
    """Get trend data for a pipeline."""
    snapshots = _snapshots.get(graph_name, [])
    if not snapshots:
        raise HTTPException(status_code=404, detail=f"No snapshots for '{graph_name}'")

    trends = []
    if len(snapshots) >= 2:
        prev = snapshots[-2]
        curr = snapshots[-1]
        for metric in ("complexity_score", "fragility_score", "maturity_score"):
            delta = round(curr[metric] - prev[metric], 1)
            if metric == "maturity_score":
                direction = "improved" if delta > 0 else ("regressed" if delta < 0 else "stable")
            else:
                direction = "improved" if delta < 0 else ("regressed" if delta > 0 else "stable")
            trends.append({
                "metric": metric.replace("_score", ""),
                "previous": prev[metric],
                "current": curr[metric],
                "delta": delta,
                "direction": direction,
            })

    return {
        "graph_name": graph_name,
        "total_snapshots": len(snapshots),
        "snapshots": snapshots,
        "trends": trends,
    }
