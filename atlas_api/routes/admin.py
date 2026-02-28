"""Admin routes for cross-tenant operations and monitoring."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Header
from atlas_api.db import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/cross-org-stats")
async def get_cross_org_stats(
    admin_secret: str = Header(..., description="Secret to verify admin status"),
    conn = Depends(get_db_connection)
):
    """Aggregate statistics across all tenants for the admin dashboard."""
    # In a real app we'd verify admin_secret via auth.require_role
    if admin_secret != "pipelineatlas-admin-secret":
        raise HTTPException(status_code=403, detail="Forbidden")

    try:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                SELECT 
                    t.name as tenant_name,
                    t.plan_tier as plan,
                    COALESCE(tu.scans_count, 0) as scans,
                    COALESCE(tu.token_count, 0) as tokens
                FROM tenants t
                LEFT JOIN tenant_usage tu ON t.id = tu.tenant_id
                ORDER BY tu.scans_count DESC NULLS LAST
                LIMIT 50
                """
            )
            rows = await cur.fetchall()

        return {"tenants": [
            {"name": r[0], "plan": r[1], "scans": r[2], "tokens": r[3]}
            for r in rows
        ]}
    except Exception as e:
        logger.error("Failed to fetch cross-org stats: %s", e)
        raise HTTPException(status_code=500, detail="Database query failed")
