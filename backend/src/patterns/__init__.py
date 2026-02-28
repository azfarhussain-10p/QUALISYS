"""
QUALISYS — Epic 2 Pattern Spikes
C2 (Retro 2026-02-26): Approved reference implementations for all Epic 2 novel patterns.

USAGE CONTRACT:
  Every Epic 2 service that touches LLM calls, pgvector, SSE streaming, or DOM crawling
  MUST match the pattern in the corresponding file. Deviations require explicit
  architectural sign-off and an updated spike file.

Files:
  llm_pattern.py       — LLM API call: cache → budget check → OpenAI → Anthropic fallback
  pgvector_pattern.py  — Vector insert + cosine similarity search (tenant-scoped)
  sse_pattern.py       — Server-Sent Events streaming via FastAPI StreamingResponse
  playwright_pattern.py — Playwright DOM crawl as managed async subprocess
"""
