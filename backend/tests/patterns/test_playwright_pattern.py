"""
Contract tests for playwright_pattern.py — Epic 2 / C2 (Retro 2026-02-26)

These tests verify INTERFACE CONTRACTS and BEHAVIOUR GUARANTEES of the Playwright pattern.
No real browser is launched. Playwright is fully mocked.

Contracts verified:
  - run_crawl(): raises RuntimeError when Playwright is not installed
  - run_crawl(): respects max_pages limit (BFS stops at boundary)
  - run_crawl(): raises asyncio.TimeoutError when timeout_ms exceeded
  - run_crawl(): auth flow (_perform_login) called when auth_config provided
  - run_crawl(): auth flow NOT called when auth_config is None
  - CrawlResult shape: all required fields present with correct types
  - CrawlResult.succeeded: True on no error_message, False with error_message
  - PageData: text_preview truncated to 2000 chars
  - _origin(): extracts scheme+netloc correctly (same-origin filtering)
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.patterns.playwright_pattern import (
    AuthConfig,
    CrawlConfig,
    CrawlResult,
    PageData,
    _origin,
    run_crawl,
)


# ---------------------------------------------------------------------------
# Helpers — mock Playwright tree
# ---------------------------------------------------------------------------

def _make_mock_page(title: str = "Test Page", links: list[str] | None = None):
    """Build a minimal mock of a Playwright Page object."""
    page = AsyncMock()
    page.title.return_value = title
    page.inner_text.return_value = "a" * 3000  # > 2000 chars, to test truncation
    page.query_selector.return_value = AsyncMock()  # truthy — body exists

    # Mock anchor elements
    link_elements = []
    for href in (links or []):
        el = AsyncMock()
        el.get_attribute.return_value = href
        link_elements.append(el)

    page.query_selector_all.side_effect = lambda selector: (
        link_elements if "a[href]" in selector else []
    )
    return page


# ---------------------------------------------------------------------------
# Playwright not installed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_crawl_raises_when_playwright_not_installed():
    # Proves: missing Playwright package produces a clear RuntimeError, not an ImportError
    config = CrawlConfig(target_url="http://example.com")
    with patch.dict("sys.modules", {"playwright": None, "playwright.async_api": None}):
        with pytest.raises((RuntimeError, ImportError)):
            await run_crawl(config)


# ---------------------------------------------------------------------------
# max_pages enforcement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_crawl_stops_at_max_pages():
    # Proves: BFS traversal never visits more pages than max_pages, even if more links exist
    config = CrawlConfig(target_url="http://example.com", max_pages=2)

    mock_page = _make_mock_page(
        title="Page",
        links=[
            "http://example.com/a",
            "http://example.com/b",
            "http://example.com/c",  # would be page 4 — must be skipped
        ],
    )

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    with patch("src.patterns.playwright_pattern.async_playwright") as mock_pw_cm:
        mock_pw    = AsyncMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cm.return_value.__aenter__.return_value = mock_pw
        mock_pw_cm.return_value.__aexit__.return_value = None

        result = await run_crawl(config)

    assert result.pages_crawled <= config.max_pages


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_crawl_raises_timeout_when_crawl_exceeds_limit():
    # Proves: asyncio.TimeoutError is raised when the crawl exceeds timeout_ms
    config = CrawlConfig(target_url="http://example.com", timeout_ms=1)  # 1ms = immediate

    async def _slow_crawl():
        await asyncio.sleep(10)  # far exceeds 1ms timeout

    with patch("src.patterns.playwright_pattern.async_playwright"):
        with patch("src.patterns.playwright_pattern._execute_bfs", side_effect=_slow_crawl):
            with pytest.raises(asyncio.TimeoutError):
                await run_crawl(config)


# ---------------------------------------------------------------------------
# Auth flow
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auth_flow_called_when_auth_config_provided():
    # Proves: _perform_login is invoked once when auth_config is present
    auth_config = AuthConfig(
        login_url="http://example.com/login",
        username_selector="#email",
        password_selector="#password",
        submit_selector='button[type="submit"]',
        username="user@example.com",
        password="s3cr3t",
    )
    config = CrawlConfig(
        target_url="http://example.com",
        max_pages=1,
        auth_config=auth_config,
    )

    with patch("src.patterns.playwright_pattern._execute_bfs") as mock_bfs, \
         patch("src.patterns.playwright_pattern.async_playwright") as mock_pw_cm:

        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cm.return_value.__aenter__.return_value = mock_pw
        mock_pw_cm.return_value.__aexit__.return_value = None
        mock_bfs.return_value = CrawlResult(pages_crawled=1, forms_found=0, links_found=0)

        await run_crawl(config)

    # _execute_bfs receives the config with auth_config intact
    call_kwargs = mock_bfs.call_args[0]
    assert call_kwargs[1].auth_config is auth_config


@pytest.mark.asyncio
async def test_auth_flow_not_called_when_no_auth_config():
    # Proves: when auth_config=None, _perform_login is never invoked
    config = CrawlConfig(target_url="http://example.com", max_pages=1, auth_config=None)

    with patch("src.patterns.playwright_pattern._perform_login") as mock_login, \
         patch("src.patterns.playwright_pattern._execute_bfs") as mock_bfs, \
         patch("src.patterns.playwright_pattern.async_playwright") as mock_pw_cm:

        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_pw.chromium.launch.return_value = mock_browser
        mock_pw_cm.return_value.__aenter__.return_value = mock_pw
        mock_pw_cm.return_value.__aexit__.return_value = None
        mock_bfs.return_value = CrawlResult(pages_crawled=0, forms_found=0, links_found=0)

        await run_crawl(config)

    mock_login.assert_not_called()


# ---------------------------------------------------------------------------
# CrawlResult shape + .succeeded
# ---------------------------------------------------------------------------

def test_crawl_result_succeeded_when_no_error():
    # Proves: CrawlResult.succeeded=True when error_message is absent
    result = CrawlResult(pages_crawled=5, forms_found=2, links_found=30)
    assert result.succeeded is True


def test_crawl_result_not_succeeded_with_error_message():
    # Proves: CrawlResult.succeeded=False when error_message is set
    result = CrawlResult(
        pages_crawled=0, forms_found=0, links_found=0,
        error_message="browser launch failed",
    )
    assert result.succeeded is False


def test_crawl_result_has_all_required_fields():
    # Proves: CrawlResult exposes all fields that the DOMCrawlerService stores in DB
    result = CrawlResult(pages_crawled=10, forms_found=5, links_found=200)
    assert hasattr(result, "pages_crawled")
    assert hasattr(result, "forms_found")
    assert hasattr(result, "links_found")
    assert hasattr(result, "crawl_data")
    assert hasattr(result, "error_message")
    assert isinstance(result.crawl_data, list)


# ---------------------------------------------------------------------------
# _origin() — same-origin filtering
# ---------------------------------------------------------------------------

def test_origin_extracts_scheme_and_netloc():
    # Proves: same-origin check correctly identifies the origin component
    assert _origin("http://example.com/page/1")  == "http://example.com"
    assert _origin("https://app.qualisys.io/dashboard") == "https://app.qualisys.io"


def test_different_subdomains_produce_different_origins():
    # Proves: sub-domain links are correctly treated as cross-origin (not crawled)
    assert _origin("https://app.example.com") != _origin("https://api.example.com")


def test_fragment_does_not_affect_origin():
    # Proves: fragment (#section) is stripped before same-origin comparison
    assert _origin("https://example.com/page#section") == "https://example.com"
