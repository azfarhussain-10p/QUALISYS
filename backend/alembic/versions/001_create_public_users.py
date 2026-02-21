"""Create public.users and public.user_email_index tables

Revision ID: 001
Revises:
Create Date: 2026-02-20

Story: 1-1-user-account-creation
AC: AC4 — public.users with all required columns
AC: AC5 — LOWER(email) unique index for case-insensitive duplicate detection

Subtasks:
  1.1 - public.users table with all AC4 columns
  1.2 - LOWER(email) unique expression index
  1.3 - SQLAlchemy User model (src/models/user.py)
  1.4 - Downgrade (rollback) script

Note: public.user_email_index is defined here (DDL only).
      Inserts occur in Story 1.2 when tenant association is established.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Subtask 1.1: public.users
    # The global user registry — created at signup, before any tenant exists.
    # Tenant schema users (with role, totp_secret, etc.) are created in Story 1.2.
    # -------------------------------------------------------------------------
    op.create_table(
        "users",
        # Primary key — UUID v4
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        # Identity
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        # AC4: password_hash NULL for OAuth-only accounts
        sa.Column("password_hash", sa.String(255), nullable=True),
        # AC3: email verification flag
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default="false"),
        # Auth provider enum — 'email' | 'google' (extensible: SAML, GitHub)
        sa.Column("auth_provider", sa.String(20), nullable=False, server_default="email"),
        # Google OAuth fields
        sa.Column("google_id", sa.String(255), nullable=True),
        # Profile
        sa.Column("avatar_url", sa.Text(), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="public",
    )

    # Subtask 1.2: LOWER(email) unique expression index — AC5
    # Prevents case-insensitive duplicates: user@example.com == USER@EXAMPLE.COM
    op.execute(
        "CREATE UNIQUE INDEX ix_users_email_lower ON public.users (LOWER(email))"
    )

    # Standard btree index for exact-match lookups (login, token validation)
    op.create_index("ix_users_email", "users", ["email"], schema="public")

    # -------------------------------------------------------------------------
    # public.user_email_index
    # Cross-tenant email lookup table (used for invite deduplication, login tenant lookup).
    # Populated by Story 1.2 (org creation) when tenant_id is available.
    # -------------------------------------------------------------------------
    op.create_table(
        "user_email_index",
        sa.Column("email", sa.String(255), primary_key=True, nullable=False),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="public",
    )

    # -------------------------------------------------------------------------
    # updated_at auto-update trigger on public.users
    # -------------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION public.set_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_users_updated_at
        BEFORE UPDATE ON public.users
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """)


def downgrade() -> None:
    # Subtask 1.4: rollback
    op.execute("DROP TRIGGER IF EXISTS trg_users_updated_at ON public.users")
    op.execute("DROP FUNCTION IF EXISTS public.set_updated_at()")
    op.drop_table("user_email_index", schema="public")
    op.drop_index("ix_users_email", table_name="users", schema="public")
    op.execute("DROP INDEX IF EXISTS ix_users_email_lower")
    op.drop_table("users", schema="public")
