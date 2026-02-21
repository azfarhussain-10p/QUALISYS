"""
Integration Tests — POST /api/v1/auth/register
Story: 1-1-user-account-creation (Task 6.2)
AC: AC1, AC4, AC5, AC6, AC8
"""

import pytest
from httpx import AsyncClient


pytestmark = pytest.mark.asyncio


class TestRegisterHappyPath:
    async def test_register_returns_201(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "SecurePass123!",
                "full_name": "New User",
            },
        )
        assert response.status_code == 201

    async def test_register_response_contains_user_and_tokens(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "jane@example.com",
                "password": "SecurePass123!",
                "full_name": "Jane Smith",
            },
        )
        data = response.json()
        assert "user" in data
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_register_user_fields_correct(self, client: AsyncClient):
        """AC4: user record has expected fields."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "jane2@example.com",
                "password": "SecurePass123!",
                "full_name": "Jane Smith",
            },
        )
        user = response.json()["user"]
        assert user["email"] == "jane2@example.com"
        assert user["full_name"] == "Jane Smith"
        assert user["email_verified"] is False
        assert user["auth_provider"] == "email"
        assert "id" in user
        assert "created_at" in user

    async def test_password_hash_not_in_response(self, client: AsyncClient):
        """AC7: password_hash NEVER returned in any response field."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "secure@example.com",
                "password": "SecurePass123!",
                "full_name": "Secure User",
            },
        )
        response_text = response.text
        assert "password_hash" not in response_text
        assert "SecurePass123!" not in response_text

    async def test_email_normalised_to_lowercase(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "UPPER@EXAMPLE.COM",
                "password": "SecurePass123!",
                "full_name": "Test",
            },
        )
        assert response.status_code == 201
        assert response.json()["user"]["email"] == "upper@example.com"


class TestRegisterValidation:
    async def test_invalid_email_returns_422(self, client: AsyncClient):
        """AC1: RFC 5322 email validation."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": "SecurePass123!", "full_name": "Test"},
        )
        assert response.status_code == 422

    async def test_weak_password_returns_422(self, client: AsyncClient):
        """AC1: password policy enforced server-side."""
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "short", "full_name": "Test"},
        )
        assert response.status_code == 422

    async def test_missing_full_name_returns_422(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "test@example.com", "password": "SecurePass123!"},
        )
        assert response.status_code == 422

    async def test_missing_fields_returns_422(self, client: AsyncClient):
        response = await client.post("/api/v1/auth/register", json={})
        assert response.status_code == 422


class TestRegisterDuplicateEmail:
    async def test_duplicate_email_returns_409(self, client: AsyncClient):
        """AC5: duplicate email returns 409, not 422 or 500."""
        payload = {
            "email": "dup@example.com",
            "password": "SecurePass123!",
            "full_name": "Dup User",
        }
        await client.post("/api/v1/auth/register", json=payload)
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 409

    async def test_duplicate_error_message_no_provider_leak(self, client: AsyncClient):
        """AC5: error message does NOT reveal which auth provider exists."""
        payload = {
            "email": "dup2@example.com",
            "password": "SecurePass123!",
            "full_name": "Dup User2",
        }
        await client.post("/api/v1/auth/register", json=payload)
        response = await client.post("/api/v1/auth/register", json=payload)
        error_msg = response.json()["error"]["message"].lower()
        assert "google" not in error_msg
        assert "oauth" not in error_msg
        assert "email" in error_msg or "account" in error_msg

    async def test_case_insensitive_duplicate_detection(self, client: AsyncClient):
        """AC5: UPPER@EXAMPLE.COM is same as upper@example.com."""
        await client.post(
            "/api/v1/auth/register",
            json={"email": "casecheck@example.com", "password": "SecurePass123!", "full_name": "Test"},
        )
        response = await client.post(
            "/api/v1/auth/register",
            json={"email": "CASECHECK@EXAMPLE.COM", "password": "SecurePass123!", "full_name": "Test"},
        )
        assert response.status_code == 409


class TestRegisterErrorFormat:
    async def test_error_response_structure(self, client: AsyncClient):
        """AC8: errors follow {error: {code, message}} structure."""
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup3@example.com",
                "password": "SecurePass123!",
                "full_name": "Test",
            },
        )
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup3@example.com",
                "password": "SecurePass123!",
                "full_name": "Test",
            },
        )
        dupe_response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "dup3@example.com",
                "password": "SecurePass123!",
                "full_name": "Test",
            },
        )
        data = dupe_response.json()
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
