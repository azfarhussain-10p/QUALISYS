"""
QUALISYS — DOM Crawler Service
Story: 2-5-application-dom-crawling
AC-12a: POST /crawls → 201, status='pending', background crawl_task enqueued
AC-12b: 409 CRAWL_ALREADY_ACTIVE if status IN ('pending','running') exists
AC-13:  auth_config password encrypted at rest (Fernet); decrypted at crawl_task time
AC-14a: GET /crawls (list), GET /crawls/{id} (detail or 404)
AC-14b: on completion → status='completed', pages/forms/links counts + crawl_data JSONB
AC-14c: asyncio.TimeoutError → 'timeout'; Exception → 'failed'; 'running' never terminal

Security (C1):
  - All SQL via text() with :params — no user data in f-string interpolation
  - schema_name always double-quoted
  - auth_config (with password_encrypted) NEVER returned in API responses (C7)
  - Credentials never logged
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from cryptography.fernet import Fernet, InvalidToken as FernetInvalidToken
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.db import AsyncSessionLocal
from src.logger import logger
from src.patterns.playwright_pattern import AuthConfig, CrawlConfig, run_crawl


# ---------------------------------------------------------------------------
# Fernet helpers (module-level, not instance — same key used for GitHub PAT)
# ---------------------------------------------------------------------------

def _get_fernet() -> Fernet:
    settings = get_settings()
    return Fernet(settings.github_token_encryption_key.encode())


def _encrypt_password(password: str) -> str:
    """Encrypt a plaintext password for at-rest storage in auth_config JSONB."""
    return _get_fernet().encrypt(password.encode()).decode()


def _decrypt_password(encrypted: str) -> str:
    """Decrypt a stored encrypted password. Raises 500 on key mismatch."""
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except FernetInvalidToken as exc:
        logger.error("crawl: failed to decrypt stored password", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "CREDENTIAL_DECRYPT_ERROR", "message": "Stored credentials could not be decrypted."},
        ) from exc


# ---------------------------------------------------------------------------
# DOMCrawlerService
# ---------------------------------------------------------------------------

class DOMCrawlerService:
    """
    Manages crawl_sessions rows and coordinates Playwright-based DOM crawls.
    The actual crawl logic is delegated to crawl_task (background function)
    which calls run_crawl() from the C2 pattern spike.
    """

    async def start_crawl(
        self,
        db:          AsyncSession,
        schema_name: str,
        project_id:  str,
        user_id:     str,
        target_url:  str,
        auth_config: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Insert a new crawl_sessions row with status='pending'.
        Raises 409 CRAWL_ALREADY_ACTIVE if an active session exists.
        Caller must schedule crawl_task via BackgroundTasks.
        """
        # AC-12b: concurrent limit — check before INSERT
        conflict = await db.execute(
            text(
                f'SELECT id FROM "{schema_name}".crawl_sessions '
                f"WHERE project_id = :pid AND status IN ('pending', 'running') "
                f"LIMIT 1"
            ),
            {"pid": project_id},
        )
        if conflict.mappings().fetchone():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "CRAWL_ALREADY_ACTIVE",
                    "message": "A crawl is already running for this project.",
                },
            )

        # AC-13: auth_config already pre-processed by router
        # (password → password_encrypted) before reaching this method.
        auth_config_db: Optional[dict[str, Any]] = auth_config

        crawl_id = str(uuid.uuid4())
        now      = datetime.now(timezone.utc)

        await db.execute(
            text(
                f'INSERT INTO "{schema_name}".crawl_sessions '
                f"(id, project_id, target_url, auth_config, status, created_by, created_at) "
                f"VALUES (:id, :pid, :url, CAST(:auth AS jsonb), 'pending', :uid, :now)"
            ),
            {
                "id":   crawl_id,
                "pid":  project_id,
                "url":  target_url,
                "auth": json.dumps(auth_config_db) if auth_config_db else None,
                "uid":  user_id,
                "now":  now,
            },
        )
        await db.commit()

        logger.info("crawl: session created", crawl_id=crawl_id, project_id=project_id)
        return {
            "id":            crawl_id,
            "project_id":    project_id,
            "target_url":    target_url,
            "status":        "pending",
            "pages_crawled": 0,
            "forms_found":   0,
            "links_found":   0,
            "crawl_data":    None,
            "error_message": None,
            "started_at":    None,
            "completed_at":  None,
            "created_at":    now,
        }

    async def get_crawl(
        self,
        db:          AsyncSession,
        schema_name: str,
        project_id:  str,
        crawl_id:    str,
    ) -> dict[str, Any]:
        """
        Return a crawl_sessions row (omitting auth_config).
        Raises 404 CRAWL_NOT_FOUND if not found.
        """
        result = await db.execute(
            text(
                f"SELECT id, project_id, target_url, status, pages_crawled, "
                f"forms_found, links_found, crawl_data, error_message, "
                f"started_at, completed_at, created_at "
                f'FROM "{schema_name}".crawl_sessions '
                f"WHERE id = :id AND project_id = :pid"
            ),
            {"id": crawl_id, "pid": project_id},
        )
        row = result.mappings().fetchone()
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "CRAWL_NOT_FOUND",
                    "message": "No crawl session found with the given ID.",
                },
            )
        return dict(row)

    async def list_crawls(
        self,
        db:          AsyncSession,
        schema_name: str,
        project_id:  str,
    ) -> list[dict[str, Any]]:
        """Return the latest 50 crawl_sessions for the project (newest first)."""
        result = await db.execute(
            text(
                f"SELECT id, project_id, target_url, status, pages_crawled, "
                f"forms_found, links_found, error_message, started_at, completed_at, created_at "
                f'FROM "{schema_name}".crawl_sessions '
                f"WHERE project_id = :pid "
                f"ORDER BY created_at DESC LIMIT 50"
            ),
            {"pid": project_id},
        )
        return [dict(row) for row in result.mappings().fetchall()]


# ---------------------------------------------------------------------------
# AC-14b/c: Background crawl task (standalone — used with BackgroundTasks)
# ---------------------------------------------------------------------------

async def crawl_task(
    crawl_id:       str,
    schema_name:    str,
    tenant_id:      str,  # noqa: ARG001 — reserved for future tenant-scoped limits
    target_url:     str,
    auth_config_db: Optional[dict[str, Any]],
) -> None:
    """
    Execute a Playwright DOM crawl in the background.
    Status transitions: pending → running → completed | timeout | failed
    Opens its own AsyncSessionLocal session (same pattern as clone_repo_task).
    Never raises — broad except guarantees 'running' is never a terminal state.
    """
    async with AsyncSessionLocal() as db:
        # 3-commit pattern step 1: mark running
        await db.execute(
            text(
                f'UPDATE "{schema_name}".crawl_sessions '
                f"SET status = 'running', started_at = NOW() WHERE id = :id"
            ),
            {"id": crawl_id},
        )
        await db.commit()

        try:
            # AC-13: decrypt password before passing to run_crawl
            auth_cfg: Optional[AuthConfig] = None
            if auth_config_db:
                encrypted_pw = auth_config_db.get("password_encrypted")
                plaintext_pw = _decrypt_password(encrypted_pw) if encrypted_pw else ""
                auth_cfg = AuthConfig(
                    login_url=auth_config_db.get("login_url", ""),
                    username_selector=auth_config_db.get("username_selector", ""),
                    password_selector=auth_config_db.get("password_selector", ""),
                    submit_selector=auth_config_db.get("submit_selector", ""),
                    username=auth_config_db.get("username", ""),
                    password=plaintext_pw,
                    post_login_url=auth_config_db.get("post_login_url"),
                )

            config = CrawlConfig(
                target_url=target_url,
                max_pages=100,
                timeout_ms=1_800_000,   # 30 minutes
                page_timeout=30_000,    # 30 seconds per page
                auth_config=auth_cfg,
            )

            # C6: run_crawl is async — await directly (no run_in_executor)
            result = await run_crawl(config)

            # AC-14b: serialize crawl_data (list[PageData] → JSON string)
            crawl_data_json = json.dumps(
                [dataclasses.asdict(p) for p in result.crawl_data]
            )

            # 3-commit pattern step 2: store results
            await db.execute(
                text(
                    f'UPDATE "{schema_name}".crawl_sessions '
                    f"SET status = 'completed', "
                    f"    pages_crawled = :pc, "
                    f"    forms_found = :ff, "
                    f"    links_found = :lf, "
                    f"    crawl_data = CAST(:data AS jsonb), "
                    f"    completed_at = NOW() "
                    f"WHERE id = :id"
                ),
                {
                    "id":   crawl_id,
                    "pc":   result.pages_crawled,
                    "ff":   result.forms_found,
                    "lf":   result.links_found,
                    "data": crawl_data_json,
                },
            )
            await db.commit()

            logger.info(
                "crawl: completed",
                crawl_id=crawl_id,
                pages=result.pages_crawled,
                forms=result.forms_found,
                links=result.links_found,
            )

        except asyncio.TimeoutError:
            # AC-14c: 30-min timeout
            logger.warning("crawl: timed out", crawl_id=crawl_id)
            await db.execute(
                text(
                    f'UPDATE "{schema_name}".crawl_sessions '
                    f"SET status = 'timeout', "
                    f"    error_message = 'Crawl timed out after 30 minutes' "
                    f"WHERE id = :id"
                ),
                {"id": crawl_id},
            )
            await db.commit()

        except Exception as exc:  # noqa: BLE001 — C4: guarantee no terminal 'running'
            # AC-14c: any other error → failed
            logger.error("crawl: failed", crawl_id=crawl_id, error=str(exc))
            await db.execute(
                text(
                    f'UPDATE "{schema_name}".crawl_sessions '
                    f"SET status = 'failed', "
                    f"    error_message = :msg "
                    f"WHERE id = :id"
                ),
                {"id": crawl_id, "msg": str(exc)[:500]},
            )
            await db.commit()


# Module-level singleton
dom_crawler_service = DOMCrawlerService()
