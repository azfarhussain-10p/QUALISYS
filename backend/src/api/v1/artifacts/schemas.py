"""
QUALISYS — Artifact API Schemas
Story: 2-10-test-artifact-storage-viewer
AC-26: Response models for artifact list, detail, and version endpoints.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ArtifactSummary(BaseModel):
    """Artifact list item — returned by GET /artifacts."""

    id: str
    agent_type: str
    artifact_type: str
    title: str
    current_version: int
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ArtifactDetail(ArtifactSummary):
    """Artifact detail — returned by GET /artifacts/{id}, includes version content."""

    content: str
    content_type: str


class ArtifactVersionSummary(BaseModel):
    """Version list item — returned by GET /artifacts/{id}/versions."""

    id: str
    version: int
    content_type: str
    edited_by: Optional[str] = None
    created_at: Optional[str] = None


class ArtifactUpdateRequest(BaseModel):
    """Request body for PUT /artifacts/{id} — save edited content (AC-28)."""

    content: str
