"""
Unit tests — ProjectService
Story: 1-9-project-creation-configuration
Task 6.1 — Unit tests: slug generation (basic, special chars, collision handling),
            input validation (URL formats)
AC: AC6 — generate_slug: lowercase, hyphens, collapse, strip, collision suffix
AC: AC7 — URL validation via Pydantic schemas
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.project_service import ProjectService, _slugify_base


# ---------------------------------------------------------------------------
# _slugify_base — AC6 slug algorithm
# ---------------------------------------------------------------------------

class TestSlugifyBase:
    """AC6: slug generation algorithm."""

    def test_basic_name(self):
        assert _slugify_base("My Project") == "my-project"

    def test_special_chars(self):
        assert _slugify_base("Hello! World?") == "hello-world"

    def test_consecutive_hyphens_collapsed(self):
        assert _slugify_base("A  B   C") == "a-b-c"

    def test_leading_trailing_stripped(self):
        assert _slugify_base("  My Project  ") == "my-project"

    def test_unicode_normalized(self):
        result = _slugify_base("Café")
        # Unicode normalize: Café → Cafe → cafe
        assert result == "cafe"

    def test_numbers_preserved(self):
        assert _slugify_base("Project 2024") == "project-2024"

    def test_empty_falls_back(self):
        assert _slugify_base("!@#$%") == "project"

    def test_truncates_at_90(self):
        long_name = "a" * 100
        result = _slugify_base(long_name)
        assert len(result) <= 90

    def test_all_special_chars(self):
        assert _slugify_base("!!!") == "project"


# ---------------------------------------------------------------------------
# ProjectService.generate_slug — AC6 collision handling
# ---------------------------------------------------------------------------

class TestGenerateSlug:
    """AC6: collision suffix -1, -2, ..."""

    @pytest.mark.asyncio
    async def test_no_collision(self):
        svc = ProjectService()
        mock_db = AsyncMock()
        # fetchone returns None → no existing slug
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            slug = await svc.generate_slug("My Project", mock_db, "tenant_test")

        assert slug == "my-project"

    @pytest.mark.asyncio
    async def test_collision_adds_suffix(self):
        svc = ProjectService()
        mock_db = AsyncMock()

        # First call returns row (collision), second returns None (available)
        mock_collision = MagicMock()
        mock_collision.fetchone.return_value = ("conflict",)
        mock_clear = MagicMock()
        mock_clear.fetchone.return_value = None
        mock_db.execute.side_effect = [mock_collision, mock_clear]

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            slug = await svc.generate_slug("My Project", mock_db, "tenant_test")

        assert slug == "my-project-1"

    @pytest.mark.asyncio
    async def test_multiple_collisions(self):
        svc = ProjectService()
        mock_db = AsyncMock()

        collision = MagicMock()
        collision.fetchone.return_value = ("conflict",)
        clear = MagicMock()
        clear.fetchone.return_value = None
        # 3 collisions then clear
        mock_db.execute.side_effect = [collision, collision, collision, clear]

        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            slug = await svc.generate_slug("My Project", mock_db, "tenant_test")

        assert slug == "my-project-3"

    @pytest.mark.asyncio
    async def test_exclude_id_skips_self(self):
        """When updating, existing record shouldn't conflict with itself."""
        import uuid
        svc = ProjectService()
        mock_db = AsyncMock()

        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_db.execute.return_value = mock_result

        own_id = uuid.uuid4()
        with patch("src.services.project_service._get_schema", return_value="tenant_test"):
            slug = await svc.generate_slug("My Project", mock_db, "tenant_test", exclude_id=own_id)

        assert slug == "my-project"


# ---------------------------------------------------------------------------
# Pydantic schema validation — AC7
# ---------------------------------------------------------------------------

class TestProjectSchemas:
    """AC7: server-side validation of request schemas."""

    def test_name_too_short(self):
        from pydantic import ValidationError
        from src.api.v1.projects.schemas import CreateProjectRequest

        with pytest.raises(ValidationError) as exc_info:
            CreateProjectRequest(name="ab")
        assert "min_length" in str(exc_info.value) or "3" in str(exc_info.value)

    def test_name_too_long(self):
        from pydantic import ValidationError
        from src.api.v1.projects.schemas import CreateProjectRequest

        with pytest.raises(ValidationError):
            CreateProjectRequest(name="a" * 101)

    def test_valid_app_url(self):
        from src.api.v1.projects.schemas import CreateProjectRequest

        req = CreateProjectRequest(name="Test Project", app_url="https://app.example.com")
        assert req.app_url == "https://app.example.com"

    def test_invalid_app_url_rejects_javascript(self):
        from pydantic import ValidationError
        from src.api.v1.projects.schemas import CreateProjectRequest

        with pytest.raises(ValidationError) as exc_info:
            CreateProjectRequest(name="Test", app_url="javascript:alert(1)")
        assert "scheme" in str(exc_info.value).lower() or "not allowed" in str(exc_info.value).lower()

    def test_invalid_app_url_rejects_data_uri(self):
        from pydantic import ValidationError
        from src.api.v1.projects.schemas import CreateProjectRequest

        with pytest.raises(ValidationError):
            CreateProjectRequest(name="Test", app_url="data:text/html,<script>alert(1)</script>")

    def test_valid_github_url(self):
        from src.api.v1.projects.schemas import CreateProjectRequest

        req = CreateProjectRequest(
            name="Test Project",
            github_repo_url="https://github.com/owner/repo"
        )
        assert req.github_repo_url == "https://github.com/owner/repo"

    def test_invalid_github_url_non_github(self):
        from pydantic import ValidationError
        from src.api.v1.projects.schemas import CreateProjectRequest

        with pytest.raises(ValidationError):
            CreateProjectRequest(name="Test", github_repo_url="https://gitlab.com/owner/repo")

    def test_invalid_github_url_missing_repo(self):
        from pydantic import ValidationError
        from src.api.v1.projects.schemas import CreateProjectRequest

        with pytest.raises(ValidationError):
            CreateProjectRequest(name="Test", github_repo_url="https://github.com/owner")

    def test_description_too_long(self):
        from pydantic import ValidationError
        from src.api.v1.projects.schemas import CreateProjectRequest

        with pytest.raises(ValidationError):
            CreateProjectRequest(name="Test Project", description="x" * 2001)

    def test_name_whitespace_stripped(self):
        from src.api.v1.projects.schemas import CreateProjectRequest

        req = CreateProjectRequest(name="  My Project  ")
        assert req.name == "My Project"

    def test_update_settings_invalid_environment(self):
        from pydantic import ValidationError
        from src.api.v1.projects.schemas import UpdateProjectRequest

        with pytest.raises(ValidationError):
            UpdateProjectRequest(settings={"default_environment": "invalid_env"})

    def test_update_settings_too_many_tags(self):
        from pydantic import ValidationError
        from src.api.v1.projects.schemas import UpdateProjectRequest

        with pytest.raises(ValidationError):
            UpdateProjectRequest(settings={"tags": [f"tag{i}" for i in range(11)]})

    def test_update_settings_tag_too_long(self):
        from pydantic import ValidationError
        from src.api.v1.projects.schemas import UpdateProjectRequest

        with pytest.raises(ValidationError):
            UpdateProjectRequest(settings={"tags": ["a" * 51]})

    def test_update_valid_settings(self):
        from src.api.v1.projects.schemas import UpdateProjectRequest

        req = UpdateProjectRequest(
            settings={
                "default_environment": "staging",
                "default_browser": "chromium",
                "tags": ["smoke", "regression"]
            }
        )
        assert req.settings["default_environment"] == "staging"
        assert req.settings["tags"] == ["smoke", "regression"]
