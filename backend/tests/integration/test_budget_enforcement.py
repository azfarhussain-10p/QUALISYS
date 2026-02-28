"""
Integration tests — Budget enforcement and LLM cache (Story 2-8)
AC-17: POST /agent-runs returns 429 BUDGET_EXCEEDED when monthly limit exhausted.
AC-18: call_llm() with context_hash hits Redis cache and skips LLM API.

DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.

Tests mock:
  - DB session (get_db override)
  - Redis (src.cache.get_redis_client + src.middleware.rate_limit.get_redis_client)
  - token_budget_service.check_budget (service-level for AC-17 HTTP tests)
  - _call_openai / _call_anthropic (for AC-18 cache hit test)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.db import get_db
from src.main import app
from src.patterns.llm_pattern import BudgetExceededError, LLMResult, call_llm
from src.services.token_service import token_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TENANT_ID    = str(uuid.uuid4())
DAILY_BUDGET = 100_000
AGENT_TYPE   = "qa_consultant"
PROMPT       = "List test cases for the login flow."


def _make_token(user_id: uuid.UUID, tenant_id: uuid.UUID, role: str = "owner") -> str:
    return token_service.create_access_token(
        user_id=user_id,
        email=f"{role}@test.com",
        tenant_id=tenant_id,
        role=role,
        tenant_slug="test-org",
    )


def _make_redis_mock():
    """Minimal Redis mock for auth/rate-limit middleware."""
    mock = MagicMock()
    pipeline = MagicMock()
    pipeline.incr    = MagicMock(return_value=pipeline)
    pipeline.expire  = MagicMock(return_value=pipeline)
    pipeline.ttl     = MagicMock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[1, 3600])
    mock.pipeline.return_value = pipeline
    mock.incr   = AsyncMock(return_value=1)
    mock.expire = AsyncMock(return_value=True)
    mock.get    = AsyncMock(return_value=None)
    mock.set    = AsyncMock(return_value=True)
    mock.eval   = AsyncMock(return_value=[100, 2592000])
    return mock


def _setup_db_session(
    user_id:    uuid.UUID,
    tenant_id:  uuid.UUID,
    project_id: uuid.UUID,
    role:       str = "owner",
):
    """Mock DB session providing auth + data-source check (passes by default)."""
    from src.models.user import User
    from src.models.tenant import Tenant, TenantUser

    mock_user              = MagicMock(spec=User)
    mock_user.id           = user_id
    mock_user.email        = f"{role}@test.com"

    mock_tenant            = MagicMock(spec=Tenant)
    mock_tenant.id         = tenant_id
    mock_tenant.slug       = "test-org"

    mock_membership             = MagicMock(spec=TenantUser)
    mock_membership.role        = role
    mock_membership.is_active   = True
    mock_membership.tenant_id   = tenant_id
    mock_membership.user_id     = user_id

    mock_session         = AsyncMock()
    mock_session.commit  = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        result   = MagicMock()
        mappings = MagicMock()
        s        = str(stmt).lower()

        if "public.tenants_users" in s:
            result.scalar_one_or_none.return_value = mock_membership
        elif "public.users" in s and "public.tenants" not in s:
            result.scalar_one_or_none.return_value = mock_user
        elif "public.tenants" in s:
            result.scalar_one_or_none.return_value = mock_tenant
        elif "insert" in s and ("agent_runs" in s or "agent_run_steps" in s):
            result.rowcount = 1
        else:
            # _check_has_data_sources: SELECT 1 FROM ... — return truthy so check passes
            result.scalar_one_or_none.return_value = mock_membership

        return result

    mock_session.execute = mock_execute

    async def get_db_override():
        yield mock_session

    return get_db_override


# ---------------------------------------------------------------------------
# AC-17 integration tests
# ---------------------------------------------------------------------------

class TestBudgetEnforcementEndpoint:

    @pytest.mark.asyncio
    async def test_post_agent_runs_budget_exceeded_returns_429(self):
        # Proves: when check_budget raises BudgetExceededError, POST /agent-runs → 429 BUDGET_EXCEEDED.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id)
        app.dependency_overrides[get_db] = get_db_override

        exc = BudgetExceededError(str(tenant_id), 100_000, 100_000)

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()), \
                 patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()), \
                 patch(
                     "src.api.v1.agent_runs.router.token_budget_service.check_budget",
                     new_callable=AsyncMock,
                     side_effect=exc,
                 ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.post(
                        f"/api/v1/projects/{project_id}/agent-runs",
                        json={"agents_selected": ["qa_consultant"]},
                        headers={"Authorization": f"Bearer {token}"},
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 429
        detail = resp.json()["detail"]
        assert detail["error"] == "BUDGET_EXCEEDED"
        assert "Monthly token budget exceeded" in detail["message"]

    @pytest.mark.asyncio
    async def test_post_agent_runs_within_budget_returns_201(self):
        # Proves: when check_budget passes (no exception), POST /agent-runs → 201 with queued run.
        user_id    = uuid.uuid4()
        tenant_id  = uuid.uuid4()
        project_id = uuid.uuid4()
        run_id     = uuid.uuid4()
        token      = _make_token(user_id, tenant_id, "owner")

        get_db_override = _setup_db_session(user_id, tenant_id, project_id)
        app.dependency_overrides[get_db] = get_db_override

        dummy_run = {
            "id":              str(run_id),
            "project_id":      str(project_id),
            "pipeline_mode":   "sequential",
            "agents_selected": ["qa_consultant"],
            "status":          "queued",
            "total_tokens":    0,
            "total_cost_usd":  0.0,
            "started_at":      None,
            "completed_at":    None,
            "error_message":   None,
            "created_at":      datetime.now(timezone.utc).isoformat(),
            "steps":           None,
        }

        try:
            with patch("src.cache.get_redis_client", return_value=_make_redis_mock()), \
                 patch("src.middleware.rate_limit.get_redis_client", return_value=_make_redis_mock()), \
                 patch(
                     "src.api.v1.agent_runs.router.token_budget_service.check_budget",
                     new_callable=AsyncMock,
                     return_value=None,
                 ), \
                 patch(
                     "src.api.v1.agent_runs.router.agent_run_service.create_run",
                     new_callable=AsyncMock,
                     return_value=dummy_run,
                 ), \
                 patch(
                     "src.api.v1.agent_runs.router.execute_pipeline",
                     new_callable=AsyncMock,
                 ):
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    resp = await c.post(
                        f"/api/v1/projects/{project_id}/agent-runs",
                        json={"agents_selected": ["qa_consultant"]},
                        headers={"Authorization": f"Bearer {token}"},
                    )
        finally:
            app.dependency_overrides.pop(get_db, None)

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "queued"
        assert data["id"] == str(run_id)


# ---------------------------------------------------------------------------
# AC-18 integration test — cache hit with context_hash
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_context_hash_hit_skips_llm():
    # Proves: call_llm() with context_hash hits Redis cache and returns without calling LLM API.
    cached_payload = json.dumps({
        "content":     "cached response",
        "tokens_used": 150,
        "cost_usd":    0.0045,
    })

    mock_redis = AsyncMock()
    mock_redis.get.return_value = cached_payload

    with patch("src.cache.get_redis_client", return_value=mock_redis), \
         patch("src.patterns.llm_pattern._call_openai") as mock_openai, \
         patch("src.patterns.llm_pattern._call_anthropic") as mock_anthropic:

        result = await call_llm(
            PROMPT,
            TENANT_ID,
            DAILY_BUDGET,
            AGENT_TYPE,
            context_hash="abc123contexthashhex",
        )

    assert result.cached is True
    assert result.provider == "cache"
    assert result.content == "cached response"
    assert result.tokens_used == 150
    mock_openai.assert_not_called()
    mock_anthropic.assert_not_called()
