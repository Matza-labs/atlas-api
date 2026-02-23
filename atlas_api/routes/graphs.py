"""Graphs API endpoints."""

import json
from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from atlas_api.db import get_db_connection
from atlas_api.dependencies import get_tenant_id

router = APIRouter()


@router.get("/")
async def list_graphs(
    limit: int = 50,
    conn: AsyncConnection = Depends(get_db_connection),
    tenant_id: str = Depends(get_tenant_id),
):
    """List all stored graphs for the tenant."""
    # MVP: We use the tenant_id as a dummy filter or just ignore it if no tenant col exists yet.
    # We will query the cicd_graphs table created by atlas-graph
    
    # Let's ensure the table exists or handle if it doesn't
    try:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT id, name, platform, created_at FROM cicd_graphs "
                "ORDER BY updated_at DESC LIMIT %s",
                (limit,)
            )
            rows = await cur.fetchall()
            
        return [
            {"id": r[0], "name": r[1], "platform": r[2], "created_at": r[3]}
            for r in rows
        ]
    except Exception as e:
        # Table might not exist if graph service hasn't run
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
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
