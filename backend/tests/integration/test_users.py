"""
Integration Tests — Users API (Story 1-8 AC2–AC9)
Story: 1-8-profile-notification-preferences (Task 7.2–7.7)

Covers:
  7.2  GET /api/v1/users/me — returns profile
       PATCH /api/v1/users/me/profile — updates name, timezone; validation errors
  7.3  POST /api/v1/users/me/avatar — presigned URL generation
       DELETE /api/v1/users/me/avatar — removes avatar URL
  7.4  POST /api/v1/users/me/change-password — correct, wrong, weak, same-as-old, session invalidation
  7.5  GET/PUT /api/v1/users/me/notifications — defaults, update, security alerts non-disableable
  7.6  Change-password rate limiting (3/user/hour)
  7.7  JWT required, auth_provider check
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# GET /api/v1/users/me  (AC8)
# ===========================================================================

class TestGetMe:
    """GET /api/v1/users/me returns the authenticated user's profile."""

    @pytest.mark.asyncio
    async def test_returns_full_profile(self, client_with_auth, existing_user, auth_headers):
        r = await client_with_auth.get("/api/v1/users/me", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["email"] == existing_user.email
        assert data["full_name"] == existing_user.full_name
        assert "timezone" in data
        assert "auth_provider" in data
        assert "email_verified" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_requires_auth(self, client):
        r = await client.get("/api/v1/users/me")
        assert r.status_code == 401


# ===========================================================================
# PATCH /api/v1/users/me/profile  (AC2, AC4)
# ===========================================================================

class TestUpdateProfile:
    """PATCH /api/v1/users/me/profile updates name and timezone."""

    @pytest.mark.asyncio
    async def test_update_name(self, client_with_auth, auth_headers):
        r = await client_with_auth.patch(
            "/api/v1/users/me/profile",
            json={"full_name": "Updated Name"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["full_name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_timezone(self, client_with_auth, auth_headers):
        r = await client_with_auth.patch(
            "/api/v1/users/me/profile",
            json={"timezone": "America/Chicago"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["timezone"] == "America/Chicago"

    @pytest.mark.asyncio
    async def test_name_too_short_422(self, client_with_auth, auth_headers):
        r = await client_with_auth.patch(
            "/api/v1/users/me/profile",
            json={"full_name": "X"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_name_too_long_422(self, client_with_auth, auth_headers):
        r = await client_with_auth.patch(
            "/api/v1/users/me/profile",
            json={"full_name": "A" * 101},
            headers=auth_headers,
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_timezone_422(self, client_with_auth, auth_headers):
        r = await client_with_auth.patch(
            "/api/v1/users/me/profile",
            json={"timezone": "Not/AReal/Timezone"},
            headers=auth_headers,
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_requires_auth(self, client):
        r = await client.patch("/api/v1/users/me/profile", json={"full_name": "X"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_empty_body_ok(self, client_with_auth, auth_headers, existing_user):
        """Empty PATCH should be a no-op and return current profile."""
        r = await client_with_auth.patch(
            "/api/v1/users/me/profile",
            json={},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["email"] == existing_user.email


# ===========================================================================
# POST /api/v1/users/me/avatar  (AC3)
# ===========================================================================

class TestAvatarUpload:
    """POST /api/v1/users/me/avatar returns presigned URL."""

    @pytest.mark.asyncio
    async def test_presigned_url_returned(self, client_with_auth, auth_headers):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = "https://s3.example.com/upload"

        with patch("boto3.client", return_value=mock_s3):
            with patch("src.services.profile_service.settings") as ms:
                ms.s3_bucket_name = "test-bucket"
                ms.s3_avatar_key_prefix = "user-avatars"
                ms.avatar_presigned_url_expires = 300

                r = await client_with_auth.post(
                    "/api/v1/users/me/avatar",
                    json={
                        "filename": "photo.png",
                        "content_type": "image/png",
                        "file_size": 1024,
                    },
                    headers=auth_headers,
                )
        assert r.status_code == 200
        data = r.json()
        assert "upload_url" in data
        assert "key" in data
        assert "expires_in_seconds" in data

    @pytest.mark.asyncio
    async def test_invalid_content_type_422(self, client_with_auth, auth_headers):
        r = await client_with_auth.post(
            "/api/v1/users/me/avatar",
            json={
                "filename": "shell.sh",
                "content_type": "application/x-sh",
                "file_size": 100,
            },
            headers=auth_headers,
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_file_too_large_422(self, client_with_auth, auth_headers):
        r = await client_with_auth.post(
            "/api/v1/users/me/avatar",
            json={
                "filename": "big.png",
                "content_type": "image/png",
                "file_size": 6 * 1024 * 1024,
            },
            headers=auth_headers,
        )
        assert r.status_code == 422


# ===========================================================================
# DELETE /api/v1/users/me/avatar  (AC3)
# ===========================================================================

class TestRemoveAvatar:
    """DELETE /api/v1/users/me/avatar clears avatar_url."""

    @pytest.mark.asyncio
    async def test_remove_avatar_clears_url(self, client_with_auth, auth_headers, db_session, existing_user):
        # Seed an avatar URL
        existing_user.avatar_url = "https://s3.example.com/old-avatar.png"
        await db_session.flush()

        with patch("src.services.profile_service._delete_s3_avatar", return_value=None):
            r = await client_with_auth.delete(
                "/api/v1/users/me/avatar",
                headers=auth_headers,
            )
        assert r.status_code == 200
        assert r.json()["avatar_url"] is None


# ===========================================================================
# POST /api/v1/users/me/change-password  (AC5)
# ===========================================================================

class TestChangePassword:
    """POST /api/v1/users/me/change-password."""

    @pytest.mark.asyncio
    async def test_wrong_current_password_400(self, client_with_auth, auth_headers):
        with patch("src.services.profile_service.token_service") as mock_ts:
            mock_ts.invalidate_all_user_tokens = AsyncMock()
            r = await client_with_auth.post(
                "/api/v1/users/me/change-password",
                json={
                    "current_password": "WrongPassword!",
                    "new_password": "NewSecure789!@",
                    "confirm_new_password": "NewSecure789!@",
                },
                headers=auth_headers,
            )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_weak_new_password_422(self, client_with_auth, auth_headers):
        r = await client_with_auth.post(
            "/api/v1/users/me/change-password",
            json={
                "current_password": "SecurePass123!",
                "new_password": "weak",
                "confirm_new_password": "weak",
            },
            headers=auth_headers,
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_passwords_dont_match_422(self, client_with_auth, auth_headers):
        r = await client_with_auth.post(
            "/api/v1/users/me/change-password",
            json={
                "current_password": "SecurePass123!",
                "new_password": "NewSecure789!@",
                "confirm_new_password": "DifferentPass789!@",
            },
            headers=auth_headers,
        )
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_same_as_old_400(self, client_with_auth, auth_headers):
        with patch("src.services.profile_service.token_service") as mock_ts:
            mock_ts.invalidate_all_user_tokens = AsyncMock()
            r = await client_with_auth.post(
                "/api/v1/users/me/change-password",
                json={
                    "current_password": "SecurePass123!",
                    "new_password": "SecurePass123!",
                    "confirm_new_password": "SecurePass123!",
                },
                headers=auth_headers,
            )
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_successful_change_returns_message(self, client_with_auth, auth_headers):
        with patch("src.services.profile_service.token_service") as mock_ts:
            mock_ts.invalidate_all_user_tokens = AsyncMock()
            with patch("src.api.v1.auth.router._clear_auth_cookies"):
                r = await client_with_auth.post(
                    "/api/v1/users/me/change-password",
                    json={
                        "current_password": "SecurePass123!",
                        "new_password": "NewSecure789!@",
                        "confirm_new_password": "NewSecure789!@",
                    },
                    headers=auth_headers,
                )
        assert r.status_code == 200
        assert "message" in r.json()
        mock_ts.invalidate_all_user_tokens.assert_called_once()

    @pytest.mark.asyncio
    async def test_requires_auth(self, client):
        r = await client.post(
            "/api/v1/users/me/change-password",
            json={
                "current_password": "X",
                "new_password": "NewSecure789!@",
                "confirm_new_password": "NewSecure789!@",
            },
        )
        assert r.status_code == 401


    @pytest.mark.asyncio
    async def test_change_password_oauth_user_returns_400(self, client_with_auth, auth_headers, existing_user, db_session):
        """OAuth-only users (password_hash=None) cannot change password — AC5, AC: 8.7."""
        # Simulate an OAuth user by removing their password_hash
        existing_user.password_hash = None
        await db_session.flush()

        with patch("src.services.profile_service.token_service") as mock_ts:
            mock_ts.invalidate_all_user_tokens = AsyncMock()
            r = await client_with_auth.post(
                "/api/v1/users/me/change-password",
                json={
                    "current_password": "AnyPass123!",
                    "new_password": "NewSecure789!@",
                    "confirm_new_password": "NewSecure789!@",
                },
                headers=auth_headers,
            )
        assert r.status_code == 400
        data = r.json()
        assert data["error"]["code"] == "PASSWORD_CHANGE_ERROR"
        assert "social login" in data["error"]["message"].lower() or "oauth" in data["error"]["message"].lower()


# ===========================================================================
# Rate limiting — change-password  (AC: 4.8)
# ===========================================================================

class TestChangePasswordRateLimit:
    """POST /api/v1/users/me/change-password — rate limit 3/user/hour."""

    @pytest.mark.asyncio
    async def test_rate_limit_429(self, client_with_auth, auth_headers):
        """Mock Redis to report count ≥ 3 → 429."""
        from src.db import get_db
        from src.main import app
        from unittest.mock import AsyncMock, MagicMock

        rate_exceeded_redis = MagicMock()
        rate_exceeded_redis.get = AsyncMock(return_value=b"3")  # already at limit
        pipeline = MagicMock()
        pipeline.incr = MagicMock(return_value=pipeline)
        pipeline.expire = MagicMock(return_value=pipeline)
        pipeline.execute = AsyncMock(return_value=[4, True])
        rate_exceeded_redis.pipeline = MagicMock(return_value=pipeline)

        with patch("src.api.v1.users.router.get_redis_client", return_value=rate_exceeded_redis):
            r = await client_with_auth.post(
                "/api/v1/users/me/change-password",
                json={
                    "current_password": "SecurePass123!",
                    "new_password": "NewSecure789!@",
                    "confirm_new_password": "NewSecure789!@",
                },
                headers=auth_headers,
            )
        assert r.status_code == 429


# ===========================================================================
# GET /api/v1/users/me/notifications  (AC6)
# ===========================================================================

class TestGetNotifications:
    """GET /api/v1/users/me/notifications returns preferences with defaults on first access."""

    @pytest.mark.asyncio
    async def test_returns_defaults_on_first_access(self, client_with_auth, auth_headers):
        r = await client_with_auth.get("/api/v1/users/me/notifications", headers=auth_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["email_test_completions"] is True
        assert data["email_test_failures"] is True
        assert data["email_team_changes"] is True
        assert data["email_security_alerts"] is True
        assert data["email_frequency"] == "realtime"
        assert "digest_time" in data
        assert "digest_day" in data

    @pytest.mark.asyncio
    async def test_requires_auth(self, client):
        r = await client.get("/api/v1/users/me/notifications")
        assert r.status_code == 401


# ===========================================================================
# PUT /api/v1/users/me/notifications  (AC6, AC7)
# ===========================================================================

class TestUpdateNotifications:
    """PUT /api/v1/users/me/notifications saves preferences."""

    @pytest.mark.asyncio
    async def test_update_frequency_to_daily(self, client_with_auth, auth_headers):
        r = await client_with_auth.put(
            "/api/v1/users/me/notifications",
            json={"email_frequency": "daily", "digest_time": "08:00"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["email_frequency"] == "daily"
        assert data["digest_time"] == "08:00"

    @pytest.mark.asyncio
    async def test_update_toggles(self, client_with_auth, auth_headers):
        r = await client_with_auth.put(
            "/api/v1/users/me/notifications",
            json={"email_test_completions": False, "email_team_changes": False},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["email_test_completions"] is False
        assert data["email_team_changes"] is False

    @pytest.mark.asyncio
    async def test_security_alerts_always_true_ac7(self, client_with_auth, auth_headers):
        """AC7: setting email_security_alerts=False is silently overridden to True."""
        r = await client_with_auth.put(
            "/api/v1/users/me/notifications",
            json={"email_security_alerts": False},
            headers=auth_headers,
        )
        assert r.status_code == 200
        assert r.json()["email_security_alerts"] is True

    @pytest.mark.asyncio
    async def test_invalid_frequency_422(self, client_with_auth, auth_headers):
        r = await client_with_auth.put(
            "/api/v1/users/me/notifications",
            json={"email_frequency": "hourly"},
            headers=auth_headers,
        )
        assert r.status_code in (422, 400)

    @pytest.mark.asyncio
    async def test_weekly_with_day(self, client_with_auth, auth_headers):
        r = await client_with_auth.put(
            "/api/v1/users/me/notifications",
            json={"email_frequency": "weekly", "digest_day": "friday", "digest_time": "09:00"},
            headers=auth_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["email_frequency"] == "weekly"
        assert data["digest_day"] == "friday"

    @pytest.mark.asyncio
    async def test_requires_auth(self, client):
        r = await client.put("/api/v1/users/me/notifications", json={})
        assert r.status_code == 401
