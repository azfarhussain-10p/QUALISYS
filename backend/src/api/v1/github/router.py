"""
QUALISYS — GitHub Connection Router
Story: 2-3-github-repository-connection
AC: #9 — POST /github: validates PAT, 400 INVALID_TOKEN on failure
AC: #10 — POST /github: queues clone_repo_task (background), 7-day expiry

Endpoints (mounted under /api/v1/projects/{project_id}):
  POST   /github   — Connect GitHub repo (PAT + repo_url)
  GET    /github   — Connection status + analysis summary
  DELETE /github   — Disconnect (delete connection + clean clone dir)
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.github.schemas import GitHubConnectRequest, GitHubConnectionResponse
from src.db import get_db
from src.logger import logger
from src.middleware.rbac import require_project_role
from src.middleware.tenant_context import current_tenant_slug
from src.services.github_connector_service import (
    clone_repo_task,
    github_connector_service,
)
from src.services.tenant_provisioning import slug_to_schema_name

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/github",
    tags=["github"],
)


# ---------------------------------------------------------------------------
# POST /api/v1/projects/{project_id}/github
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED, response_model=GitHubConnectionResponse)
async def connect_github_repo(
    project_id:       uuid.UUID,
    body:             GitHubConnectRequest,
    background_tasks: BackgroundTasks,
    auth:             tuple = require_project_role("owner", "admin", "qa-automation"),
    db:               AsyncSession = Depends(get_db),
):
    """Connect a GitHub repository to the project. Validates PAT and queues clone."""
    user, membership = auth
    schema_name = slug_to_schema_name(current_tenant_slug.get())

    connection = await github_connector_service.connect_repo(
        db=db,
        schema_name=schema_name,
        project_id=str(project_id),
        user_id=str(user.id),
        repo_url=body.repo_url,
        pat=body.pat,
    )

    # AC-10: Schedule background clone
    background_tasks.add_task(
        clone_repo_task,
        connection_id=connection["id"],
        schema_name=schema_name,
        tenant_id=str(membership.tenant_id),
        repo_url=body.repo_url,
        pat=body.pat,
    )

    logger.info(
        "github: clone task scheduled",
        connection_id=connection["id"],
        project_id=str(project_id),
    )
    return connection


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/github
# ---------------------------------------------------------------------------

@router.get("", response_model=GitHubConnectionResponse)
async def get_github_connection(
    project_id: uuid.UUID,
    auth:       tuple = require_project_role("owner", "admin", "qa-automation"),
    db:         AsyncSession = Depends(get_db),
):
    """Return the current GitHub connection status for the project."""
    schema_name = slug_to_schema_name(current_tenant_slug.get())

    connection = await github_connector_service.get_connection(
        db=db,
        schema_name=schema_name,
        project_id=str(project_id),
    )
    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "CONNECTION_NOT_FOUND", "message": "No GitHub connection found for this project."},
        )
    return connection


# ---------------------------------------------------------------------------
# DELETE /api/v1/projects/{project_id}/github
# ---------------------------------------------------------------------------

@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect_github_repo(
    project_id: uuid.UUID,
    auth:       tuple = require_project_role("owner", "admin", "qa-automation"),
    db:         AsyncSession = Depends(get_db),
):
    """Disconnect GitHub repo, delete the connection row and clone directory."""
    schema_name = slug_to_schema_name(current_tenant_slug.get())

    await github_connector_service.disconnect(
        db=db,
        schema_name=schema_name,
        project_id=str(project_id),
    )
