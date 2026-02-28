"""
QUALISYS — Agent Runs Router
Stories: 2-6-ai-agent-selection-ui, 2-7-agent-pipeline-orchestration

Endpoints:
  GET  /api/v1/agents                                     — List available agent definitions (no auth)
  POST /api/v1/projects/{project_id}/agent-runs           — Create + queue pipeline run (201)
  GET  /api/v1/projects/{project_id}/agent-runs           — List runs (latest 20)
  GET  /api/v1/projects/{project_id}/agent-runs/{run_id}  — Run detail with steps

RBAC: require_project_role("owner", "admin", "qa-automation") on all project-scoped endpoints.
GET /api/v1/agents: no auth — static catalog data.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db import get_db
from src.middleware.rbac import require_project_role
from src.middleware.tenant_context import current_tenant_slug
from src.patterns.llm_pattern import BudgetExceededError
from src.services.agent_run_service import agent_run_service
from src.services.agents.orchestrator import execute_pipeline
from src.services.tenant_provisioning import slug_to_schema_name
from src.services.token_budget_service import token_budget_service


# ---------------------------------------------------------------------------
# Two routers: global (no prefix) + project-scoped
# ---------------------------------------------------------------------------

# Global catalog endpoint — no project_id, no auth required
agents_catalog_router = APIRouter(tags=["Agent Runs"])

# Project-scoped endpoints
router = APIRouter(
    prefix="/api/v1/projects/{project_id}/agent-runs",
    tags=["Agent Runs"],
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class StartRunRequest(BaseModel):
    agents_selected: list[str]
    pipeline_mode:   str = "sequential"


class AgentRunStepResponse(BaseModel):
    id:             str
    run_id:         str
    agent_type:     str
    status:         str
    progress_pct:   int = 0
    progress_label: Optional[str] = None
    tokens_used:    int = 0
    started_at:     Optional[datetime] = None
    completed_at:   Optional[datetime] = None
    error_message:  Optional[str] = None

    model_config = {"from_attributes": True}


class AgentRunResponse(BaseModel):
    id:              str
    project_id:      str
    pipeline_mode:   str
    agents_selected: list[str]   # Fixed F-3: was Any
    status:          str
    total_tokens:    int = 0
    total_cost_usd:  float = 0.0
    started_at:      Optional[datetime] = None
    completed_at:    Optional[datetime] = None
    error_message:   Optional[str] = None
    created_at:      Optional[datetime] = None
    steps:           Optional[list[AgentRunStepResponse]] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _check_has_data_sources(
    db:          AsyncSession,
    schema_name: str,
    project_id:  str,
) -> None:
    """
    AC-17a: Verify at least one ready data source exists for the project.
    Checks documents (parse_status='completed'), github_connections (status='cloned'),
    and crawl_sessions (status='completed') in order.
    Raises 400 NO_DATA_SOURCES if none found.
    """
    # Check documents
    result = await db.execute(
        text(
            f'SELECT 1 FROM "{schema_name}".documents '
            f"WHERE project_id = :pid AND parse_status = 'completed' LIMIT 1"
        ),
        {"pid": project_id},
    )
    if result.scalar_one_or_none():
        return

    # Check GitHub connections
    result = await db.execute(
        text(
            f'SELECT 1 FROM "{schema_name}".github_connections '
            f"WHERE project_id = :pid AND status = 'cloned' LIMIT 1"
        ),
        {"pid": project_id},
    )
    if result.scalar_one_or_none():
        return

    # Check crawl sessions
    result = await db.execute(
        text(
            f'SELECT 1 FROM "{schema_name}".crawl_sessions '
            f"WHERE project_id = :pid AND status = 'completed' LIMIT 1"
        ),
        {"pid": project_id},
    )
    if result.scalar_one_or_none():
        return

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "error":   "NO_DATA_SOURCES",
            "message": (
                "No ready data sources found for this project. "
                "Upload and parse documents, connect a GitHub repository, "
                "or complete a DOM crawl before running agents."
            ),
        },
    )


# ---------------------------------------------------------------------------
# GET /api/v1/agents  — static catalog, no auth
# ---------------------------------------------------------------------------

@agents_catalog_router.get("/api/v1/agents")
async def list_agents_endpoint():
    """Return the 3 MVP agent definitions. No authentication required."""
    return agent_run_service.list_agents()


# ---------------------------------------------------------------------------
# POST /api/v1/projects/{project_id}/agent-runs
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED, response_model=AgentRunResponse)
async def start_run_endpoint(
    project_id:        uuid.UUID,
    body:              StartRunRequest,
    background_tasks:  BackgroundTasks,
    auth:              tuple = require_project_role("owner", "admin", "qa-automation"),
    db:                AsyncSession = Depends(get_db),
):
    """
    Create and queue an agent pipeline run for the project.

    AC-17a: Validates at least one ready data source exists (docs/github/crawl).
    AC-17b: Dispatches execute_pipeline as a BackgroundTask after INSERT; returns 201 immediately.
    """
    user, membership = auth
    schema_name = slug_to_schema_name(current_tenant_slug.get())
    tenant_id   = str(membership.tenant_id)

    # AC-17a: must have at least one ready data source
    await _check_has_data_sources(db, schema_name, str(project_id))

    # AC-17: reject if monthly token budget exhausted
    try:
        settings = get_settings()
        await token_budget_service.check_budget(tenant_id, settings.monthly_token_budget)
    except BudgetExceededError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error":   "BUDGET_EXCEEDED",
                "message": "Monthly token budget exceeded. Contact your admin.",
            },
        )

    run = await agent_run_service.create_run(
        db=db,
        schema_name=schema_name,
        project_id=str(project_id),
        user_id=str(user.id),
        agents_selected=body.agents_selected,
        pipeline_mode=body.pipeline_mode,
    )

    # AC-17b: dispatch background orchestration; HTTP 201 returned immediately
    background_tasks.add_task(
        execute_pipeline,
        run["id"],
        schema_name,
        str(project_id),
        tenant_id,
        str(user.id),
    )

    return run


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/agent-runs
# ---------------------------------------------------------------------------

@router.get("", response_model=list[AgentRunResponse])
async def list_runs_endpoint(
    project_id: uuid.UUID,
    auth:       tuple = require_project_role("owner", "admin", "qa-automation"),
    db:         AsyncSession = Depends(get_db),
):
    """List agent runs for the project (latest 20, newest first)."""
    schema_name = slug_to_schema_name(current_tenant_slug.get())

    runs = await agent_run_service.list_runs(
        db=db,
        schema_name=schema_name,
        project_id=str(project_id),
    )
    return runs


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/agent-runs/{run_id}
# ---------------------------------------------------------------------------

@router.get("/{run_id}", response_model=AgentRunResponse)
async def get_run_endpoint(
    project_id: uuid.UUID,
    run_id:     uuid.UUID,
    auth:       tuple = require_project_role("owner", "admin", "qa-automation"),
    db:         AsyncSession = Depends(get_db),
):
    """Return a single agent run with its per-agent steps. Raises 404 if not found."""
    schema_name = slug_to_schema_name(current_tenant_slug.get())

    run = await agent_run_service.get_run(
        db=db,
        schema_name=schema_name,
        project_id=str(project_id),
        run_id=str(run_id),
    )
    return run
