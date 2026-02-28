"""
Unit tests — DOMCrawlerService + crawl_task (Story 2-5)
DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.

Mocks:
  - AsyncSession (mock_db) — no real DB required
  - AsyncSessionLocal context manager — crawl_task opens its own session
  - run_crawl — no Playwright in test env
"""

import asyncio
import dataclasses
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.services.dom_crawler_service import (
    DOMCrawlerService,
    _decrypt_password,
    _encrypt_password,
    crawl_task,
)
from src.patterns.playwright_pattern import CrawlResult, PageData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_db(conflict_row=None, session_row=None, session_rows=None):
    """Return a mock AsyncSession with configurable execute results."""
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()

    async def mock_execute(stmt, *args, **kwargs):
        result = MagicMock()
        mappings = MagicMock()
        s = str(stmt).lower()

        if "status in" in s and "crawl_sessions" in s:
            # Concurrent check
            mappings.fetchone.return_value = conflict_row
        elif "order by created_at desc limit 50" in s:
            # list_crawls — checked BEFORE "select id" to avoid false match
            mappings.fetchall.return_value = session_rows or []
        elif "select id" in s or ("select" in s and "where id" in s and "project_id" in s):
            # get_crawl single lookup
            mappings.fetchone.return_value = session_row
        else:
            mappings.fetchone.return_value = None
            mappings.fetchall.return_value = []

        result.mappings.return_value = mappings
        return result

    mock_db.execute = mock_execute
    return mock_db


def _make_session_row(crawl_id=None, project_id=None, status="pending"):
    """Return a dict that simulates a crawl_sessions DB row."""
    now = "2026-02-28T00:00:00+00:00"
    return {
        "id":            crawl_id or str(uuid.uuid4()),
        "project_id":    project_id or str(uuid.uuid4()),
        "target_url":    "https://app.example.com",
        "status":        status,
        "pages_crawled": 0,
        "forms_found":   0,
        "links_found":   0,
        "crawl_data":    None,
        "error_message": None,
        "started_at":    None,
        "completed_at":  None,
        "created_at":    now,
    }


# ---------------------------------------------------------------------------
# Task 1 — DOMCrawlerService unit tests
# ---------------------------------------------------------------------------

class TestDOMCrawlerService:

    @pytest.mark.asyncio
    async def test_start_crawl_inserts_and_returns_pending(self):
        # Proves: valid start_crawl with no conflict → INSERT executed, status='pending' returned, db.commit called once.
        svc = DOMCrawlerService()
        mock_db = _make_mock_db(conflict_row=None)

        result = await svc.start_crawl(
            db=mock_db,
            schema_name="tenant_test",
            project_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            target_url="https://app.example.com",
            auth_config=None,
        )

        assert result["status"] == "pending"
        assert result["target_url"] == "https://app.example.com"
        assert result["pages_crawled"] == 0
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_crawl_conflict_when_active_exists(self):
        # Proves: active crawl session found → raises HTTP 409 CRAWL_ALREADY_ACTIVE.
        svc = DOMCrawlerService()
        fake_row = {"id": str(uuid.uuid4())}
        mock_db = _make_mock_db(conflict_row=fake_row)

        with pytest.raises(HTTPException) as exc_info:
            await svc.start_crawl(
                db=mock_db,
                schema_name="tenant_test",
                project_id=str(uuid.uuid4()),
                user_id=str(uuid.uuid4()),
                target_url="https://app.example.com",
                auth_config=None,
            )

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["error"] == "CRAWL_ALREADY_ACTIVE"

    @pytest.mark.asyncio
    async def test_get_crawl_returns_session(self):
        # Proves: existing crawl session returned as dict with expected fields.
        svc = DOMCrawlerService()
        cid = str(uuid.uuid4())
        pid = str(uuid.uuid4())
        row = _make_session_row(crawl_id=cid, project_id=pid, status="completed")
        mock_db = _make_mock_db(session_row=row)

        result = await svc.get_crawl(
            db=mock_db,
            schema_name="tenant_test",
            project_id=pid,
            crawl_id=cid,
        )

        assert result["id"] == cid
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_get_crawl_raises_404_when_not_found(self):
        # Proves: missing crawl session → raises HTTP 404 CRAWL_NOT_FOUND.
        svc = DOMCrawlerService()
        mock_db = _make_mock_db(session_row=None)

        with pytest.raises(HTTPException) as exc_info:
            await svc.get_crawl(
                db=mock_db,
                schema_name="tenant_test",
                project_id=str(uuid.uuid4()),
                crawl_id=str(uuid.uuid4()),
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["error"] == "CRAWL_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_list_crawls_returns_sessions(self):
        # Proves: list_crawls returns all rows from DB as list of dicts.
        svc = DOMCrawlerService()
        rows = [_make_session_row(status="completed"), _make_session_row(status="pending")]
        mock_db = _make_mock_db(session_rows=rows)

        result = await svc.list_crawls(
            db=mock_db,
            schema_name="tenant_test",
            project_id=str(uuid.uuid4()),
        )

        assert len(result) == 2


# ---------------------------------------------------------------------------
# Task 2 — crawl_task unit tests
# ---------------------------------------------------------------------------

class TestCrawlTask:

    @pytest.mark.asyncio
    async def test_crawl_task_success(self):
        # Proves: successful run_crawl → DB updated to status='completed' with counts; commit called twice (running + completed).
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock())

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        page = PageData(url="https://app.example.com", title="Home", form_count=1, link_count=5, text_preview="hello")
        fake_result = CrawlResult(pages_crawled=2, forms_found=1, links_found=5, crawl_data=[page])

        with patch("src.services.dom_crawler_service.AsyncSessionLocal", return_value=mock_ctx):
            with patch("src.services.dom_crawler_service.run_crawl", new_callable=AsyncMock, return_value=fake_result):
                await crawl_task(
                    crawl_id=str(uuid.uuid4()),
                    schema_name="tenant_test",
                    tenant_id=str(uuid.uuid4()),
                    target_url="https://app.example.com",
                    auth_config_db=None,
                )

        # running + completed: 2 commits
        assert mock_db.commit.call_count == 2
        all_sql = " ".join(str(c.args[0]).lower() for c in mock_db.execute.call_args_list)
        assert "completed" in all_sql

    @pytest.mark.asyncio
    async def test_crawl_task_timeout(self):
        # Proves: asyncio.TimeoutError from run_crawl → DB status set to 'timeout'.
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock())

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.dom_crawler_service.AsyncSessionLocal", return_value=mock_ctx):
            with patch("src.services.dom_crawler_service.run_crawl", new_callable=AsyncMock, side_effect=asyncio.TimeoutError()):
                await crawl_task(
                    crawl_id=str(uuid.uuid4()),
                    schema_name="tenant_test",
                    tenant_id=str(uuid.uuid4()),
                    target_url="https://app.example.com",
                    auth_config_db=None,
                )

        all_sql = " ".join(str(c.args[0]).lower() for c in mock_db.execute.call_args_list)
        assert "timeout" in all_sql

    @pytest.mark.asyncio
    async def test_crawl_task_failure(self):
        # Proves: RuntimeError from run_crawl → DB status set to 'failed' with error_message containing exception text.
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock())

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.dom_crawler_service.AsyncSessionLocal", return_value=mock_ctx):
            with patch("src.services.dom_crawler_service.run_crawl", new_callable=AsyncMock, side_effect=RuntimeError("browser crash")):
                await crawl_task(
                    crawl_id=str(uuid.uuid4()),
                    schema_name="tenant_test",
                    tenant_id=str(uuid.uuid4()),
                    target_url="https://app.example.com",
                    auth_config_db=None,
                )

        all_sql = " ".join(str(c.args[0]).lower() for c in mock_db.execute.call_args_list)
        assert "failed" in all_sql
        # error_message passed as positional param dict → check args
        all_args = " ".join(str(c.args) for c in mock_db.execute.call_args_list)
        assert "browser crash" in all_args

    @pytest.mark.asyncio
    async def test_crawl_task_running_never_terminal(self):
        # Proves: even on unexpected Exception, DB is always updated from 'running' (never left terminal).
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock())

        mock_ctx = MagicMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_db)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("src.services.dom_crawler_service.AsyncSessionLocal", return_value=mock_ctx):
            with patch("src.services.dom_crawler_service.run_crawl", new_callable=AsyncMock, side_effect=ValueError("unexpected")):
                await crawl_task(
                    crawl_id=str(uuid.uuid4()),
                    schema_name="tenant_test",
                    tenant_id=str(uuid.uuid4()),
                    target_url="https://app.example.com",
                    auth_config_db=None,
                )

        # Must commit twice: running + failed (never just one commit leaving status=running)
        assert mock_db.commit.call_count == 2


# ---------------------------------------------------------------------------
# Task 1.2 — Fernet roundtrip test
# ---------------------------------------------------------------------------

def test_encrypt_decrypt_roundtrip():
    # Proves: encrypt then decrypt a password returns the original plaintext unchanged.
    original = "supersecret!Password123"
    encrypted = _encrypt_password(original)

    assert encrypted != original
    assert _decrypt_password(encrypted) == original
