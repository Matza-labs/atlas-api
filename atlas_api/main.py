"""FastAPI entrypoint."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlas_api.config import ApiConfig
from atlas_api.db import init_db, get_db_pool
from atlas_api.routes import graphs, proposals, reports, trends, webhooks, health

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
    
    yield
    
    # Shutdown
    logger.info("Shutting down atlas-api")
    if pool:
        await pool.close()
        logger.info("Database connection pool closed")


app = FastAPI(
    title="PipelineAtlas API",
    description="Control plane for PipelineAtlas CI/CD intelligence.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for the dashboard UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production this should be configured!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(graphs.router, prefix="/api/v1/graphs", tags=["graphs"])
app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(proposals.router)
app.include_router(trends.router)
app.include_router(webhooks.router)

