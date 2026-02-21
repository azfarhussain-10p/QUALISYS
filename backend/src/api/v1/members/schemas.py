"""
QUALISYS — Member Management API Schemas
Story: 1-4-user-management-remove-change-roles
ACs: AC1, AC2, AC3, AC6
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator

from src.services.user_management.user_management_service import ALLOWED_ROLES


class MemberResponse(BaseModel):
    """Single member record returned by GET /members and PATCH /members/{id}/role."""
    user_id: uuid.UUID
    email: str
    full_name: str
    role: str
    joined_at: datetime
    is_active: bool

    model_config = {"from_attributes": True}


class PaginatedMembersResponse(BaseModel):
    """Paginated list of active members. AC1."""
    members: list[MemberResponse]
    total: int
    page: int
    per_page: int


class ChangeRoleRequest(BaseModel):
    """Body for PATCH /api/v1/orgs/{org_id}/members/{user_id}/role. AC2."""
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ALLOWED_ROLES:
            raise ValueError(f"Role must be one of: {', '.join(sorted(ALLOWED_ROLES))}")
        return v


class RemoveMemberResponse(BaseModel):
    """Response body for DELETE /api/v1/orgs/{org_id}/members/{user_id}. AC3."""
    message: str
    removed_at: datetime
