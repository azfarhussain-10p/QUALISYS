# QUALISYS Backend

Python FastAPI backend powering the QUALISYS AI System Quality Assurance Platform. Handles all business logic, AI agent orchestration, multi-tenant data isolation, authentication, and real-time SSE streaming.

## Tech Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Runtime |
| FastAPI | 0.115+ | REST API framework + OpenAPI docs |
| SQLAlchemy | 2.x (async) | ORM with asyncpg driver |
| Alembic | 1.x | Database migrations |
| PostgreSQL | 15+ with pgvector | Multi-tenant database (schema-per-tenant) |
| Redis | 7+ | Caching, sessions, rate limiting, SSE queues |
| Pydantic | 2.x | Request/response schema validation |
| pytest | 8.x | Test runner (asyncio_mode = auto) |

## Prerequisites

- Python 3.11+
- PostgreSQL 15+ with the `pgvector` extension enabled
- Redis 7+
- Podman Desktop (Docker Desktop is **not approved** on 10Pearls systems)

## Setup

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate      # macOS/Linux
.venv\Scripts\activate         # Windows

# 2. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt   # dev/test tools

# 3. Configure environment variables
cp ../.env.example ../.env
# Edit .env — set DATABASE_URL, REDIS_URL, SECRET_KEY, etc.

# 4. Apply database migrations
alembic upgrade head

# 5. Start the development server
uvicorn src.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`.
Interactive API docs (Swagger UI): `http://localhost:8000/docs`
OpenAPI JSON: `http://localhost:8000/openapi.json`

## Running with Podman Compose

From the project root:

```bash
podman-compose up -d           # Start all services (API, DB, Redis, web, mail)
podman-compose exec api alembic upgrade head   # Apply migrations
podman-compose logs -f api     # Tail API logs
podman-compose down            # Stop all services
```

## Project Structure

```
backend/
├── src/
│   ├── main.py                 # FastAPI app factory, middleware registration
│   ├── config.py               # Settings (pydantic-settings, env vars)
│   ├── cache.py                # Redis client singleton
│   ├── api/
│   │   └── v1/                 # Versioned REST routers
│   │       ├── admin/          # Analytics, audit logs (Owner/Admin)
│   │       ├── agent_runs/     # AI agent run management
│   │       ├── artifacts/      # Test artifact CRUD + versioning
│   │       ├── auth/           # Login, register, OAuth, sessions
│   │       ├── crawls/         # DOM crawl sessions
│   │       ├── dashboard/      # PM/CSM project health + coverage metrics
│   │       ├── documents/      # Document upload + parsing
│   │       ├── events/         # SSE streaming endpoint
│   │       ├── github/         # GitHub repository connections
│   │       ├── invitations/    # Organisation invitations
│   │       ├── members/        # Organisation member management
│   │       ├── orgs/           # Organisation CRUD + export + deletion
│   │       ├── projects/       # Project CRUD + archive/restore
│   │       └── users/          # User profile management
│   ├── middleware/
│   │   ├── rbac.py             # require_role() / require_project_role() guards
│   │   ├── rate_limit.py       # Redis-backed rate limiting (Lua atomic scripts)
│   │   └── tenant_context.py   # TenantContextMiddleware + ContextVar
│   ├── models/                 # SQLAlchemy ORM models (public schema)
│   ├── patterns/               # Canonical integration patterns — see patterns/README.md
│   ├── services/               # Business logic layer
│   │   ├── agents/             # AI agents (BAConsultant, QAConsultant, AutomationConsultant, Orchestrator)
│   │   ├── artifact_service.py
│   │   ├── agent_run_service.py
│   │   ├── audit_service.py
│   │   ├── document_service.py
│   │   ├── dom_crawler_service.py
│   │   ├── embedding_service.py
│   │   ├── export_service.py
│   │   ├── github_connector_service.py
│   │   ├── pm_dashboard_service.py
│   │   ├── project_service.py
│   │   ├── sse_manager.py
│   │   ├── token_budget_service.py
│   │   └── ... (auth, invitation, notification, profile, etc.)
│   └── templates/email/        # 7 Jinja2 email templates
├── alembic/
│   ├── versions/               # 15 migration files (001–015)
│   └── env.py
├── tests/                      # See tests/README.md
│   ├── unit/                   # Pure unit tests (no DB, no Redis)
│   ├── integration/            # API endpoint tests (mocked DB/Redis)
│   ├── security/               # RBAC and tenant isolation tests
│   └── patterns/               # Pattern contract tests
├── pyproject.toml              # pytest config (asyncio_mode = auto)
├── requirements.txt
└── requirements-dev.txt
```

## Key Architectural Patterns

### Multi-Tenant Isolation

Every tenant has its own PostgreSQL schema (`tenant_{slug}`). The `TenantContextMiddleware` reads the JWT and sets a `ContextVar` that all services consume:

```python
# In any service
schema_name = slug_to_schema_name(current_tenant_slug.get())
await db.execute(text(f'SELECT * FROM "{schema_name}".table WHERE ...'))
```

### RBAC

```python
# Organisation-level (uses org_id path param)
user, tenant_user = await require_role("owner", "admin")(...)

# Project-level (reads tenant_id from JWT)
user, tenant_user = await require_project_role("owner", "admin", "qa-automation")(...)
```

### Rate Limiting

Atomic Redis Lua script pattern — INCR + conditional EXPIRE in a single round trip. Keys follow `rate:{action}:{entity_id}`.

### SSE Pattern

Agent runs stream progress events via `SSEManager` (asyncio Queue registry). Consumers connect to `GET /api/v1/events/agent-runs/{run_id}`. See [`src/patterns/README.md`](./src/patterns/README.md).

## Running Tests

See [`tests/README.md`](./tests/README.md) for the full guide.

```bash
# Quick: all tests
python -m pytest tests/ -v

# By suite
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/security/ -v
python -m pytest tests/patterns/ -v
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Async PostgreSQL DSN | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection URL | `redis://localhost:6379` |
| `SECRET_KEY` | JWT signing key (RS256 private key path or inline) | — |
| `OPENAI_API_KEY` | OpenAI API key for AI agents | — |
| `ANTHROPIC_API_KEY` | Anthropic fallback LLM key | — |
| `GITHUB_TOKEN_ENCRYPTION_KEY` | Fernet key for PAT encryption | dev default |
| `ENVIRONMENT` | `development` / `staging` / `production` | `development` |

## API Documentation

Full OpenAPI specification is auto-generated at runtime:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Related Documentation

- [Integration Patterns](./src/patterns/README.md) — LLM, pgvector, SSE, Playwright contracts
- [Test Guide](./tests/README.md) — How to run and write tests
- [System Architecture](../docs/architecture/architecture.md) — Full technical design
- [Epic 2 Tech Spec](../docs/stories/epic-2/tech-spec-epic-2.md) — AI Agent Platform specification
- [Database Migrations](./alembic/versions/) — 15 applied migrations
