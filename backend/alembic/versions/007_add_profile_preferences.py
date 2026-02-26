"""Add timezone to users + user_notification_preferences table

Revision ID: 007
Revises: 006
Create Date: 2026-02-24

Story: 1-8-profile-notification-preferences
AC: AC4 — timezone column on public.users
AC: AC6 — user_notification_preferences table for email notification prefs
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AC4: Add timezone column to public.users
    op.add_column(
        "users",
        sa.Column("timezone", sa.String(50), nullable=False, server_default="UTC"),
        schema="public",
    )

    # AC6: Create user_notification_preferences table
    op.create_table(
        "user_notification_preferences",
        # Primary key
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        # Foreign key to public.users
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("public.users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # Email notification toggles (default: all on — except security_alerts which can't be disabled)
        sa.Column("email_test_completions", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("email_test_failures", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("email_team_changes", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("email_security_alerts", sa.Boolean, nullable=False, server_default="true"),
        # Email frequency: 'realtime' | 'daily' | 'weekly'
        sa.Column("email_frequency", sa.String(20), nullable=False, server_default="realtime"),
        # Digest schedule (for daily/weekly)
        sa.Column("digest_time", sa.Time, nullable=False, server_default="09:00:00"),
        sa.Column("digest_day", sa.String(10), nullable=False, server_default="monday"),
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

    # AC: unique index — one preference row per user
    op.create_index(
        "ix_user_notification_preferences_user_id",
        "user_notification_preferences",
        ["user_id"],
        unique=True,
        schema="public",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_notification_preferences_user_id",
        table_name="user_notification_preferences",
        schema="public",
    )
    op.drop_table("user_notification_preferences", schema="public")
    op.drop_column("users", "timezone", schema="public")
