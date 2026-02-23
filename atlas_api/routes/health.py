"""Health check endpoints."""

from fastapi import APIRouter, Depends
from psycopg_pool import AsyncConnectionPool

from atlas_api.db import get_db_pool

router = APIRouter()


@router.get("/health")
async def health_check(pool: AsyncConnectionPool = Depends(get_db_pool)):
    """Basic health check and database connectivity test."""
    try:
        async with pool.connection() as conn:
            await conn.execute("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "up" if db_status == "ok" else "degraded",
        "database": db_status,
        "service": "atlas-api",
    }
