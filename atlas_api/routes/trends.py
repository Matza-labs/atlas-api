"""Trends API routes — time-series score tracking (PostgreSQL-backed).

Endpoints:
    POST   /api/v1/snapshots          — store a scan snapshot
    GET    /api/v1/trends/{graph_name} — get trend data for a pipeline
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from atlas_api.auth import get_current_user
from atlas_api.db import get_db_connection

router = APIRouter(prefix="/api/v1", tags=["trends"])


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
async def create_snapshot(
    req: CreateSnapshotRequest,
    authorization: str = Header(...),
    conn=Depends(get_db_connection),
) -> dict[str, Any]:
    """Store a scan snapshot."""
    get_current_user(authorization)
    from uuid import uuid4

    snapshot_id = str(uuid4())
    now = datetime.now(timezone.utc)

    async with conn.cursor() as cur:
        await cur.execute(
            """INSERT INTO snapshots (id, graph_name, graph_id, complexity_score, fragility_score, maturity_score, finding_count, node_count, edge_count, scanned_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (snapshot_id, req.graph_name, req.graph_id, req.complexity_score,
             req.fragility_score, req.maturity_score, req.finding_count,
             req.node_count, req.edge_count, now),
        )
    await conn.commit()

    return {
        "id": snapshot_id,
        "graph_name": req.graph_name,
        "graph_id": req.graph_id,
        "complexity_score": req.complexity_score,
        "fragility_score": req.fragility_score,
        "maturity_score": req.maturity_score,
        "finding_count": req.finding_count,
        "node_count": req.node_count,
        "edge_count": req.edge_count,
        "scanned_at": now.isoformat(),
    }


@router.get("/trends/{graph_name}")
async def get_trends(
    graph_name: str,
    authorization: str = Header(...),
    conn=Depends(get_db_connection),
) -> dict[str, Any]:
    """Get trend data for a pipeline."""
    get_current_user(authorization)

    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT * FROM snapshots WHERE graph_name = %s ORDER BY scanned_at ASC",
            (graph_name,),
        )
        rows = await cur.fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail=f"No snapshots for '{graph_name}'")

        cols = [d.name for d in cur.description]
        snapshots = []
        for row in rows:
            s = dict(zip(cols, row))
            if isinstance(s.get("scanned_at"), datetime):
                s["scanned_at"] = s["scanned_at"].isoformat()
            snapshots.append(s)

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
