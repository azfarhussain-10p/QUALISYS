"""
QUALISYS — Artifact API Router
Story: 2-10-test-artifact-storage-viewer (GET endpoints)
       2-11-artifact-editing-versioning (PUT endpoint, AC-28)
AC-26: GET endpoints for artifact list (with type filter), detail, versions, and specific version.
AC-28: PUT endpoint to save edited content as a new artifact version.
       RBAC: require_project_role("owner", "admin", "qa-automation") on all endpoints.

Endpoints (mounted under /api/v1/projects/{project_id}):
  GET  /artifacts                               — List artifacts (optional ?artifact_type filter)
  GET  /artifacts/{artifact_id}                 — Artifact detail + current version content
  PUT  /artifacts/{artifact_id}                 — Save edit as new version (AC-28)
  GET  /artifacts/{artifact_id}/versions        — List all versions
  GET  /artifacts/{artifact_id}/versions/{ver}  — Specific version detail + content
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.artifacts.schemas import ArtifactDetail, ArtifactSummary, ArtifactUpdateRequest, ArtifactVersionSummary
from src.db import get_db
from src.middleware.rbac import require_project_role
from src.middleware.tenant_context import current_tenant_slug
from src.services.artifact_service import artifact_service
from src.services.tenant_provisioning import slug_to_schema_name

router = APIRouter(
    prefix="/api/v1/projects/{project_id}/artifacts",
    tags=["artifacts"],
)


@router.get("", response_model=List[ArtifactSummary])
async def list_artifacts(
    project_id: str,
    artifact_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    auth: tuple = require_project_role("owner", "admin", "qa-automation"),
) -> List[ArtifactSummary]:
    """Return artifacts for a project, optionally filtered by artifact_type."""
    slug = current_tenant_slug.get()
    schema_name = slug_to_schema_name(slug)
    rows = await artifact_service.list_artifacts(
        db=db,
        schema_name=schema_name,
        project_id=project_id,
        artifact_type=artifact_type,
    )
    return [ArtifactSummary(**row) for row in rows]


@router.get("/{artifact_id}", response_model=ArtifactDetail)
async def get_artifact(
    project_id: str,
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    auth: tuple = require_project_role("owner", "admin", "qa-automation"),
) -> ArtifactDetail:
    """Return artifact detail including current version content."""
    slug = current_tenant_slug.get()
    schema_name = slug_to_schema_name(slug)
    row = await artifact_service.get_artifact(
        db=db,
        schema_name=schema_name,
        project_id=project_id,
        artifact_id=artifact_id,
    )
    return ArtifactDetail(**row)


@router.put("/{artifact_id}", response_model=ArtifactDetail)
async def update_artifact(
    project_id: str,
    artifact_id: str,
    body: ArtifactUpdateRequest,
    db: AsyncSession = Depends(get_db),
    auth: tuple = require_project_role("owner", "admin", "qa-automation"),
) -> ArtifactDetail:
    """Save edited content as a new artifact version (AC-28)."""
    slug = current_tenant_slug.get()
    schema_name = slug_to_schema_name(slug)
    edited_by = str(auth[0].id)
    row = await artifact_service.update_artifact(
        db=db,
        schema_name=schema_name,
        project_id=project_id,
        artifact_id=artifact_id,
        content=body.content,
        edited_by=edited_by,
    )
    return ArtifactDetail(**row)


@router.get("/{artifact_id}/versions", response_model=List[ArtifactVersionSummary])
async def list_versions(
    project_id: str,
    artifact_id: str,
    db: AsyncSession = Depends(get_db),
    auth: tuple = require_project_role("owner", "admin", "qa-automation"),
) -> List[ArtifactVersionSummary]:
    """Return all versions for an artifact, latest first."""
    slug = current_tenant_slug.get()
    schema_name = slug_to_schema_name(slug)
    rows = await artifact_service.list_versions(
        db=db,
        schema_name=schema_name,
        project_id=project_id,
        artifact_id=artifact_id,
    )
    return [ArtifactVersionSummary(**row) for row in rows]


@router.get("/{artifact_id}/versions/{version}", response_model=ArtifactDetail)
async def get_version(
    project_id: str,
    artifact_id: str,
    version: int,
    db: AsyncSession = Depends(get_db),
    auth: tuple = require_project_role("owner", "admin", "qa-automation"),
) -> ArtifactDetail:
    """Return specific version detail + content for an artifact."""
    slug = current_tenant_slug.get()
    schema_name = slug_to_schema_name(slug)
    row = await artifact_service.get_version(
        db=db,
        schema_name=schema_name,
        project_id=project_id,
        artifact_id=artifact_id,
        version=version,
    )
    return ArtifactDetail(**row)
