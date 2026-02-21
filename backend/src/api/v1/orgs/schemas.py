"""
QUALISYS — Organization API Schemas (Pydantic v2)
Story: 1-2-organization-creation-setup
AC: AC1 — CreateOrgRequest validates name (3-100 chars), slug format
AC: AC2 — OrgResponse includes all tenants columns
AC: AC5 — UpdateOrgSettingsRequest for PATCH /orgs/{id}/settings
AC: AC6 — PresignedUrlRequest / PresignedUrlResponse for logo upload
"""

import re
import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Slug validation helper
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}[a-z0-9]$")


def _validate_slug(slug: str) -> str:
    """
    Validate user-provided slug.
    Rules (AC2):
      - Lowercase alphanumeric + hyphens only
      - No leading/trailing hyphens
      - 3-50 chars (min 3: first + middle + last; covers the regex minimum of 3)
    """
    if not _SLUG_RE.match(slug):
        raise ValueError(
            "Slug must be 3-50 characters, lowercase alphanumeric and hyphens only, "
            "with no leading or trailing hyphens."
        )
    return slug


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CreateOrgRequest(BaseModel):
    """POST /api/v1/orgs — AC1, AC2"""

    name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Organization display name (3-100 characters)",
    )
    slug: Optional[str] = Field(
        None,
        description="URL slug (auto-generated from name if omitted). 3-50 chars, lowercase alphanumeric + hyphens.",
    )
    logo_url: Optional[str] = Field(None, description="S3 logo URL (set after upload)")
    custom_domain: Optional[str] = Field(
        None,
        max_length=255,
        description="Custom domain (e.g. app.mycompany.com)",
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_slug(v)
        return v

    @field_validator("custom_domain")
    @classmethod
    def validate_domain(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            domain_re = re.compile(
                r"^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
            )
            if not domain_re.match(v):
                raise ValueError("Custom domain must be a valid domain name (e.g. app.example.com).")
        return v


class UpdateOrgSettingsRequest(BaseModel):
    """PATCH /api/v1/orgs/{org_id}/settings — AC5"""

    name: Optional[str] = Field(None, min_length=3, max_length=100)
    slug: Optional[str] = Field(None, description="New slug — triggers uniqueness re-check")
    logo_url: Optional[str] = Field(None)
    custom_domain: Optional[str] = Field(None, max_length=255)
    data_retention_days: Optional[int] = Field(
        None,
        description="Data retention in days. Allowed: 30, 90, 180, 365",
    )
    settings: Optional[dict[str, Any]] = Field(None, description="Org JSONB settings")

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return _validate_slug(v)
        return v

    @field_validator("data_retention_days")
    @classmethod
    def validate_retention(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in (30, 90, 180, 365):
            raise ValueError("data_retention_days must be one of: 30, 90, 180, 365")
        return v

    @field_validator("custom_domain")
    @classmethod
    def validate_domain(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            domain_re = re.compile(
                r"^([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}$"
            )
            if not domain_re.match(v):
                raise ValueError("Custom domain must be a valid domain name.")
        return v


class PresignedUrlRequest(BaseModel):
    """POST /api/v1/orgs/{org_id}/logo/presigned-url — AC6"""

    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., description="MIME type: image/png, image/jpeg, image/svg+xml")
    file_size: int = Field(..., gt=0, description="File size in bytes (validated ≤ 2MB)")

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, v: str) -> str:
        allowed = {"image/png", "image/jpeg", "image/svg+xml"}
        if v not in allowed:
            raise ValueError(
                f"Unsupported file type '{v}'. Allowed: PNG, JPG, SVG."
            )
        return v

    @field_validator("file_size")
    @classmethod
    def validate_file_size(cls, v: int) -> int:
        max_bytes = 2 * 1024 * 1024  # 2MB
        if v > max_bytes:
            raise ValueError(f"File size {v} bytes exceeds maximum of 2MB ({max_bytes} bytes).")
        return v


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class OrgResponse(BaseModel):
    """Returned for org creation and settings GET. Excludes internal fields."""

    id: uuid.UUID
    name: str
    slug: str
    logo_url: Optional[str]
    custom_domain: Optional[str]
    data_retention_days: int
    plan: str
    settings: dict[str, Any]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    provisioning_status: Optional[str] = None  # "pending" | "ready" | "failed"

    model_config = {"from_attributes": True}


class CreateOrgResponse(BaseModel):
    """POST /api/v1/orgs response."""

    org: OrgResponse
    schema_name: str
    provisioning_status: str


class PresignedUrlResponse(BaseModel):
    """POST /api/v1/orgs/{org_id}/logo/presigned-url response — AC6"""

    upload_url: str
    key: str
    fields: dict[str, str] = {}
    expires_in_seconds: int = 900  # 15 minutes
