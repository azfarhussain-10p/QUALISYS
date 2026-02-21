"""Add soft-delete columns to public.tenants_users

Revision ID: 004
Revises: 003
Create Date: 2026-02-21

Story: 1-4-user-management-remove-change-roles
AC: AC3 — soft delete via is_active flag + removed_at + removed_by
AC: AC7 — preserves referential integrity / audit trail (rows never deleted)

Subtasks:
  1.1 - Add is_active BOOLEAN NOT NULL DEFAULT true
  1.2 - Add removed_at TIMESTAMPTZ NULL
  1.3 - Add removed_by UUID NULL FK to public.users (ON DELETE SET NULL)
  1.4 - Create composite index (tenant_id, is_active) for efficient member queries
  1.5 - Rollback script
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1.1 — is_active: soft-delete flag (AC3)
    op.add_column(
        "tenants_users",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        schema="public",
    )

    # 1.2 — removed_at: timestamp of removal (AC3)
    op.add_column(
        "tenants_users",
        sa.Column(
            "removed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="public",
    )

    # 1.3 — removed_by: actor who removed the member (AC3, AC7)
    op.add_column(
        "tenants_users",
        sa.Column(
            "removed_by",
            UUID(as_uuid=True),
            nullable=True,
        ),
        schema="public",
    )
    op.create_foreign_key(
        "fk_tenants_users_removed_by",
        "tenants_users",
        "users",
        ["removed_by"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="SET NULL",
    )

    # 1.4 — composite index for active-member queries (AC1)
    op.create_index(
        "ix_tenants_users_tenant_active",
        "tenants_users",
        ["tenant_id", "is_active"],
        schema="public",
    )


def downgrade() -> None:
    # Reverse in the opposite order of creation
    op.drop_index("ix_tenants_users_tenant_active", table_name="tenants_users", schema="public")
    op.drop_constraint("fk_tenants_users_removed_by", "tenants_users", schema="public", type_="foreignkey")
    op.drop_column("tenants_users", "removed_by", schema="public")
    op.drop_column("tenants_users", "removed_at", schema="public")
    op.drop_column("tenants_users", "is_active", schema="public")
