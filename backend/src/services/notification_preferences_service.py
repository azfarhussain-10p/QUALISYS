"""
QUALISYS — Notification Preferences Service
Story: 1-8-profile-notification-preferences
AC: AC6 — email notification preferences (categories, frequency, digest schedule)
AC: AC7 — preferences applied to notifications; security_alerts non-disableable
AC: AC9 — audit log on preferences update
"""

import uuid
from datetime import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.logger import logger
from src.models.user_notification_preferences import UserNotificationPreferences

# Valid email frequency values
_VALID_FREQUENCIES = {"realtime", "daily", "weekly"}
# Valid digest days (for weekly frequency)
_VALID_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}


async def get_preferences(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> UserNotificationPreferences:
    """
    Return notification preferences for user. Creates default row on first access (lazy init).

    Args:
        db:      Database session
        user_id: User to query

    Returns:
        UserNotificationPreferences row (with all defaults if newly created)
    """
    result = await db.execute(
        select(UserNotificationPreferences).where(
            UserNotificationPreferences.user_id == user_id
        )
    )
    prefs = result.scalar_one_or_none()

    if prefs is None:
        # Lazy creation with defaults (AC6)
        prefs = UserNotificationPreferences(
            id=uuid.uuid4(),
            user_id=user_id,
        )
        db.add(prefs)
        await db.flush()

    return prefs


async def update_preferences(
    db: AsyncSession,
    user_id: uuid.UUID,
    email_test_completions: Optional[bool] = None,
    email_test_failures: Optional[bool] = None,
    email_team_changes: Optional[bool] = None,
    email_security_alerts: Optional[bool] = None,
    email_frequency: Optional[str] = None,
    digest_time: Optional[time] = None,
    digest_day: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> UserNotificationPreferences:
    """
    Update notification preferences (upsert).

    AC7: email_security_alerts=False is silently overridden to True.
    AC6: email_frequency must be one of: realtime, daily, weekly.
    AC6: digest_day must be a valid day name (for weekly frequency).

    Raises:
        ValueError: On invalid frequency or digest_day
    """
    prefs = await get_preferences(db, user_id)

    if email_frequency is not None:
        if email_frequency not in _VALID_FREQUENCIES:
            raise ValueError(
                f"Invalid frequency '{email_frequency}'. Must be: realtime, daily, or weekly."
            )
        prefs.email_frequency = email_frequency

    if digest_day is not None:
        if digest_day.lower() not in _VALID_DAYS:
            raise ValueError(
                f"Invalid digest_day '{digest_day}'. Must be a day name (e.g. monday, tuesday)."
            )
        prefs.digest_day = digest_day.lower()

    if digest_time is not None:
        prefs.digest_time = digest_time

    if email_test_completions is not None:
        prefs.email_test_completions = email_test_completions

    if email_test_failures is not None:
        prefs.email_test_failures = email_test_failures

    if email_team_changes is not None:
        prefs.email_team_changes = email_team_changes

    # AC7: security_alerts cannot be disabled — silently enforce
    if email_security_alerts is not None:
        prefs.email_security_alerts = True  # always on, regardless of request value

    await db.flush()

    # AC9: Audit
    logger.info(
        "Notification preferences updated",
        user_id=str(user_id),
        ip=ip,
        user_agent=user_agent,
    )

    return prefs


def should_notify(
    prefs: UserNotificationPreferences,
    category: str,
) -> bool:
    """
    Check whether a user should receive email for the given category.

    AC7: Security alerts always return True.

    Args:
        prefs:    User's notification preferences
        category: One of 'test_completions', 'test_failures', 'team_changes', 'security_alerts'

    Returns:
        True if the user wants to receive email for this category
    """
    if category == "security_alerts":
        return True  # AC7: non-disableable
    return getattr(prefs, f"email_{category}", True)
