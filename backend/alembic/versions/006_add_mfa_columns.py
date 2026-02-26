"""Add MFA columns to public.users and create public.user_backup_codes

Story: 1-7-two-factor-authentication-totp
AC: #3 (TOTP secret storage), #4 (backup code storage), #9 (MFA lockout column)

Revision ID: 006
Revises: 005
Create Date: 2026-02-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ---------------------------------------------------------------------------
    # Add MFA columns to public.users (AC3, AC9)
    # ---------------------------------------------------------------------------
    # totp_secret_encrypted — AES-256-GCM encrypted TOTP secret (never stored plaintext)
    # totp_enabled_at       — timestamp of when 2FA was successfully enabled (NULL = disabled)
    # mfa_lockout_until     — set after 10 failed MFA attempts/hr; blocks MFA until expiry
    op.add_column(
        "users",
        sa.Column("totp_secret_encrypted", sa.LargeBinary(), nullable=True),
        schema="public",
    )
    op.add_column(
        "users",
        sa.Column(
            "totp_enabled_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="public",
    )
    op.add_column(
        "users",
        sa.Column(
            "mfa_lockout_until",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        schema="public",
    )

    # ---------------------------------------------------------------------------
    # Create public.user_backup_codes table (AC4)
    # ---------------------------------------------------------------------------
    op.create_table(
        "user_backup_codes",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("public.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # bcrypt hash of the backup code (one-way — never store plaintext)
        sa.Column("code_hash", sa.String(255), nullable=False),
        # Set when code is consumed — single-use enforcement
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        schema="public",
    )

    # Index on user_id — for fast lookup of all backup codes for a user
    op.create_index(
        "ix_user_backup_codes_user_id",
        "user_backup_codes",
        ["user_id"],
        schema="public",
    )


def downgrade() -> None:
    # Drop backup codes table first (FK dependency on users)
    op.drop_index("ix_user_backup_codes_user_id", table_name="user_backup_codes", schema="public")
    op.drop_table("user_backup_codes", schema="public")

    # Remove MFA columns from users
    op.drop_column("users", "mfa_lockout_until", schema="public")
    op.drop_column("users", "totp_enabled_at", schema="public")
    op.drop_column("users", "totp_secret_encrypted", schema="public")
