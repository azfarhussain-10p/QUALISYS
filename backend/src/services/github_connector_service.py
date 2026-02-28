"""
QUALISYS — GitHub Connector Service
Story: 2-3-github-repository-connection
AC: #9 — validate PAT via GitHub API; INVALID_TOKEN on 401/403/404
AC: #10 — clone repo to tenant-scoped temp dir; 7-day expiry + cleanup

Security (C1):
  - All SQL uses text() with :params — no user data in f-string interpolation
  - schema_name always double-quoted; no tenant data appended to SQL strings
  - PAT encrypted at rest with Fernet (AES-128-CBC + HMAC-SHA256)
  - Clone URL uses embedded PAT (https://{pat}@github.com/...) — never logged
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx
from cryptography.fernet import Fernet, InvalidToken as FernetInvalidToken
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db import AsyncSessionLocal
from src.logger import logger
from src.services.source_code_analyzer_service import source_code_analyzer_service

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GITHUB_API_BASE    = "https://api.github.com"
_CLONE_BASE_DIR     = Path("tmp/tenants")
_REPO_EXPIRY_DAYS   = 7

# Regex to extract owner/repo from GitHub URLs:
# https://github.com/owner/repo  or  git@github.com:owner/repo.git
_REPO_URL_RE = re.compile(
    r"(?:https?://github\.com/|git@github\.com:)"
    r"([A-Za-z0-9_.\-]+)/([A-Za-z0-9_.\-]+?)(?:\.git)?$"
)


# ---------------------------------------------------------------------------
# GitHubConnectorService
# ---------------------------------------------------------------------------

class GitHubConnectorService:
    """
    Validates GitHub PATs, manages github_connections rows, and clones repos
    into tenant-scoped temp directories with a 7-day expiry.
    """

    # ------------------------------------------------------------------
    # PAT encryption helpers
    # ------------------------------------------------------------------

    def _get_fernet(self) -> Fernet:
        settings = get_settings()
        return Fernet(settings.github_token_encryption_key.encode())

    def _encrypt_pat(self, pat: str) -> str:
        """Encrypt a GitHub PAT for at-rest storage."""
        return self._get_fernet().encrypt(pat.encode()).decode()

    def _decrypt_pat(self, encrypted: str) -> str:
        """Decrypt a stored encrypted PAT. Raises 500 on key mismatch."""
        try:
            return self._get_fernet().decrypt(encrypted.encode()).decode()
        except FernetInvalidToken as exc:
            logger.error("github: failed to decrypt stored PAT", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "TOKEN_DECRYPT_ERROR", "message": "Stored token could not be decrypted."},
            ) from exc

    # ------------------------------------------------------------------
    # AC-09: PAT validation
    # ------------------------------------------------------------------

    def _parse_owner_repo(self, repo_url: str) -> tuple[str, str]:
        """Extract (owner, repo) from a GitHub URL. Raises 400 on invalid format."""
        match = _REPO_URL_RE.match(repo_url.strip())
        if not match:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_REPO_URL", "message": "Repo URL must be a valid GitHub repository URL."},
            )
        return match.group(1), match.group(2)

    async def _validate_pat(self, repo_url: str, pat: str) -> None:
        """
        Call GitHub API to validate PAT has access to the repo.
        Raises HTTP 400 INVALID_TOKEN if validation fails.
        """
        owner, repo = self._parse_owner_repo(repo_url)
        url = f"{_GITHUB_API_BASE}/repos/{owner}/{repo}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, headers={"Authorization": f"token {pat}"})
        except httpx.RequestError as exc:
            logger.warning("github: PAT validation network error", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "GITHUB_UNREACHABLE", "message": "Could not reach GitHub API. Check your network connection."},
            ) from exc

        if resp.status_code in (401, 403, 404):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "INVALID_TOKEN", "message": "GitHub PAT is invalid or does not have access to this repository."},
            )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "GITHUB_API_ERROR", "message": f"GitHub API returned {resp.status_code}."},
            )

    # ------------------------------------------------------------------
    # AC-09 + AC-10: Connect repo
    # ------------------------------------------------------------------

    async def connect_repo(
        self,
        db:          AsyncSession,
        schema_name: str,
        project_id:  str,
        user_id:     str,
        repo_url:    str,
        pat:         str,
    ) -> dict[str, Any]:
        """
        Validate PAT, insert github_connections row (status='pending'),
        and return the connection dict. Caller must schedule clone_repo_task.
        Raises 409 CONNECTION_EXISTS if an active connection exists.
        """
        # AC-09: validate PAT first — fail fast before touching DB
        await self._validate_pat(repo_url, pat)

        # Check for existing active connection (not failed/expired)
        existing = await db.execute(
            text(
                f'SELECT id FROM "{schema_name}".github_connections '
                f"WHERE project_id = :pid "
                f"  AND status NOT IN ('failed', 'expired') "
                f"ORDER BY created_at DESC LIMIT 1"
            ),
            {"pid": project_id},
        )
        if existing.mappings().fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error": "CONNECTION_EXISTS", "message": "A GitHub connection already exists for this project. Disconnect it first."},
            )

        connection_id  = str(uuid.uuid4())
        encrypted_pat  = self._encrypt_pat(pat)
        now            = datetime.now(timezone.utc)

        await db.execute(
            text(
                f'INSERT INTO "{schema_name}".github_connections '
                f'(id, project_id, repo_url, encrypted_token, status, created_by, created_at, updated_at) '
                f'VALUES (:id, :pid, :repo_url, :token, :status, :created_by, :now, :now)'
            ),
            {
                "id":         connection_id,
                "pid":        project_id,
                "repo_url":   repo_url,
                "token":      encrypted_pat,
                "status":     "pending",
                "created_by": user_id,
                "now":        now,
            },
        )
        await db.commit()

        logger.info(
            "github: connection created",
            connection_id=connection_id,
            project_id=project_id,
        )
        return {
            "id":               connection_id,
            "project_id":       project_id,
            "repo_url":         repo_url,
            "status":           "pending",
            "routes_count":     0,
            "components_count": 0,
            "endpoints_count":  0,
            "analysis_summary": None,
            "error_message":    None,
            "expires_at":       None,
            "created_at":       now,
            "updated_at":       now,
        }

    # ------------------------------------------------------------------
    # Get connection
    # ------------------------------------------------------------------

    async def get_connection(
        self,
        db:          AsyncSession,
        schema_name: str,
        project_id:  str,
    ) -> Optional[dict[str, Any]]:
        """Return the most recent github_connections row for the project, or None."""
        result = await db.execute(
            text(
                f'SELECT id, project_id, repo_url, status, routes_count, '
                f'components_count, endpoints_count, analysis_summary, '
                f'error_message, expires_at, created_at, updated_at '
                f'FROM "{schema_name}".github_connections '
                f'WHERE project_id = :pid '
                f'ORDER BY created_at DESC LIMIT 1'
            ),
            {"pid": project_id},
        )
        row = result.mappings().fetchone()
        if not row:
            return None
        return dict(row)

    # ------------------------------------------------------------------
    # Disconnect
    # ------------------------------------------------------------------

    async def disconnect(
        self,
        db:          AsyncSession,
        schema_name: str,
        project_id:  str,
    ) -> None:
        """Delete the active github_connections row and clean up clone directory."""
        result = await db.execute(
            text(
                f'SELECT id, clone_path FROM "{schema_name}".github_connections '
                f'WHERE project_id = :pid '
                f'ORDER BY created_at DESC LIMIT 1'
            ),
            {"pid": project_id},
        )
        row = result.mappings().fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "CONNECTION_NOT_FOUND", "message": "No GitHub connection found for this project."},
            )

        # Delete clone directory if it exists
        if row["clone_path"]:
            clone_dir = Path(row["clone_path"])
            if clone_dir.exists():
                shutil.rmtree(clone_dir, ignore_errors=True)
                logger.info("github: clone dir removed", path=str(clone_dir))

        await db.execute(
            text(f'DELETE FROM "{schema_name}".github_connections WHERE id = :id'),
            {"id": row["id"]},
        )
        await db.commit()
        logger.info("github: connection deleted", connection_id=row["id"])

    # ------------------------------------------------------------------
    # Expired repo cleanup (arq cron — Story 2-6+)
    # ------------------------------------------------------------------

    async def cleanup_expired_repos(self, schema_name: str) -> int:
        """
        Delete clone directories for rows where expires_at < NOW() across
        the given schema. Updates status to 'expired'. Returns count cleaned.
        """
        cleaned = 0
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                text(
                    f'SELECT id, clone_path FROM "{schema_name}".github_connections '
                    f"WHERE expires_at < NOW() AND status IN ('cloned', 'analyzed')"
                )
            )
            rows = result.mappings().fetchall()
            for row in rows:
                if row["clone_path"]:
                    shutil.rmtree(row["clone_path"], ignore_errors=True)
                await db.execute(
                    text(
                        f'UPDATE "{schema_name}".github_connections '
                        f"SET status = 'expired', updated_at = NOW() WHERE id = :id"
                    ),
                    {"id": row["id"]},
                )
                cleaned += 1
            if cleaned:
                await db.commit()
        return cleaned


# ---------------------------------------------------------------------------
# AC-10: Background clone task (standalone — used with BackgroundTasks)
# ---------------------------------------------------------------------------

async def clone_repo_task(
    connection_id: str,
    schema_name:   str,
    tenant_id:     str,
    repo_url:      str,
    pat:           str,
) -> None:
    """
    Clone the GitHub repo into a tenant-scoped temp directory, then analyse
    the source code structure (Story 2-4).
    Status transitions: pending → cloning → cloned → analyzed (success)
                                                    → failed    (clone or analysis error)
    Called via FastAPI BackgroundTasks after connect_repo() succeeds.
    """
    from git import Repo, GitCommandError  # deferred — not installed in all test envs

    clone_dir = _CLONE_BASE_DIR / tenant_id / "repos" / connection_id

    async with AsyncSessionLocal() as db:
        # Mark cloning start
        await db.execute(
            text(
                f'UPDATE "{schema_name}".github_connections '
                f"SET status = 'cloning', updated_at = NOW() WHERE id = :id"
            ),
            {"id": connection_id},
        )
        await db.commit()

        try:
            clone_dir.mkdir(parents=True, exist_ok=True)

            # Build authenticated URL — PAT embedded so no interactive auth needed
            # Strip trailing .git if present before re-adding
            owner_repo = _REPO_URL_RE.match(repo_url.strip())
            if not owner_repo:
                raise ValueError(f"Cannot parse repo_url for clone: {repo_url}")
            clone_url = f"https://{pat}@github.com/{owner_repo.group(1)}/{owner_repo.group(2)}.git"

            logger.info("github: cloning repo", connection_id=connection_id, clone_dir=str(clone_dir))

            # Run synchronous git clone in thread pool to avoid blocking event loop
            await asyncio.to_thread(Repo.clone_from, clone_url, str(clone_dir), depth=1)

            expires_at = datetime.now(timezone.utc) + timedelta(days=_REPO_EXPIRY_DAYS)

            await db.execute(
                text(
                    f'UPDATE "{schema_name}".github_connections '
                    f"SET status = 'cloned', clone_path = :path, expires_at = :exp, "
                    f"    updated_at = NOW() "
                    f"WHERE id = :id"
                ),
                {"id": connection_id, "path": str(clone_dir), "exp": expires_at},
            )
            await db.commit()

            logger.info(
                "github: clone completed",
                connection_id=connection_id,
                clone_dir=str(clone_dir),
                expires_at=str(expires_at),
            )

            # Story 2-4: Source code analysis (AC-11d/e)
            # Runs inside the same AsyncSessionLocal() context — no new session needed (C6).
            try:
                summary    = source_code_analyzer_service.analyze(str(clone_dir))
                routes     = summary.get('routes', [])
                components = summary.get('components', [])

                await db.execute(
                    text(
                        f'UPDATE "{schema_name}".github_connections '
                        f"SET status = 'analyzed', "
                        f"    routes_count = :rc, "
                        f"    components_count = :cc, "
                        f"    endpoints_count = :ec, "
                        f"    analysis_summary = CAST(:summary AS jsonb), "
                        f"    updated_at = NOW() "
                        f"WHERE id = :id"
                    ),
                    {
                        "id":      connection_id,
                        "rc":      len(routes),
                        "cc":      len(components),
                        "ec":      len(routes),      # endpoints == routes in MVP
                        "summary": json.dumps(summary),
                    },
                )
                await db.commit()

                logger.info(
                    "github: analysis completed",
                    connection_id=connection_id,
                    framework=summary.get('framework'),
                    routes_count=len(routes),
                    components_count=len(components),
                )

            except Exception as exc:
                logger.error(
                    "github: analysis failed",
                    connection_id=connection_id,
                    error=str(exc),
                )
                await db.execute(
                    text(
                        f'UPDATE "{schema_name}".github_connections '
                        f"SET status = 'failed', error_message = :msg, updated_at = NOW() "
                        f"WHERE id = :id"
                    ),
                    {"id": connection_id, "msg": str(exc)[:500]},
                )
                await db.commit()

        except (GitCommandError, ValueError, OSError) as exc:
            logger.error("github: clone failed", connection_id=connection_id, error=str(exc))
            # Clean up partially-created directory
            if clone_dir.exists():
                shutil.rmtree(clone_dir, ignore_errors=True)
            await db.execute(
                text(
                    f'UPDATE "{schema_name}".github_connections '
                    f"SET status = 'failed', error_message = :msg, updated_at = NOW() "
                    f"WHERE id = :id"
                ),
                {"id": connection_id, "msg": str(exc)[:500]},
            )
            await db.commit()


# Module-level singleton
github_connector_service = GitHubConnectorService()
