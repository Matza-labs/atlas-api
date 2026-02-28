"""Database connection pooling using psycopg."""

import logging
from typing import AsyncGenerator

from psycopg_pool import AsyncConnectionPool

from atlas_api.config import ApiConfig

logger = logging.getLogger(__name__)

# Global pool instance
_pool: AsyncConnectionPool | None = None


def init_db(config: ApiConfig) -> None:
    """Initialize the async connection pool."""
    global _pool
    if _pool is None:
        logger.info("Initializing async connection pool to %s:%d/%s", 
                    config.db_host, config.db_port, config.db_name)
        _pool = AsyncConnectionPool(
            conninfo=config.database_url,
            min_size=config.db_pool_min_size,
            max_size=config.db_pool_max_size,
            open=False, # Wait for async startup
        )


async def get_db_pool() -> AsyncConnectionPool:
    """Get the connection pool instance."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_db() first.")
    return _pool


async def get_db_connection() -> AsyncGenerator:
    """FastAPI dependency to get a single database connection from the pool."""
    pool = await get_db_pool()
    async with pool.connection() as conn:
        yield conn


async def create_tables(pool: AsyncConnectionPool) -> None:
    """Create required database tables if they do not already exist."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS webhook_events (
                    id           TEXT PRIMARY KEY,
                    platform     TEXT NOT NULL,
                    event_type   TEXT NOT NULL,
                    repository   TEXT,
                    ref          TEXT,
                    sender       TEXT,
                    action       TEXT,
                    received_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        await conn.commit()
    logger.info("Database tables verified/created")
