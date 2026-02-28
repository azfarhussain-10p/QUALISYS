"""
Unit tests — GitHub Connector Service (Story 2-3)
DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.

Tests mock:
  - httpx.AsyncClient (GitHub API PAT validation)
  - git module (sys.modules patch — gitpython not installed in all test envs)
  - AsyncSessionLocal (DB session for background task)
"""

import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.services.github_connector_service import (
    GitHubConnectorService,
    clone_repo_task,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_svc() -> GitHubConnectorService:
    return GitHubConnectorService()


def _make_mock_db(existing_connection: bool = False):
    """Return a mock AsyncSession for github_connector tests."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        result = MagicMock()
        s = str(stmt).lower()
        if "select id from" in s and "github_connections" in s and "status not in" in s:
            # Existing connection check
            mappings = MagicMock()
            mappings.fetchone.return_value = {"id": str(uuid.uuid4())} if existing_connection else None
            result.mappings.return_value = mappings
        elif "select id, clone_path" in s:
            # disconnect() lookup
            mappings = MagicMock()
            mappings.fetchone.return_value = {"id": str(uuid.uuid4()), "clone_path": None}
            result.mappings.return_value = mappings
        else:
            result.scalar.return_value = None
            result.mappings.return_value = MagicMock(fetchone=MagicMock(return_value=None))
        return result

    mock_db.execute = mock_execute
    return mock_db


def _make_git_mock():
    """Build a sys.modules['git'] mock so deferred `from git import Repo` works."""
    mock_git = MagicMock()
    mock_git.GitCommandError = Exception
    return mock_git


# ---------------------------------------------------------------------------
# Tests: PAT validation
# ---------------------------------------------------------------------------

class TestValidatePat:

    @pytest.mark.asyncio
    async def test_validate_pat_success(self):
        # Proves: httpx 200 response → _validate_pat returns without raising.
        svc = _make_svc()
        mock_response = MagicMock(status_code=200)
        with patch("src.services.github_connector_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            await svc._validate_pat("https://github.com/owner/repo", "ghp_valid")

    @pytest.mark.asyncio
    async def test_validate_pat_invalid_token_401(self):
        # Proves: httpx 401 response → raises HTTP 400 INVALID_TOKEN.
        svc = _make_svc()
        mock_response = MagicMock(status_code=401)
        with patch("src.services.github_connector_service.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            with pytest.raises(HTTPException) as exc_info:
                await svc._validate_pat("https://github.com/owner/repo", "ghp_bad")

        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "INVALID_TOKEN"

    def test_validate_pat_malformed_url(self):
        # Proves: non-GitHub URL raises HTTP 400 INVALID_REPO_URL without calling API.
        svc = _make_svc()
        with pytest.raises(HTTPException) as exc_info:
            svc._parse_owner_repo("https://gitlab.com/owner/repo")
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail["error"] == "INVALID_REPO_URL"


# ---------------------------------------------------------------------------
# Tests: PAT encryption
# ---------------------------------------------------------------------------

class TestEncryption:

    def test_encrypt_decrypt_roundtrip(self):
        # Proves: encrypt then decrypt returns the original PAT unchanged.
        svc = _make_svc()
        pat = "ghp_supersecretpat1234567890abcdef"
        encrypted = svc._encrypt_pat(pat)
        assert encrypted != pat
        decrypted = svc._decrypt_pat(encrypted)
        assert decrypted == pat

    def test_encrypted_pat_differs_from_original(self):
        # Proves: the stored encrypted value does not expose the plain PAT (at-rest protection).
        svc = _make_svc()
        pat = "ghp_mytoken"
        encrypted = svc._encrypt_pat(pat)
        assert "ghp_mytoken" not in encrypted


# ---------------------------------------------------------------------------
# Tests: connect_repo
# ---------------------------------------------------------------------------

class TestConnectRepo:

    @pytest.mark.asyncio
    async def test_connect_repo_inserts_and_returns(self):
        # Proves: valid PAT + no existing connection → INSERT called and connection dict returned.
        svc = _make_svc()
        mock_db = _make_mock_db(existing_connection=False)

        with patch.object(svc, "_validate_pat", new_callable=AsyncMock):
            result = await svc.connect_repo(
                db=mock_db,
                schema_name="tenant_test",
                project_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                repo_url="https://github.com/owner/repo",
                pat="ghp_test",
            )

        assert result["status"] == "pending"
        assert result["repo_url"] == "https://github.com/owner/repo"
        assert "id" in result
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_repo_conflict_when_existing(self):
        # Proves: existing active connection → raises HTTP 409 CONNECTION_EXISTS.
        svc = _make_svc()
        mock_db = _make_mock_db(existing_connection=True)

        with patch.object(svc, "_validate_pat", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await svc.connect_repo(
                    db=mock_db,
                    schema_name="tenant_test",
                    project_id=str(uuid.uuid4()),
                    user_id=str(uuid.uuid4()),
                    repo_url="https://github.com/owner/repo",
                    pat="ghp_test",
                )
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["error"] == "CONNECTION_EXISTS"


# ---------------------------------------------------------------------------
# Tests: clone_repo_task
# ---------------------------------------------------------------------------

class TestCloneRepoTask:

    @pytest.mark.asyncio
    async def test_clone_repo_task_success(self):
        # Proves: successful git clone + analysis → DB updated to status='analyzed' with counts set (C9: 3 commits).
        connection_id = str(uuid.uuid4())
        tenant_id     = str(uuid.uuid4())

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock())

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_git = _make_git_mock()

        dummy_summary = {
            "framework": "fastapi",
            "routes":    [{"method": "GET", "path": "/api/test", "file": "main.py"}],
            "components": [],
            "endpoints": [{"method": "GET", "path": "/api/test", "file": "main.py"}],
        }

        with patch("src.services.github_connector_service.AsyncSessionLocal", return_value=mock_ctx):
            with patch("src.services.github_connector_service.Path.mkdir"):
                with patch("src.services.github_connector_service.asyncio.to_thread", new_callable=AsyncMock):
                    with patch.dict(sys.modules, {"git": mock_git}):
                        with patch(
                            "src.services.github_connector_service.source_code_analyzer_service.analyze",
                            return_value=dummy_summary,
                        ):
                            await clone_repo_task(
                                connection_id=connection_id,
                                schema_name="tenant_test",
                                tenant_id=tenant_id,
                                repo_url="https://github.com/owner/repo",
                                pat="ghp_test",
                            )

        # cloning → cloned → analyzed: 3 commits
        assert mock_db.commit.call_count == 3
        all_sql = " ".join(str(c.args[0]).lower() for c in mock_db.execute.call_args_list)
        assert "analyzed" in all_sql

    @pytest.mark.asyncio
    async def test_clone_repo_task_analysis_failure_marks_failed(self):
        # Proves: analysis exception after successful clone → DB status set to 'failed' (AC-11e, 3 commits total).
        connection_id = str(uuid.uuid4())
        tenant_id     = str(uuid.uuid4())

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock())

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_git = _make_git_mock()

        with patch("src.services.github_connector_service.AsyncSessionLocal", return_value=mock_ctx):
            with patch("src.services.github_connector_service.Path.mkdir"):
                with patch("src.services.github_connector_service.asyncio.to_thread", new_callable=AsyncMock):
                    with patch.dict(sys.modules, {"git": mock_git}):
                        with patch(
                            "src.services.github_connector_service.source_code_analyzer_service.analyze",
                            side_effect=RuntimeError("analysis exploded"),
                        ):
                            await clone_repo_task(
                                connection_id=connection_id,
                                schema_name="tenant_test",
                                tenant_id=tenant_id,
                                repo_url="https://github.com/owner/repo",
                                pat="ghp_test",
                            )

        # cloning → cloned → failed (analysis error): 3 commits
        assert mock_db.commit.call_count == 3
        all_sql = " ".join(str(c.args[0]).lower() for c in mock_db.execute.call_args_list)
        assert "failed" in all_sql

    @pytest.mark.asyncio
    async def test_clone_repo_task_failure_marks_failed(self):
        # Proves: exception during clone → DB status set to 'failed'.
        connection_id = str(uuid.uuid4())

        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock())

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        # Simulate git clone failure via OSError (no gitpython required)
        mock_git = _make_git_mock()

        with patch("src.services.github_connector_service.AsyncSessionLocal", return_value=mock_ctx):
            with patch("src.services.github_connector_service.Path.mkdir"):
                with patch(
                    "src.services.github_connector_service.asyncio.to_thread",
                    new_callable=AsyncMock,
                    side_effect=OSError("clone failed"),
                ):
                    with patch.dict(sys.modules, {"git": mock_git}):
                        await clone_repo_task(
                            connection_id=connection_id,
                            schema_name="tenant_test",
                            tenant_id=str(uuid.uuid4()),
                            repo_url="https://github.com/owner/repo",
                            pat="ghp_test",
                        )

        all_sql = " ".join(str(c.args[0]).lower() for c in mock_db.execute.call_args_list)
        assert "failed" in all_sql
