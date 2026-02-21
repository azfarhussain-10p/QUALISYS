"""Create public.tenants, public.tenants_users; add default_tenant_id to public.users

Revision ID: 002
Revises: 001
Create Date: 2026-02-20

Story: 1-2-organization-creation-setup
AC: AC2 — public.tenants table with all required columns
AC: AC2 — LOWER(slug) unique index for case-insensitive uniqueness
AC: AC4 — public.tenants_users join table with role
AC: AC4 — public.users.default_tenant_id nullable FK

Subtasks:
  1.1 - public.tenants (id, name, slug unique, logo_url, custom_domain,
        data_retention_days default 365, plan default 'free', settings JSONB,
        created_by FK, created_at, updated_at)
  1.2 - LOWER(slug) unique expression index on public.tenants
  1.3 - public.tenants_users (tenant_id FK, user_id FK, role, joined_at, PK composite)
  1.4 - public.users.default_tenant_id nullable FK to public.tenants
  1.5 - FK constraint from public.user_email_index.tenant_id -> public.tenants.id
  1.6 - Downgrade (rollback) script

Note: public.user_email_index.tenant_id was created in migration 001 without
      FK constraint (public.tenants didn't exist then). Adding FK here.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # Subtask 1.1: public.tenants — tenant registry
    # Holds the org name, slug, settings, and meta.
    # Per-tenant schema (tenant_{slug}) created dynamically by provisioning service.
    # -------------------------------------------------------------------------
    op.create_table(
        "tenants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        # Slug: URL-safe identifier (lowercase alphanumeric + hyphens, max 50 chars)
        # AC2: lowercase, unique, alphanumeric + hyphens, no leading/trailing hyphens
        sa.Column("slug", sa.String(50), nullable=False),
        # Profile / settings
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("custom_domain", sa.String(255), nullable=True),
        # AC2: data_retention_days default 365
        sa.Column("data_retention_days", sa.Integer(), nullable=False, server_default="365"),
        # AC2: plan default 'free'
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        # AC2: settings JSONB default {}
        sa.Column("settings", postgresql.JSONB(), nullable=False, server_default="{}"),
        # Audit
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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

    # Subtask 1.2: LOWER(slug) unique expression index — case-insensitive uniqueness (AC2)
    op.execute(
        "CREATE UNIQUE INDEX ix_tenants_slug_lower ON public.tenants (LOWER(slug))"
    )
    # Standard btree index for exact-match and prefix queries
    op.create_index("ix_tenants_slug", "tenants", ["slug"], schema="public")

    # updated_at trigger for public.tenants (reuses the function created in migration 001)
    op.execute("""
        CREATE TRIGGER trg_tenants_updated_at
        BEFORE UPDATE ON public.tenants
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """)

    # -------------------------------------------------------------------------
    # Subtask 1.3: public.tenants_users — membership + role join table
    # AC4: tenant_id FK, user_id FK, role varchar 30, joined_at, composite PK
    # -------------------------------------------------------------------------
    op.create_table(
        "tenants_users",
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # AC4: role — one of: owner, admin, pm-csm, qa-manual, qa-automation, developer, viewer
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        # Composite primary key on (tenant_id, user_id) — each user has one role per tenant
        sa.PrimaryKeyConstraint("tenant_id", "user_id", name="pk_tenants_users"),
        schema="public",
    )

    op.create_index("ix_tenants_users_tenant_id", "tenants_users", ["tenant_id"], schema="public")
    op.create_index("ix_tenants_users_user_id", "tenants_users", ["user_id"], schema="public")

    # -------------------------------------------------------------------------
    # Subtask 1.4: Add default_tenant_id nullable FK to public.users
    # AC4: "User's default tenant set in public.users.default_tenant_id"
    # NULL = user has not yet created or joined any org
    # -------------------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "default_tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("public.tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        schema="public",
    )

    # -------------------------------------------------------------------------
    # Subtask 1.5: Add FK constraint to public.user_email_index.tenant_id
    # Migration 001 created user_email_index.tenant_id WITHOUT FK (tenants didn't exist).
    # Now that public.tenants exists, add the referential constraint.
    # -------------------------------------------------------------------------
    op.create_foreign_key(
        "fk_user_email_index_tenant_id",
        "user_email_index",
        "tenants",
        ["tenant_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Subtask 1.6: rollback in reverse order

    # Remove FK from user_email_index
    op.drop_constraint(
        "fk_user_email_index_tenant_id",
        "user_email_index",
        schema="public",
        type_="foreignkey",
    )

    # Remove default_tenant_id from users
    op.drop_column("users", "default_tenant_id", schema="public")

    # Drop tenants_users indexes + table
    op.drop_index("ix_tenants_users_user_id", table_name="tenants_users", schema="public")
    op.drop_index("ix_tenants_users_tenant_id", table_name="tenants_users", schema="public")
    op.drop_table("tenants_users", schema="public")

    # Drop tenants trigger, indexes + table
    op.execute("DROP TRIGGER IF EXISTS trg_tenants_updated_at ON public.tenants")
    op.drop_index("ix_tenants_slug", table_name="tenants", schema="public")
    op.execute("DROP INDEX IF EXISTS ix_tenants_slug_lower")
    op.drop_table("tenants", schema="public")
