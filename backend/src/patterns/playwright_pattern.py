"""
QUALISYS — Playwright DOM Crawl Pattern Spike
Epic 2 / C2 (Retro 2026-02-26): Approved pattern for headless DOM crawling.

CONTRACT — every DOM crawl in Epic 2 MUST follow this pattern:

RESOURCE LIMITS (non-negotiable):
    max_pages   : 100 pages per crawl session (configurable, default 100)
    timeout_ms  : 1_800_000 ms = 30 minutes (entire crawl, not per page)
    page_timeout: 30_000 ms = 30 seconds per-page navigation timeout

SUBPROCESS MODEL:
    Playwright is run via async_playwright() context manager.
    The browser is a managed resource — ALWAYS use try/finally to ensure browser.close().
    Spawning Playwright as a separate OS process (via asyncio.subprocess) is NOT used;
    the async API is sufficient for the MVP and avoids IPC overhead.

AUTH FLOW (optional):
    If CrawlConfig.auth_config is provided, the crawler logs in on the first page before
    starting BFS traversal. Credentials are NEVER logged.

BFS ALGORITHM:
    1. Start from target_url, add to visited set.
    2. For each page: extract all same-origin <a href> links.
    3. Enqueue unvisited same-origin links up to max_pages.
    4. Record page title, URL, form count, and link count per page.
    5. Capture page DOM summary (title + text content truncated to 2000 chars).

OUTPUT:
    CrawlResult with pages_crawled, forms_found, links_found, crawl_data (list of PageData)

Tenant isolation:
    The crawl itself is stateless with respect to tenants.
    The CALLER must:
      - Store CrawlResult in the correct tenant schema (crawl_sessions table)
      - Decrypt auth credentials before passing to run_crawl()
      - Enforce max_pages against the tenant's plan limit (not done here)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urljoin, urlparse

# ---------------------------------------------------------------------------
# Configuration and result types
# ---------------------------------------------------------------------------

@dataclass
class AuthConfig:
    """
    Optional authentication configuration for crawling behind a login wall.
    Credentials must be decrypted by the caller before passing here.
    """
    login_url:          str
    username_selector:  str   # CSS selector for the username/email field
    password_selector:  str   # CSS selector for the password field
    submit_selector:    str   # CSS selector for the submit button
    username:           str   # plaintext (caller decrypts from DB)
    password:           str   # plaintext (caller decrypts from DB)
    post_login_url:     Optional[str] = None  # URL to verify login succeeded


@dataclass
class PageData:
    """Captured summary for a single crawled page."""
    url:          str
    title:        str
    form_count:   int
    link_count:   int
    text_preview: str  # First 2000 chars of visible text content


@dataclass
class CrawlResult:
    """Output of a successful (or partially successful) crawl run."""
    pages_crawled: int
    forms_found:   int
    links_found:   int
    crawl_data:    list[PageData] = field(default_factory=list)
    error_message: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.error_message is None


@dataclass
class CrawlConfig:
    """Input configuration for run_crawl()."""
    target_url:   str
    max_pages:    int             = 100
    timeout_ms:   int             = 1_800_000  # 30 minutes
    page_timeout: int             = 30_000     # 30 seconds per-page
    auth_config:  Optional[AuthConfig] = None


# ---------------------------------------------------------------------------
# Main crawl function
# ---------------------------------------------------------------------------

async def run_crawl(config: CrawlConfig) -> CrawlResult:
    """
    Perform a headless BFS DOM crawl using Playwright.

    Args:
        config: CrawlConfig with target URL, limits, and optional auth.

    Returns:
        CrawlResult with page summaries and aggregate counts.

    Raises:
        asyncio.TimeoutError: If the overall crawl exceeds config.timeout_ms.
        Exception:            On browser launch failure (Playwright not installed).
    """
    try:
        from playwright.async_api import async_playwright  # deferred import
    except ImportError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: playwright install chromium"
        ) from exc

    async def _crawl() -> CrawlResult:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                return await _execute_bfs(browser, config)
            finally:
                await browser.close()

    return await asyncio.wait_for(
        _crawl(),
        timeout=config.timeout_ms / 1000.0,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _execute_bfs(browser: object, config: CrawlConfig) -> CrawlResult:  # type: ignore[type-arg]
    """BFS crawl logic. Runs inside the browser context."""
    from playwright.async_api import Browser  # type: ignore[import]

    context = await browser.new_context()  # type: ignore[attr-defined]
    page    = await context.new_page()

    # ------------------------------------------------------------------
    # Auth flow (optional)
    # ------------------------------------------------------------------
    if config.auth_config:
        await _perform_login(page, config.auth_config, config.page_timeout)

    # ------------------------------------------------------------------
    # BFS traversal
    # ------------------------------------------------------------------
    origin  = _origin(config.target_url)
    queue   = [config.target_url]
    visited: set[str] = set()
    pages_data: list[PageData] = []
    total_forms  = 0
    total_links  = 0

    while queue and len(visited) < config.max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            await page.goto(url, timeout=config.page_timeout, wait_until="domcontentloaded")
        except Exception:  # noqa: BLE001
            # Skip pages that fail to load (redirects, auth-gated, errors)
            continue

        # Extract page data
        title      = await page.title()
        text_raw   = await page.inner_text("body") if await page.query_selector("body") else ""
        text_preview = text_raw[:2000]
        forms      = await page.query_selector_all("form")
        links      = await page.query_selector_all("a[href]")

        # Collect same-origin hrefs
        for link_el in links:
            href = await link_el.get_attribute("href")
            if href:
                abs_url = urljoin(url, href).split("#")[0]  # strip fragments
                if _origin(abs_url) == origin and abs_url not in visited:
                    queue.append(abs_url)

        page_data = PageData(
            url=url,
            title=title,
            form_count=len(forms),
            link_count=len(links),
            text_preview=text_preview,
        )
        pages_data.append(page_data)
        total_forms += len(forms)
        total_links += len(links)

    await context.close()

    return CrawlResult(
        pages_crawled=len(visited),
        forms_found=total_forms,
        links_found=total_links,
        crawl_data=pages_data,
    )


async def _perform_login(page: object, auth: AuthConfig, timeout: int) -> None:  # type: ignore[type-arg]
    """Fill and submit a login form. Credentials are never logged."""
    await page.goto(auth.login_url, timeout=timeout)  # type: ignore[attr-defined]
    await page.fill(auth.username_selector, auth.username, timeout=timeout)  # type: ignore[attr-defined]
    await page.fill(auth.password_selector, auth.password, timeout=timeout)  # type: ignore[attr-defined]
    await page.click(auth.submit_selector, timeout=timeout)  # type: ignore[attr-defined]

    if auth.post_login_url:
        await page.wait_for_url(auth.post_login_url, timeout=timeout)  # type: ignore[attr-defined]


def _origin(url: str) -> str:
    """Extract scheme + netloc (origin) from a URL for same-origin filtering."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"
