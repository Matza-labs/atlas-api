# atlas-api ✅ Complete

Control Plane API for **PipelineAtlas** — FastAPI multi-tenant REST API.

## Purpose

Provides REST endpoints for the web dashboard (`atlas-ui`), multi-tenant management, authentication, graph queries, report serving, proposal CRUD, and score trend tracking.

## Running

```bash
# Docker (recommended)
docker compose up atlas-api

# Local dev
REDIS_URL=redis://localhost:6379 DB_URL=postgresql://postgres:postgres@localhost:5432/pipelineatlas \
  uvicorn atlas_api.main:app --reload
```

## Endpoints

| Method | Path | Description | Role required |
|--------|------|-------------|---------------|
| `GET` | `/health` | Connectivity check | — |
| `GET` | `/api/v1/graphs/` | List all graphs | viewer |
| `GET` | `/api/v1/graphs/{id}` | Get single graph | viewer |
| `GET` | `/api/v1/reports/{graph_id}` | Get report for a graph | viewer |
| `POST` | `/api/v1/proposals` | Create refactor proposal | auditor |
| `GET` | `/api/v1/proposals` | List proposals (filter by status) | viewer |
| `PATCH` | `/api/v1/proposals/{id}` | Approve / reject proposal | auditor |
| `POST` | `/api/v1/proposals/{id}/apply` | Apply approved fixes (Phase 4) | admin |
| `POST` | `/api/v1/snapshots` | Record a trend snapshot | auditor |
| `GET` | `/api/v1/trends/{graph_name}` | Get score trend history | viewer |
| `POST` | `/api/v1/webhooks/github` | GitHub webhook ingestion | — |
| `POST` | `/api/v1/webhooks/gitlab` | GitLab webhook ingestion | — |

## Authentication

All routes (except `/health` and webhooks) require an `Authorization` header:

```
Authorization: Bearer <JWT>
Authorization: ApiKey <key>
```

All multi-tenant routes also require: `X-Tenant-Id: <tenant-id>`

## Database Tables

Auto-created on startup: `cicd_graphs`, `webhook_events`, `tenants`, `tenant_usage`, `proposals`, `proposal_comments`, `snapshots`, `api_keys`

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_URL` | — | PostgreSQL connection URL |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `ATLAS_JWT_SECRET` | dev secret | JWT signing key (required in production) |
| `ATLAS_API_ENVIRONMENT` | `production` | Set to `development` to relax JWT secret check |

## Dependencies

- `atlas-sdk` (shared models)
- `fastapi` + `uvicorn`
- `psycopg[binary]` (async PostgreSQL)
- `redis`
