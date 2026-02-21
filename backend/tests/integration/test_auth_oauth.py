"""
Integration Tests — Google OAuth Flow
Story: 1-1-user-account-creation (Task 6.3)
AC: AC2
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


class TestGoogleOAuthAuthorize:
    async def test_authorize_redirects_to_google(self, client: AsyncClient):
        """AC2: OAuth button initiates authorization code flow."""
        with patch("src.api.v1.auth.router.settings") as mock_settings:
            mock_settings.google_client_id = "test-client-id"
            mock_settings.google_redirect_uri = "http://localhost:8000/api/v1/auth/oauth/google/callback"
            mock_settings.frontend_url = "http://localhost:3000"

            # Mock redis for state storage
            mock_redis = MagicMock()
            mock_redis.setex = AsyncMock(return_value=True)
            with patch("src.api.v1.auth.router.get_redis_client", return_value=mock_redis):
                response = await client.get(
                    "/api/v1/auth/oauth/google/authorize",
                    follow_redirects=False,
                )
        assert response.status_code == 307
        location = response.headers["location"]
        assert "accounts.google.com" in location
        assert "client_id=test-client-id" in location
        assert "code_challenge" in location
        assert "code_challenge_method=S256" in location

    async def test_authorize_returns_501_when_not_configured(self, client: AsyncClient):
        """Returns 501 when Google OAuth is not configured."""
        with patch("src.api.v1.auth.router.settings") as mock_settings:
            mock_settings.google_client_id = ""
            response = await client.get("/api/v1/auth/oauth/google/authorize")
        assert response.status_code == 501


class TestGoogleOAuthCallback:
    async def test_callback_handles_consent_denied(self, client: AsyncClient):
        """AC2: user denying consent redirects with error param."""
        with patch("src.api.v1.auth.router.settings") as mock_settings:
            mock_settings.frontend_url = "http://localhost:3000"
            mock_redis = MagicMock()
            mock_redis.pipeline.return_value = MagicMock()
            pipe = mock_redis.pipeline.return_value
            pipe.incr = MagicMock(return_value=pipe)
            pipe.ttl = MagicMock(return_value=pipe)
            pipe.execute = AsyncMock(return_value=[1, 60])
            mock_redis.expire = AsyncMock()
            with patch("src.api.v1.auth.router.get_redis_client", return_value=mock_redis):
                response = await client.get(
                    "/api/v1/auth/oauth/google/callback?error=access_denied",
                    follow_redirects=False,
                )
        assert response.status_code == 307
        assert "oauth_denied" in response.headers["location"]

    async def test_callback_invalid_state_redirects_with_error(self, client: AsyncClient):
        """AC2: CSRF protection — invalid state param."""
        mock_redis = MagicMock()
        pipe = MagicMock()
        pipe.incr = MagicMock(return_value=pipe)
        pipe.ttl = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[1, 60])
        mock_redis.pipeline.return_value = pipe
        mock_redis.expire = AsyncMock()
        mock_redis.getdel = AsyncMock(return_value=None)  # state not found

        with patch("src.api.v1.auth.router.get_redis_client", return_value=mock_redis):
            with patch("src.api.v1.auth.router.settings") as mock_settings:
                mock_settings.frontend_url = "http://localhost:3000"
                response = await client.get(
                    "/api/v1/auth/oauth/google/callback?code=abc&state=badstate",
                    follow_redirects=False,
                )
        assert response.status_code == 307
        assert "oauth_state_mismatch" in response.headers["location"]

    async def test_callback_creates_new_user_on_first_login(
        self, client: AsyncClient, db_session
    ):
        """AC2: on successful Google consent, creates account from Google profile."""
        mock_redis = MagicMock()
        pipe = MagicMock()
        pipe.incr = MagicMock(return_value=pipe)
        pipe.ttl = MagicMock(return_value=pipe)
        pipe.execute = AsyncMock(return_value=[1, 60])
        mock_redis.pipeline.return_value = pipe
        mock_redis.expire = AsyncMock()
        mock_redis.getdel = AsyncMock(return_value="test-code-verifier")
        mock_redis.setex = AsyncMock(return_value=True)

        mock_http_response = MagicMock()
        mock_http_response.json.side_effect = [
            {"access_token": "google-access-token"},  # token exchange
            {
                "sub": "google-sub-123",
                "email": "newgoogleuser@example.com",
                "name": "Google User",
                "picture": "https://example.com/avatar.jpg",
            },  # profile
        ]
        mock_http_response.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.__aenter__ = AsyncMock(return_value=mock_http_client)
        mock_http_client.__aexit__ = AsyncMock(return_value=False)
        mock_http_client.post = AsyncMock(return_value=mock_http_response)
        mock_http_client.get = AsyncMock(return_value=mock_http_response)

        with patch("src.api.v1.auth.router.get_redis_client", return_value=mock_redis):
            with patch("src.api.v1.auth.router.settings") as mock_settings:
                mock_settings.google_client_id = "test-id"
                mock_settings.google_client_secret = "test-secret"
                mock_settings.google_redirect_uri = "http://localhost:8000/callback"
                mock_settings.frontend_url = "http://localhost:3000"
                mock_settings.jwt_secret = "test-secret"
                mock_settings.jwt_algorithm = "HS256"
                mock_settings.jwt_access_token_expire_minutes = 15
                mock_settings.jwt_refresh_token_expire_days = 7
                with patch("src.api.v1.auth.router.httpx.AsyncClient", return_value=mock_http_client):
                    response = await client.get(
                        "/api/v1/auth/oauth/google/callback?code=testcode&state=teststate",
                        follow_redirects=False,
                    )
        assert response.status_code == 307
        location = response.headers["location"]
        assert "onboarding" in location or "access_token" in location
