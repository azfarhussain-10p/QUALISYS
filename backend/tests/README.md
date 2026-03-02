# QUALISYS Backend Tests

Test suite for the QUALISYS FastAPI backend. 400+ tests across four suites: unit, integration, security, and pattern contracts.

## Running Tests

```bash
# All tests
python -m pytest tests/ -v

# Specific suite
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/security/ -v
python -m pytest tests/patterns/ -v

# Single file
python -m pytest tests/unit/services/test_artifact_service.py -v

# With coverage
python -m pytest tests/ --cov=src --cov-report=term-missing
```

> **pytest config:** `asyncio_mode = "auto"` is set in `pyproject.toml` — all async tests work without any decorator.

---

## Test Suites

### `unit/` — Pure Unit Tests

No database, no Redis, no network. All external dependencies are mocked.

```
unit/
├── services/
│   ├── test_artifact_service.py
│   ├── test_agent_run_service.py
│   ├── test_audit_service.py
│   ├── test_document_service.py
│   ├── test_dom_crawler_service.py
│   ├── test_embedding_service.py
│   ├── test_github_connector_service.py
│   ├── test_orchestrator.py
│   ├── test_pm_dashboard_service.py
│   ├── test_project_service.py
│   ├── test_source_code_analyzer_service.py
│   ├── test_sse_manager.py
│   └── test_token_budget_service.py
├── test_analytics_service.py
├── test_auth_service.py
├── test_backup_code_service.py
├── test_export_service.py
├── test_invitation_service.py
├── test_org_deletion_service.py
├── test_profile_service.py
├── test_token_service.py
├── test_totp_service.py
└── ...
```

### `integration/` — API Endpoint Tests

Tests FastAPI routes end-to-end using `httpx.AsyncClient` with the full app. All database and Redis calls are mocked via dependency overrides — no real DB or Redis required.

```
integration/
├── test_agent_pipeline.py
├── test_agent_runs.py
├── test_artifacts.py
├── test_auth_login.py
├── test_auth_register.py
├── test_crawls.py
├── test_dashboard.py
├── test_documents.py
├── test_github_connections.py
├── test_invitations.py
├── test_members.py
├── test_mfa.py
├── test_orgs.py
├── test_projects.py
├── test_sse_events.py
├── test_users.py
└── ...
```

### `security/` — RBAC and Tenant Isolation

Verifies that role-based access control and multi-tenant schema isolation work correctly. Tests unauthorised access attempts, privilege escalation, and cross-tenant data leakage.

### `patterns/` — Pattern Contract Tests

Validates the four integration pattern contracts in `src/patterns/`. These tests assert wire format, error handling, and interface compliance.

```
patterns/
├── test_llm_pattern.py
├── test_pgvector_pattern.py
├── test_sse_pattern.py
└── test_playwright_pattern.py
```

---

## Key Mocking Conventions

### Auth Session (`conftest.py`)

```python
# Standard pattern used across integration tests
_setup_auth_session(user_id, tenant_id, role)
# Returns a mock AsyncSession pre-configured for the given user/tenant/role
```

### Database Dependency Override

```python
# Override get_db for tests
app.dependency_overrides[get_db] = lambda: mock_async_session
```

### Redis

```python
# Patch both locations
with patch("src.cache.get_redis_client") as mock_redis, \
     patch("src.middleware.rate_limit.get_redis_client") as mock_rate_redis:
    mock_redis.return_value = AsyncMock()
    ...
```

### Background Tasks

```python
# Capture FastAPI background tasks without running them
with patch("fastapi.BackgroundTasks.add_task") as mock_bg:
    response = await client.post(...)
    mock_bg.assert_called_once_with(my_task_fn, ...)
```

### Git Module (for GitHub connector tests)

```python
# gitpython may not be installed in test env — mock at import level
import sys
sys.modules['git'] = MagicMock()
```

---

## Test File Naming

| Suite | Convention | Example |
|-------|-----------|---------|
| Unit — service | `test_{service_name}.py` | `test_artifact_service.py` |
| Integration — endpoint | `test_{domain}.py` | `test_artifacts.py` |
| Security | `test_{concern}.py` | `test_tenant_context.py` |
| Pattern | `test_{pattern_name}_pattern.py` | `test_llm_pattern.py` |

---

## Related Documentation

- [Backend README](../README.md) — Full backend setup guide
- [Integration Patterns](../src/patterns/README.md) — Pattern contracts tested by `patterns/`
- [Test Design System](../../../docs/planning/test-design-system.md) — Test strategy and quality framework
