"""Reports API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from psycopg import AsyncConnection

from atlas_api.db import get_db_connection
from atlas_api.dependencies import get_tenant_id

router = APIRouter()


@router.get("/{graph_id}")
async def get_report_for_graph(
    graph_id: str,
    conn: AsyncConnection = Depends(get_db_connection),
    tenant_id: str = Depends(get_tenant_id),
):
    """Get the report for a specific graph.
    
    In a real implementation, this might read from a `reports` table 
    or generate it via the atlas-report library on the fly.
    """
    
    # For Sprint 9: Dummy response simulating a report object
    # until atlas-report storage is formalized.
    
    # 1. Fetch the graph to ensure it exists
    async with conn.cursor() as cur:
        await cur.execute("SELECT name, platform FROM cicd_graphs WHERE id = %s", (graph_id,))
        row = await cur.fetchone()
        
    if not row:
        raise HTTPException(status_code=404, detail="Graph not found")
        
    name, platform = row
    
    return {
        "graph_id": graph_id,
        "name": name,
        "platform": platform,
        "scores": {
            "complexity_score": 65.5,
            "fragility_score": 32.0,
            "overall_health": "good"
        },
        "findings": [
            {
                "rule_id": "no-timeout",
                "severity": "medium",
                "message": "Job is missing a timeout"
            }
        ]
    }
