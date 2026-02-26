"""
QUALISYS — Project API Schemas
Story: 1-9-project-creation-configuration
AC: AC1 — CreateProjectRequest with name validation (3-100 chars), optional fields
AC: AC2 — ProjectResponse with all created fields
AC: AC3 — UpdateProjectRequest for PATCH settings
AC: AC4 — ProjectSettingsResponse for advanced settings
AC: AC7 — Validation: name required, URL formats

Story: 1-11-project-management-archive-delete-list
AC: AC1, AC2 — ProjectListItemResponse (adds member_count, health)
AC: AC1 — PaginatedProjectsResponse with pagination metadata
AC: AC6 — health field placeholder '—'
"""

import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# URL validators — AC7 (C6: reject javascript:, data: schemes)
# ---------------------------------------------------------------------------

_URL_RE = re.compile(
    r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE
)
_GITHUB_URL_RE = re.compile(
    r"^https://github\.com/[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+/?$"
)
_DANGEROUS_SCHEME_RE = re.compile(
    r"^(javascript|data|vbscript|file):", re.IGNORECASE
)


def _validate_app_url(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v = v.strip()
    if not v:
        return None
    if _DANGEROUS_SCHEME_RE.match(v):
        raise ValueError("URL scheme not allowed (javascript:, data:, etc.)")
    if not _URL_RE.match(v):
        raise ValueError("Must be a valid HTTP or HTTPS URL")
    return v


def _validate_github_url(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v = v.strip()
    if not v:
        return None
    if not _GITHUB_URL_RE.match(v):
        raise ValueError("Must be a valid GitHub URL: https://github.com/{owner}/{repo}")
    return v


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CreateProjectRequest(BaseModel):
    """POST /api/v1/projects — AC1, AC2, AC7"""

    name: str = Field(..., min_length=3, max_length=100, description="Project name (3-100 chars)")
    description: Optional[str] = Field(None, max_length=2000)
    app_url: Optional[str] = Field(None, max_length=500)
    github_repo_url: Optional[str] = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("name must be at least 3 characters after trimming whitespace")
        if len(v) > 100:
            raise ValueError("name must be at most 100 characters")
        return v

    @field_validator("app_url")
    @classmethod
    def validate_app_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_app_url(v)

    @field_validator("github_repo_url")
    @classmethod
    def validate_github_repo_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_github_url(v)


class UpdateProjectRequest(BaseModel):
    """PATCH /api/v1/projects/{project_id} — AC3, AC4, AC7"""

    name: Optional[str] = Field(None, min_length=3, max_length=100)
    description: Optional[str] = Field(None, max_length=2000)
    app_url: Optional[str] = Field(None, max_length=500)
    github_repo_url: Optional[str] = Field(None, max_length=500)
    settings: Optional[dict[str, Any]] = Field(None, description="Advanced settings JSONB (merged)")

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if len(v) < 3:
            raise ValueError("name must be at least 3 characters after trimming whitespace")
        return v

    @field_validator("app_url")
    @classmethod
    def validate_app_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_app_url(v)

    @field_validator("github_repo_url")
    @classmethod
    def validate_github_repo_url(cls, v: Optional[str]) -> Optional[str]:
        return _validate_github_url(v)

    @field_validator("settings")
    @classmethod
    def validate_settings(cls, v: Optional[dict]) -> Optional[dict]:
        if v is None:
            return v
        # AC4: validate known advanced settings keys
        allowed_envs = {"development", "staging", "production", "custom"}
        allowed_browsers = {"chromium", "firefox", "webkit"}

        if "default_environment" in v and v["default_environment"] not in allowed_envs:
            raise ValueError(f"default_environment must be one of: {', '.join(sorted(allowed_envs))}")
        if "default_browser" in v and v["default_browser"] not in allowed_browsers:
            raise ValueError(f"default_browser must be one of: {', '.join(sorted(allowed_browsers))}")
        if "tags" in v:
            tags = v["tags"]
            if not isinstance(tags, list):
                raise ValueError("tags must be an array")
            if len(tags) > 10:
                raise ValueError("tags: max 10 tags allowed")
            for tag in tags:
                if not isinstance(tag, str):
                    raise ValueError("tags: each tag must be a string")
                if len(tag) > 50:
                    raise ValueError("tags: each tag must be at most 50 characters")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class ProjectResponse(BaseModel):
    """Full project response — AC2, AC3, AC5"""

    id: str
    name: str
    slug: str
    description: Optional[str]
    app_url: Optional[str]
    github_repo_url: Optional[str]
    status: str
    settings: dict[str, Any]
    is_active: bool
    created_by: Optional[str]
    tenant_id: str
    organization_id: Optional[str]
    created_at: str
    updated_at: str

    @classmethod
    def from_project(cls, project: Any) -> "ProjectResponse":
        d = project.to_dict()
        return cls(**d)


class ProjectSettingsResponse(BaseModel):
    """GET /api/v1/projects/{id}/settings — AC4"""

    id: str
    name: str
    slug: str
    description: Optional[str]
    app_url: Optional[str]
    github_repo_url: Optional[str]
    default_environment: Optional[str]
    default_browser: Optional[str]
    tags: list[str]

    @classmethod
    def from_project(cls, project: Any) -> "ProjectSettingsResponse":
        settings = project.settings or {}
        return cls(
            id=str(project.id),
            name=project.name,
            slug=project.slug,
            description=project.description,
            app_url=project.app_url,
            github_repo_url=project.github_repo_url,
            default_environment=settings.get("default_environment"),
            default_browser=settings.get("default_browser"),
            tags=settings.get("tags", []),
        )


# ---------------------------------------------------------------------------
# Story 1.11 — Project list response schemas (AC1, AC2, AC6)
# ---------------------------------------------------------------------------

class ProjectListItemResponse(BaseModel):
    """
    Project item in list view. Story 1.11, AC1, AC2, AC6.
    Extends ProjectResponse with member_count and health placeholder.
    """
    id: str
    name: str
    slug: str
    description: Optional[str]
    app_url: Optional[str]
    github_repo_url: Optional[str]
    status: str
    settings: dict[str, Any]
    is_active: bool
    created_by: Optional[str]
    tenant_id: str
    organization_id: Optional[str]
    created_at: str
    updated_at: str
    member_count: int
    health: str  # AC6: placeholder '—', future metrics in Epic 2-4

    @classmethod
    def from_project_with_count(cls, p: Any) -> "ProjectListItemResponse":
        d = p.to_dict()
        return cls(**d)


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses. Story 1.11, AC1."""
    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedProjectsResponse(BaseModel):
    """Paginated project list response. Story 1.11, AC1, AC2."""
    data: list[ProjectListItemResponse]
    pagination: PaginationMeta
