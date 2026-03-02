# Integration Patterns

Canonical integration contracts for the four external systems used by QUALISYS AI agents. These patterns are **the single source of truth** for how the backend interacts with LLMs, pgvector, SSE streaming, and Playwright.

> **Architecture rule:** Do not call OpenAI, pgvector, SSE, or Playwright directly from services or agents. Always go through these patterns. Modifying a pattern requires architecture review.

---

## Pattern Files

| File | System | Entry Point |
|------|--------|-------------|
| `llm_pattern.py` | OpenAI / Anthropic | `call_llm(prompt, tenant_id, ...)` |
| `pgvector_pattern.py` | PostgreSQL + pgvector | `insert_embedding()`, `similarity_search()` |
| `sse_pattern.py` | Server-Sent Events | `build_sse_response(event_generator, run_id)` |
| `playwright_pattern.py` | Playwright (DOM crawling) | `run_crawl(config: CrawlConfig)` |

---

## LLM Pattern (`llm_pattern.py`)

**Entry point:** `call_llm(prompt, tenant_id, daily_budget, agent_type, ...) → LLMResult`

**Flow:**
1. Check Redis cache — key: `llm:cache:{sha256(agent_type + prompt)}`, TTL 86400s
2. Check daily budget gate — key: `budget:{tenant_id}:daily` (atomic Lua INCR)
3. Call OpenAI (primary) — `gpt-4o` with retry
4. Fall back to Anthropic on failure
5. Write result to cache

**Key types:**
```python
@dataclass
class LLMResult:
    content: str
    tokens_used: int
    cost_usd: float
    cached: bool
    provider: str   # "openai" | "anthropic"
```

**Raises:** `BudgetExceededError` when `current_used + max_tokens > daily_budget`.

---

## pgvector Pattern (`pgvector_pattern.py`)

**Entry points:**
- `insert_embedding(db, schema_name, chunk_id, embedding) → UUID`
- `similarity_search(db, schema_name, query_embedding, limit) → list[ChunkMatch]`

**Key constraints:**
- Embedding dimensions: **1536** (text-embedding-ada-002) — `ValueError` raised on mismatch
- Distance operator: `<=>` (cosine distance) via `ivfflat` index (`vector_cosine_ops`)
- All SQL uses double-quoted tenant schema: `text(f'... FROM "{schema_name}".table ...')`
- `CAST(:embedding AS vector)` required — asyncpg cannot serialise Python lists natively

```python
@dataclass
class ChunkMatch:
    chunk_id: UUID
    content: str
    similarity: float   # = 1.0 - (cosine_distance / 2.0)
```

---

## SSE Pattern (`sse_pattern.py`)

**Entry point:** `build_sse_response(event_generator, run_id, heartbeat_interval=15) → StreamingResponse`

**Wire format** — every event is a single `data:` line followed by `\n\n`:
```
data: {"type":"running","run_id":"<uuid>","payload":{...}}\n\n
```

**Valid event types:**

| Type | Meaning |
|------|---------|
| `queued` | Run accepted, waiting to start |
| `running` | Agent step in progress |
| `complete` | Run finished successfully |
| `error` | Run failed |
| `heartbeat` | Keep-alive (emitted every 15 s of silence) |

**Required headers** set automatically: `X-Accel-Buffering: no`, `Cache-Control: no-cache`, `media_type: text/event-stream`.

**Frontend usage:** Use native `EventSource` (not Axios):
```typescript
const es = new EventSource(`/api/v1/events/agent-runs/${runId}`, { withCredentials: true })
es.onmessage = (e) => { const event = JSON.parse(e.data); ... }
```

---

## Playwright Pattern (`playwright_pattern.py`)

**Entry point:** `run_crawl(config: CrawlConfig) → CrawlResult`

**Key limits:**

| Limit | Value |
|-------|-------|
| Max pages | 100 |
| Total timeout | 30 minutes (1,800,000 ms) |
| Per-page timeout | 30,000 ms |

**Behaviour:**
- BFS same-origin traversal — cross-origin links skipped
- URL fragments stripped before deduplication
- Optional auth flow: `auth_config` triggers `_perform_login()` before crawl
- Always closes browser in `try/finally`

```python
@dataclass
class CrawlConfig:
    url: str
    max_pages: int = 100
    auth_config: Optional[AuthConfig] = None

@dataclass
class CrawlResult:
    pages_crawled: int
    forms_found: int
    links_found: int
    crawl_data: dict
    error_message: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.error_message is None
```

---

## Pattern Contract Tests

Each pattern has a corresponding contract test in [`../../tests/patterns/`](../../tests/patterns/):

| Pattern | Test File |
|---------|-----------|
| LLM | `test_llm_pattern.py` |
| pgvector | `test_pgvector_pattern.py` |
| SSE | `test_sse_pattern.py` |
| Playwright | `test_playwright_pattern.py` |

Run them with:
```bash
python -m pytest tests/patterns/ -v
```

---

## Related Documentation

- [Backend README](../../README.md) — Full backend setup guide
- [Test Guide](../../tests/README.md) — How to run tests
- [Epic 2 Tech Spec](../../../../docs/stories/epic-2/tech-spec-epic-2.md) — Pattern usage in agent context
- [System Architecture](../../../../docs/architecture/architecture.md) — Architecture decisions
