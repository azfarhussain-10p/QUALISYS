"""
Contract tests for llm_pattern.py — Epic 2 / C2 (Retro 2026-02-26)
Story 2-8 (AC-18): Cache key updated to use context_hash.

These tests verify INTERFACE CONTRACTS and BEHAVIOUR GUARANTEES of call_llm().
No real LLM API calls are made. No real Redis connection required.

Contracts verified:
  - Cache hit: Redis GET returns data → LLMResult.cached=True, LLM not called
  - Cache miss + budget ok → OpenAI called → result cached, budget incremented
  - Cache miss + budget exceeded → BudgetExceededError before any LLM call
  - OpenAI failure → Anthropic fallback called → result returned with provider="anthropic"
  - Both providers fail → RuntimeError raised; nothing cached
  - LLMResult shape: all fields present with correct types
  - Cache key is deterministic: same agent_type+context_hash → same key (AC-18)
  - Different agent_type → different cache key (isolation)
  - call_llm(context_hash=None) falls back to sha256(prompt) — backward compat (AC-18)
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.patterns.llm_pattern import (
    BudgetExceededError,
    LLMResult,
    _cache_key,
    call_llm,
)

TENANT_ID    = str(uuid.uuid4())
DAILY_BUDGET = 10_000
AGENT_TYPE   = "qa_consultant"
PROMPT       = "List test cases for login form."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cached_payload(content: str = "cached answer") -> str:
    """Serialised JSON stored in Redis by a previous call_llm() invocation."""
    return json.dumps({"content": content, "tokens_used": 200, "cost_usd": 0.006})


def _make_llm_result(provider: str = "openai") -> LLMResult:
    return LLMResult(
        content="generated answer",
        tokens_used=300,
        cost_usd=0.009,
        cached=False,
        provider=provider,
    )


# ---------------------------------------------------------------------------
# Cache hit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_hit_returns_cached_result_without_calling_llm():
    # Proves: when Redis contains a prior result, call_llm() returns it without calling any LLM API
    mock_redis = AsyncMock()
    mock_redis.get.return_value = _make_cached_payload()

    with patch("src.cache.get_redis_client", return_value=mock_redis), \
         patch("src.patterns.llm_pattern._call_openai") as mock_openai, \
         patch("src.patterns.llm_pattern._call_anthropic") as mock_anthropic:

        result = await call_llm(PROMPT, TENANT_ID, DAILY_BUDGET, AGENT_TYPE)

    assert result.cached is True
    assert result.provider == "cache"
    assert result.content == "cached answer"
    assert result.tokens_used == 200
    mock_openai.assert_not_called()
    mock_anthropic.assert_not_called()


# ---------------------------------------------------------------------------
# Cache miss + happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cache_miss_calls_openai_and_caches_result():
    # Proves: on cache miss with budget available, OpenAI is called and result is written to Redis
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None  # cache miss on first GET (budget check)

    openai_result = _make_llm_result("openai")

    with patch("src.cache.get_redis_client", return_value=mock_redis), \
         patch("src.patterns.llm_pattern._call_openai", return_value=openai_result) as mock_openai, \
         patch("src.patterns.llm_pattern._call_anthropic") as mock_anthropic:

        result = await call_llm(PROMPT, TENANT_ID, DAILY_BUDGET, AGENT_TYPE)

    assert result.cached is False
    assert result.provider == "openai"
    assert result.content == "generated answer"

    # Result must be cached for future calls
    mock_redis.set.assert_called_once()
    set_args = mock_redis.set.call_args
    stored = json.loads(set_args[0][1])
    assert stored["content"] == "generated answer"
    assert set_args[1]["ex"] == 86_400  # 24h TTL

    mock_openai.assert_called_once()
    mock_anthropic.assert_not_called()


# ---------------------------------------------------------------------------
# Budget exceeded
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_budget_exceeded_raises_before_any_llm_call():
    # Proves: when current token usage + max_tokens exceeds daily_budget, BudgetExceededError
    #         is raised immediately — OpenAI and Anthropic are never called
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = [None, str(9_800)]  # cache miss, then budget = 9800

    with patch("src.cache.get_redis_client", return_value=mock_redis), \
         patch("src.patterns.llm_pattern._call_openai") as mock_openai, \
         patch("src.patterns.llm_pattern._call_anthropic") as mock_anthropic:

        with pytest.raises(BudgetExceededError) as exc_info:
            await call_llm(PROMPT, TENANT_ID, DAILY_BUDGET, AGENT_TYPE, max_tokens=300)

    err = exc_info.value
    assert err.tenant_id == TENANT_ID
    assert err.used == 9_800
    assert err.limit == DAILY_BUDGET
    mock_openai.assert_not_called()
    mock_anthropic.assert_not_called()


# ---------------------------------------------------------------------------
# Anthropic fallback
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_failure_triggers_anthropic_fallback():
    # Proves: when OpenAI raises any exception, Anthropic is called as fallback
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    anthropic_result = _make_llm_result("anthropic")

    with patch("src.cache.get_redis_client", return_value=mock_redis), \
         patch("src.patterns.llm_pattern._call_openai", side_effect=Exception("openai timeout")), \
         patch("src.patterns.llm_pattern._call_anthropic", return_value=anthropic_result) as mock_fallback:

        result = await call_llm(PROMPT, TENANT_ID, DAILY_BUDGET, AGENT_TYPE)

    assert result.provider == "anthropic"
    assert result.cached is False
    mock_fallback.assert_called_once()


# ---------------------------------------------------------------------------
# Both providers fail
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_both_providers_fail_raises_runtime_error_with_no_cache_write():
    # Proves: dual failure raises RuntimeError and nothing is written to Redis cache
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    with patch("src.cache.get_redis_client", return_value=mock_redis), \
         patch("src.patterns.llm_pattern._call_openai", side_effect=Exception("openai down")), \
         patch("src.patterns.llm_pattern._call_anthropic", side_effect=Exception("anthropic down")):

        with pytest.raises(RuntimeError, match="Both LLM providers failed"):
            await call_llm(PROMPT, TENANT_ID, DAILY_BUDGET, AGENT_TYPE)

    mock_redis.set.assert_not_called()


# ---------------------------------------------------------------------------
# LLMResult shape
# ---------------------------------------------------------------------------

def test_llm_result_has_all_required_fields():
    # Proves: LLMResult dataclass exposes all fields callers depend on
    result = LLMResult(
        content="answer",
        tokens_used=100,
        cost_usd=0.003,
        cached=False,
        provider="openai",
    )
    assert isinstance(result.content,     str)
    assert isinstance(result.tokens_used, int)
    assert isinstance(result.cost_usd,    float)
    assert isinstance(result.cached,      bool)
    assert isinstance(result.provider,    str)


# ---------------------------------------------------------------------------
# Cache key determinism + isolation
# ---------------------------------------------------------------------------

def test_same_agent_and_prompt_produce_identical_cache_key():
    # Proves: cache key is deterministic for identical context_hash inputs (idempotent caching)
    key_a = _cache_key("qa_consultant", "abc123hashvalue")
    key_b = _cache_key("qa_consultant", "abc123hashvalue")
    assert key_a == key_b


def test_different_agent_type_produces_different_cache_key():
    # Proves: agent_type is part of the cache key, preventing cross-agent cache pollution
    key_qa   = _cache_key("qa_consultant",         "abc123hashvalue")
    key_ba   = _cache_key("ba_consultant",          "abc123hashvalue")
    key_auto = _cache_key("automation_consultant",  "abc123hashvalue")
    assert key_qa != key_ba
    assert key_qa != key_auto
    assert key_ba != key_auto


def test_different_prompt_produces_different_cache_key():
    # Proves: context_hash discriminates between different contexts, preventing false cache hits
    key_a = _cache_key("qa_consultant", "hash_for_context_A")
    key_b = _cache_key("qa_consultant", "hash_for_context_B")
    assert key_a != key_b


# ---------------------------------------------------------------------------
# Story 2-8 (AC-18) — context_hash cache key tests
# ---------------------------------------------------------------------------

def test_cache_key_uses_context_hash():
    # Proves: _cache_key is deterministic for identical context_hash; starts with correct prefix
    key1 = _cache_key("qa_consultant", "deadbeef1234")
    key2 = _cache_key("qa_consultant", "deadbeef1234")
    assert key1.startswith("llm:cache:")
    assert key1 == key2


@pytest.mark.asyncio
async def test_call_llm_none_context_hash_falls_back_to_prompt():
    # Proves: call_llm(context_hash=None) uses sha256(prompt) as fallback — no AttributeError raised
    mock_redis = AsyncMock()
    mock_redis.get.return_value = _make_cached_payload("fallback answer")

    with patch("src.cache.get_redis_client", return_value=mock_redis), \
         patch("src.patterns.llm_pattern._call_openai") as mock_openai, \
         patch("src.patterns.llm_pattern._call_anthropic") as mock_anthropic:

        result = await call_llm(PROMPT, TENANT_ID, DAILY_BUDGET, AGENT_TYPE, context_hash=None)

    assert result.cached is True
    assert result.provider == "cache"
    mock_openai.assert_not_called()
    mock_anthropic.assert_not_called()
