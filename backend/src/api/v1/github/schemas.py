"""
QUALISYS — GitHub Connection Schemas
Story: 2-3-github-repository-connection
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
import uuid

from pydantic import BaseModel, field_validator


class GitHubConnectRequest(BaseModel):
    repo_url: str
    pat: str

    @field_validator("repo_url")
    @classmethod
    def strip_repo_url(cls, v: str) -> str:
        return v.strip()

    @field_validator("pat")
    @classmethod
    def strip_pat(cls, v: str) -> str:
        return v.strip()


class GitHubConnectionResponse(BaseModel):
    id:                uuid.UUID
    project_id:        uuid.UUID
    repo_url:          str
    status:            str
    routes_count:      int
    components_count:  int
    endpoints_count:   int
    analysis_summary:  Optional[Any]    = None
    error_message:     Optional[str]    = None
    expires_at:        Optional[datetime] = None
    created_at:        datetime
    updated_at:        datetime

    model_config = {"from_attributes": True}
