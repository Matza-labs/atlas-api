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
                CREATE TABLE IF NOT EXISTS cicd_graphs (
                    id         TEXT PRIMARY KEY,
                    name       TEXT NOT NULL,
                    platform   TEXT,
                    data       JSONB NOT NULL DEFAULT '{}',
                    tenant_id  TEXT NOT NULL DEFAULT 'default',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS webhook_events (
                    id           TEXT PRIMARY KEY,
                    platform     TEXT NOT NULL,
                    event_type   TEXT NOT NULL,
                    repository   TEXT,
                    ref          TEXT,
                    sender       TEXT,
                    action       TEXT,
                    received_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS tenants (
                    id                 TEXT PRIMARY KEY,
                    name               TEXT NOT NULL,
                    plan_tier          TEXT NOT NULL DEFAULT 'free',
                    stripe_customer_id TEXT,
                    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                
                CREATE TABLE IF NOT EXISTS tenant_usage (
                    tenant_id    TEXT PRIMARY KEY REFERENCES tenants(id),
                    scans_count  INTEGER NOT NULL DEFAULT 0,
                    token_count  INTEGER NOT NULL DEFAULT 0,
                    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS proposals (
                    id               TEXT PRIMARY KEY,
                    graph_id         TEXT NOT NULL,
                    plan_id          TEXT NOT NULL,
                    title            TEXT NOT NULL,
                    description      TEXT NOT NULL DEFAULT '',
                    author           TEXT NOT NULL DEFAULT '',
                    status           TEXT NOT NULL DEFAULT 'draft',
                    suggestion_count INTEGER NOT NULL DEFAULT 0,
                    diff_preview     TEXT NOT NULL DEFAULT '',
                    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS proposal_comments (
                    id          SERIAL PRIMARY KEY,
                    proposal_id TEXT NOT NULL REFERENCES proposals(id),
                    author      TEXT NOT NULL DEFAULT 'system',
                    text        TEXT NOT NULL DEFAULT '',
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS snapshots (
                    id               TEXT PRIMARY KEY,
                    graph_name       TEXT NOT NULL,
                    graph_id         TEXT NOT NULL DEFAULT '',
                    complexity_score DOUBLE PRECISION NOT NULL DEFAULT 0,
                    fragility_score  DOUBLE PRECISION NOT NULL DEFAULT 0,
                    maturity_score   DOUBLE PRECISION NOT NULL DEFAULT 0,
                    finding_count    INTEGER NOT NULL DEFAULT 0,
                    node_count       INTEGER NOT NULL DEFAULT 0,
                    edge_count       INTEGER NOT NULL DEFAULT 0,
                    scanned_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS api_keys (
                    key       TEXT PRIMARY KEY,
                    user_id   TEXT NOT NULL,
                    username  TEXT NOT NULL,
                    role      TEXT NOT NULL DEFAULT 'viewer'
                );
                """
            )
        await conn.commit()
    logger.info("Database tables verified/created")
