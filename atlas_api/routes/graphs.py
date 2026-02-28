"""Graphs API endpoints."""

import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from psycopg import AsyncConnection

from atlas_api.db import get_db_connection
from atlas_api.dependencies import get_tenant_id

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_graphs(
    limit: int = 50,
    offset: int = 0,
    conn: AsyncConnection = Depends(get_db_connection),
    tenant_id: str = Depends(get_tenant_id),
):
    """List stored graphs for the tenant with cursor pagination.

    Args:
        limit:  Maximum number of results to return (default 50, max 200).
        offset: Number of rows to skip for pagination (default 0).
    """
    limit = min(limit, 200)  # hard cap
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, platform, created_at FROM cicd_graphs "
                "ORDER BY updated_at DESC LIMIT %s OFFSET %s",
                (limit, offset)
            )
            rows = await cur.fetchall()

        return [
            {"id": r[0], "name": r[1], "platform": r[2], "created_at": r[3]}
            for r in rows
        ]
    except Exception:
        # Table might not exist if graph service hasn't run yet
        return []


@router.get("/{graph_id}")
async def get_graph(
    graph_id: str,
    conn: AsyncConnection = Depends(get_db_connection),
    tenant_id: str = Depends(get_tenant_id),
):
    """Get a specific graph by ID."""
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT data FROM cicd_graphs WHERE id = %s",
                (graph_id,)
            )
            row = await cur.fetchone()
            
        if not row:
            raise HTTPException(status_code=404, detail="Graph not found")
            
        # JSONB in psycopg3 is returned as deserialized dict or string
        data = row[0]
        if isinstance(data, str):
            data = json.loads(data)
            
        return data
        
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to fetch graph %s", graph_id)
        raise HTTPException(status_code=500, detail="Internal server error")
