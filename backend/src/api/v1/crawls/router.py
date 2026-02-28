"""
QUALISYS — DOM Crawl Router
Story: 2-5-application-dom-crawling

Endpoints (mounted under /api/v1/projects/{project_id}):
  POST   /crawls          — Start Playwright DOM crawl (201 | 409 CRAWL_ALREADY_ACTIVE)
  GET    /crawls          — List crawl sessions (latest 50)
  GET    /crawls/{id}     — Crawl session detail (200 | 404 CRAWL_NOT_FOUND)

RBAC: require_project_role("owner", "admin", "qa-automation") on all endpoints (C10).
Security: auth_config (credentials) never returned in responses (C7).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.logger import logger
from src.middleware.rbac import require_project_role
from src.middleware.tenant_context import current_tenant_slug
from src.services.dom_crawler_service import _encrypt_password, crawl_task, dom_crawler_service
from src.services.tenant_provisioning import slug_to_schema_name

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/crawls",
    tags=["DOM Crawling"],
)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class StartCrawlAuthConfig(BaseModel):
    login_url:          str
    username_selector:  str
    password_selector:  str
    submit_selector:    str
    username:           str
    password:           str
    post_login_url:     Optional[str] = None


class StartCrawlRequest(BaseModel):
    target_url:  str
    auth_config: Optional[StartCrawlAuthConfig] = None


class CrawlSessionResponse(BaseModel):
    id:             str
    project_id:     str
    target_url:     str
    status:         str
    pages_crawled:  int = 0
    forms_found:    int = 0
    links_found:    int = 0
    crawl_data:     Optional[Any] = None
    error_message:  Optional[str] = None
    started_at:     Optional[datetime] = None
    completed_at:   Optional[datetime] = None
    created_at:     Optional[datetime] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# POST /api/v1/projects/{project_id}/crawls
# ---------------------------------------------------------------------------

@router.post("", status_code=status.HTTP_201_CREATED, response_model=CrawlSessionResponse)
async def start_crawl_endpoint(
    project_id:       uuid.UUID,
    body:             StartCrawlRequest,
    background_tasks: BackgroundTasks,
    auth:             tuple = require_project_role("owner", "admin", "qa-automation"),
    db:               AsyncSession = Depends(get_db),
):
    """Start a Playwright DOM crawl for the project. Queues background crawl_task."""
    user, membership = auth
    schema_name = slug_to_schema_name(current_tenant_slug.get())
    tenant_id   = str(membership.tenant_id)

    # Pre-process auth_config: encrypt password before passing to service + task.
    # Both start_crawl (for DB storage) and crawl_task receive the same
    # already-processed dict (password key removed, password_encrypted added).
    auth_config_db = None
    if body.auth_config:
        auth_config_db = body.auth_config.model_dump()
        if auth_config_db.get("password"):
            auth_config_db["password_encrypted"] = _encrypt_password(
                auth_config_db.pop("password")
            )

    session = await dom_crawler_service.start_crawl(
        db=db,
        schema_name=schema_name,
        project_id=str(project_id),
        user_id=str(user.id),
        target_url=body.target_url,
        auth_config=auth_config_db,
    )

    background_tasks.add_task(
        crawl_task,
        crawl_id=session["id"],
        schema_name=schema_name,
        tenant_id=tenant_id,
        target_url=body.target_url,
        auth_config_db=auth_config_db,
    )

    logger.info(
        "crawl: task scheduled",
        crawl_id=session["id"],
        project_id=str(project_id),
    )
    return session


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/crawls
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CrawlSessionResponse])
async def list_crawls_endpoint(
    project_id: uuid.UUID,
    auth:       tuple = require_project_role("owner", "admin", "qa-automation"),
    db:         AsyncSession = Depends(get_db),
):
    """List crawl sessions for the project (latest 50, no credentials returned)."""
    schema_name = slug_to_schema_name(current_tenant_slug.get())

    sessions = await dom_crawler_service.list_crawls(
        db=db,
        schema_name=schema_name,
        project_id=str(project_id),
    )
    return sessions


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/crawls/{crawl_id}
# ---------------------------------------------------------------------------

@router.get("/{crawl_id}", response_model=CrawlSessionResponse)
async def get_crawl_endpoint(
    project_id: uuid.UUID,
    crawl_id:   uuid.UUID,
    auth:       tuple = require_project_role("owner", "admin", "qa-automation"),
    db:         AsyncSession = Depends(get_db),
):
    """Return a single crawl session detail. Raises 404 if not found."""
    schema_name = slug_to_schema_name(current_tenant_slug.get())

    session = await dom_crawler_service.get_crawl(
        db=db,
        schema_name=schema_name,
        project_id=str(project_id),
        crawl_id=str(crawl_id),
    )
    return session
