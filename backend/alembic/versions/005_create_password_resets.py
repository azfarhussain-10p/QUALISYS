"""Create public.password_resets table

Revision ID: 005
Revises: 004
Create Date: 2026-02-24

Story: 1-6-password-reset-flow
AC: AC3 — cryptographic reset token stored as SHA-256 hash, 1-hour expiry,
           previous tokens invalidated on new request
AC: AC6 — token validated and marked used after successful password reset
AC: AC8 — created_at for audit trail

Security constraints:
  - Token stored as SHA-256 hash ONLY (never plaintext)
  - Single-use: used_at set immediately after successful reset
  - 1-hour expiry: expires_at = created_at + 1h
  - Previous unused tokens invalidated on new request (used_at = now())
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------------------
    # Task 1.1 — public.password_resets table
    # ---------------------------------------------------------------------------
    op.create_table(
        "password_resets",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("public.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # SHA-256 hex digest = 64 chars — NEVER store raw token (AC3)
        sa.Column("token_hash", sa.String(64), nullable=False),
        # 1-hour window from creation (AC3)
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        # Set when used successfully — single-use enforcement (AC6)
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="public",
    )

    # Task 1.2 — index on token_hash for fast lookup during validation
    op.create_index(
        "ix_password_resets_token_hash",
        "password_resets",
        ["token_hash"],
        unique=True,
        schema="public",
    )

    # Task 1.3 — composite index on (user_id, used_at) for invalidating previous tokens
    # used_at IS NULL identifies active (unused) tokens for a user
    op.create_index(
        "ix_password_resets_user_id_used_at",
        "password_resets",
        ["user_id", "used_at"],
        schema="public",
    )


def downgrade() -> None:
    # Task 1.4 — rollback
    op.drop_index("ix_password_resets_user_id_used_at", table_name="password_resets", schema="public")
    op.drop_index("ix_password_resets_token_hash", table_name="password_resets", schema="public")
    op.drop_table("password_resets", schema="public")
