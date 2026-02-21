"""Create public.invitations table

Revision ID: 003
Revises: 002
Create Date: 2026-02-21

Story: 1-3-team-member-invitation
AC: AC2 — public.invitations with id, tenant_id, email, role, invited_by, token,
           status, expires_at, accepted_at, created_at
AC: AC7 — lazy expiry; partial unique index prevents re-invite to same pending email
AC: AC9 — token unique index for O(1) accept lookup

Subtasks:
  1.1 - public.invitations core columns
  1.2 - Partial unique index (tenant_id, LOWER(email)) WHERE status='pending'
  1.3 - Unique index on token for fast accept lookup
  1.4 - Composite index on (tenant_id, status) for listing
  1.6 - Downgrade (rollback) script
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Subtask 1.1: public.invitations
    # Per architecture §Four-Pillar-Multi-Tenancy: stored in public schema
    # because accept flow happens BEFORE the user has tenant context.
    # -------------------------------------------------------------------------
    op.create_table(
        "invitations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # AC2: lowercase email, max 255 chars
        sa.Column("email", sa.String(255), nullable=False),
        # AC2: role from inviteable set (pm-csm, qa-manual, qa-automation, developer, viewer)
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column(
            "invited_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # AC9: cryptographically random token (secrets.token_urlsafe(32) → ~43 chars)
        sa.Column("token", sa.String(255), nullable=False),
        # status enum: 'pending' | 'accepted' | 'expired' | 'revoked'
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        # AC7: 7-day expiry — server-side validation on accept attempt
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        # AC4/AC5: set on acceptance
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="public",
    )

    # Subtask 1.2: Partial unique index — prevent duplicate pending invites
    # UNIQUE(tenant_id, LOWER(email)) WHERE status = 'pending'
    # Expired/revoked invites don't block a new invite to same email (AC7)
    op.execute(
        "CREATE UNIQUE INDEX ix_invitations_pending_email_per_tenant "
        "ON public.invitations (tenant_id, LOWER(email)) WHERE status = 'pending'"
    )

    # Subtask 1.3: Unique token index — O(1) accept lookup (AC3/AC9)
    op.create_index(
        "ix_invitations_token",
        "invitations",
        ["token"],
        unique=True,
        schema="public",
    )

    # Subtask 1.4: (tenant_id, status) composite — fast listing of pending/expired per org (AC6)
    op.create_index(
        "ix_invitations_tenant_status",
        "invitations",
        ["tenant_id", "status"],
        schema="public",
    )

    # Standard tenant_id index for FK cascade lookups
    op.create_index(
        "ix_invitations_tenant_id",
        "invitations",
        ["tenant_id"],
        schema="public",
    )


def downgrade() -> None:
    # Subtask 1.6: rollback in reverse creation order
    op.drop_index("ix_invitations_tenant_id", table_name="invitations", schema="public")
    op.drop_index("ix_invitations_tenant_status", table_name="invitations", schema="public")
    op.drop_index("ix_invitations_token", table_name="invitations", schema="public")
    op.execute("DROP INDEX IF EXISTS ix_invitations_pending_email_per_tenant")
    op.drop_table("invitations", schema="public")
