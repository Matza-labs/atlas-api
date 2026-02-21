# atlas-api

Control Plane API for **PipelineAtlas** — FastAPI multi-tenant management.

## Purpose

Provides REST API for the web dashboard, multi-tenant management, report serving, and user authentication.

## Status: 🟡 Phase 2

This service is planned for Phase 2. The directory structure is scaffolded and ready.

## Planned Features

- FastAPI REST API
- Multi-tenant management
- User authentication (JWT)
- Report serving
- Graph query API
- Billing & usage tracking
- AI cost monitoring

## Dependencies

- `atlas-sdk` (shared models)
- `fastapi` + `uvicorn`
- `psycopg[binary]` (PostgreSQL)
- `redis` (caching)

## Related Services

Receives from ← `atlas-report`
Serves → `atlas-ui`
