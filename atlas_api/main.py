"""FastAPI entrypoint."""

import logging
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from atlas_api.config import ApiConfig
from atlas_api.limiter import limiter
from atlas_api.db import init_db, get_db_pool, create_tables
from atlas_api.routes import graphs, proposals, reports, trends, webhooks, health, billing, admin
from atlas_api.worker import run_usage_worker

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

config = ApiConfig()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events for the FastAPI application."""
    # Startup
    logger.info("Starting up atlas-api in %s environment", config.environment)
    init_db(config)
    pool = await get_db_pool()
    await pool.open()
    logger.info("Database connection pool opened")
    await create_tables(pool)
    
    # Start worker
    worker_task = asyncio.create_task(run_usage_worker(config))
    
    yield
    
    # Shutdown
    logger.info("Shutting down atlas-api")
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
        
    if pool:
        await pool.close()
        logger.info("Database connection pool closed")


app = FastAPI(
    title="PipelineAtlas API",
    description="Control plane for PipelineAtlas CI/CD intelligence.",
    version="0.1.0",
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS middleware for the dashboard UI
_cors_origins_raw = config.cors_allowed_origins
_cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()] if _cors_origins_raw else []
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://localhost:3000"],
    allow_credentials=False,  # Never combine allow_credentials=True with wildcard origins
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Tenant-Id"],
)

# Register routers
app.include_router(health.router)
app.include_router(graphs.router, prefix="/api/v1/graphs", tags=["graphs"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(proposals.router)
app.include_router(trends.router)
app.include_router(webhooks.router)
app.include_router(billing.router, prefix="/api/v1/billing", tags=["billing"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])

