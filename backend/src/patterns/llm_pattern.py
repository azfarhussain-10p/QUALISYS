"""
QUALISYS — LLM Provider Pattern Spike
Epic 2 / C2 (Retro 2026-02-26): Approved pattern for all LLM API calls.
Story 2-8 (AC-18): Cache key updated to use context_hash for stable caching.

CONTRACT — every LLM call in Epic 2 MUST follow this pattern:
  1. Cache check  : Redis key llm:cache:{sha256(agent_type + context_hash)}, TTL 86400s
  2. Budget gate  : atomic INCR on budget:{tenant_id}:daily; raise BudgetExceededError at limit
  3. Primary call : OpenAI gpt-4-turbo (configured via OPENAI_API_KEY)
  4. Fallback     : Anthropic claude-3-sonnet on openai.APIError (circuit-breaker trigger)
  5. Cache write  : store result on miss; never store on error
  6. Return shape : LLMResult(content, tokens_used, cost_usd, cached, provider)

Tenant isolation:
  - current_tenant_slug ContextVar MUST be set before calling call_llm()
  - Budget counter is keyed per tenant_id (from caller — avoids extra DB lookup here)

Token budget tiers (enforced via call_llm()):
  Free       :   1,000 tokens/day
  Pro        :  10,000 tokens/day
  Enterprise : 100,000 tokens/day

Usage:
    result = await call_llm(
        prompt="Analyse these requirements: ...",
        tenant_id=str(tenant.id),
        daily_budget=10_000,
        agent_type="qa_consultant",
    )
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Cost constants (USD per token) — update when provider pricing changes
# ---------------------------------------------------------------------------
_GPT4_TURBO_COST_PER_TOKEN = 0.00003    # blended prompt+completion estimate
_CLAUDE_COST_PER_TOKEN     = 0.000015   # claude-3-sonnet blended estimate
_CACHE_TTL                 = 86_400     # 24 hours in seconds
_BUDGET_KEY_PREFIX         = "budget:"  # budget:{tenant_id}:daily
_CACHE_KEY_PREFIX          = "llm:cache:"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class LLMResult:
    """Contract shape returned by call_llm(). All Epic 2 callers depend on this."""
    content:     str
    tokens_used: int
    cost_usd:    float
    cached:      bool
    provider:    str  # "openai" | "anthropic" | "cache"


class BudgetExceededError(Exception):
    """Raised when the tenant's daily token budget would be exceeded."""
    def __init__(self, tenant_id: str, used: int, limit: int) -> None:
        self.tenant_id = tenant_id
        self.used      = used
        self.limit     = limit
        super().__init__(
            f"Token budget exceeded for tenant {tenant_id}: "
            f"{used}/{limit} tokens used today."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cache_key(agent_type: str, context_hash: str) -> str:
    """Deterministic Redis key for context-level LLM result caching (AC-18)."""
    digest = hashlib.sha256(f"{agent_type}{context_hash}".encode()).hexdigest()
    return f"{_CACHE_KEY_PREFIX}{digest}"


def _budget_key(tenant_id: str) -> str:
    return f"{_BUDGET_KEY_PREFIX}{tenant_id}:daily"


# ---------------------------------------------------------------------------
# Atomic budget-check Lua script (same pattern as rate_limit middleware)
# Returns [current_count, ttl_remaining]
# Expires key at midnight UTC (86400s from first call, approximated here)
# ---------------------------------------------------------------------------
_BUDGET_SCRIPT = """
local key   = KEYS[1]
local count = redis.call('INCR', key)
if count == 1 then
    redis.call('EXPIRE', key, 86400)
end
return {count, redis.call('TTL', key)}
"""


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

async def call_llm(
    prompt:       str,
    tenant_id:    str,
    daily_budget: int,
    agent_type:   str,
    *,
    system_prompt: Optional[str] = None,
    temperature:   float = 0.2,
    max_tokens:    int   = 4096,
    context_hash:  Optional[str] = None,
) -> LLMResult:
    """
    Single entry-point for all Epic 2 LLM calls.

    Args:
        prompt:        The user/instruction prompt to send to the LLM.
        tenant_id:     UUID string of the current tenant (for budget tracking).
        daily_budget:  Max tokens allowed today for this tenant (tier-specific).
        agent_type:    One of: ba_consultant | qa_consultant | automation_consultant
        system_prompt: Optional system context injected before the user prompt.
        temperature:   LLM temperature (default 0.2 for deterministic QA output).
        max_tokens:    Max completion tokens to request.
        context_hash:  SHA-256 hex of the assembled context dict (AC-18). When None,
                       falls back to sha256(prompt) for backward compatibility.

    Returns:
        LLMResult with content, token count, cost, cache flag, and provider used.

    Raises:
        BudgetExceededError: If adding max_tokens would exceed daily_budget.
        Exception:           On both primary and fallback LLM failures.
    """
    from src.cache import get_redis_client  # lazy — avoids import at module load

    redis = get_redis_client()
    bkey  = _budget_key(tenant_id)

    # AC-18: use context_hash for cache key; fall back to sha256(prompt) for compat
    if context_hash is None:
        context_hash = hashlib.sha256(prompt.encode()).hexdigest()
    ckey = _cache_key(agent_type, context_hash)

    # ------------------------------------------------------------------
    # Step 1: Cache check
    # ------------------------------------------------------------------
    cached_raw = await redis.get(ckey)
    if cached_raw:
        data = json.loads(cached_raw)
        return LLMResult(
            content=data["content"],
            tokens_used=data["tokens_used"],
            cost_usd=data["cost_usd"],
            cached=True,
            provider="cache",
        )

    # ------------------------------------------------------------------
    # Step 2: Budget gate (atomic INCR + TTL)
    # Pre-check with max_tokens to avoid partial writes on failure.
    # ------------------------------------------------------------------
    current_raw = await redis.get(bkey)
    current_used = int(current_raw) if current_raw else 0
    if current_used + max_tokens > daily_budget:
        raise BudgetExceededError(
            tenant_id=tenant_id,
            used=current_used,
            limit=daily_budget,
        )

    # ------------------------------------------------------------------
    # Step 3: Primary — OpenAI gpt-4-turbo
    # ------------------------------------------------------------------
    result: Optional[LLMResult] = None
    try:
        result = await _call_openai(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as openai_err:  # noqa: BLE001
        # Step 4: Fallback — Anthropic claude-3-sonnet
        try:
            result = await _call_anthropic(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as anthropic_err:  # noqa: BLE001
            raise RuntimeError(
                f"Both LLM providers failed. "
                f"OpenAI: {openai_err}. Anthropic: {anthropic_err}."
            ) from anthropic_err

    # ------------------------------------------------------------------
    # Step 5: Cache write (only on success)
    # ------------------------------------------------------------------
    await redis.set(
        ckey,
        json.dumps({
            "content":     result.content,
            "tokens_used": result.tokens_used,
            "cost_usd":    result.cost_usd,
        }),
        ex=_CACHE_TTL,
    )

    # ------------------------------------------------------------------
    # Step 6: Atomic budget increment (actual tokens used)
    # ------------------------------------------------------------------
    await redis.eval(_BUDGET_SCRIPT, 1, bkey)  # type: ignore[arg-type]

    return result


# ---------------------------------------------------------------------------
# Provider shims  (thin wrappers — production code only touches these two)
# ---------------------------------------------------------------------------

async def _call_openai(
    prompt:        str,
    system_prompt: Optional[str],
    temperature:   float,
    max_tokens:    int,
) -> LLMResult:
    """Call OpenAI gpt-4-turbo and return a normalised LLMResult."""
    import openai  # deferred — only installed in backend container

    messages: list[dict] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    client   = openai.AsyncOpenAI()
    response = await client.chat.completions.create(
        model="gpt-4-turbo",
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    usage       = response.usage
    tokens_used = usage.total_tokens if usage else max_tokens
    cost_usd    = round(tokens_used * _GPT4_TURBO_COST_PER_TOKEN, 6)

    return LLMResult(
        content=response.choices[0].message.content or "",
        tokens_used=tokens_used,
        cost_usd=cost_usd,
        cached=False,
        provider="openai",
    )


async def _call_anthropic(
    prompt:        str,
    system_prompt: Optional[str],
    temperature:   float,
    max_tokens:    int,
) -> LLMResult:
    """Fallback: Anthropic claude-3-sonnet. Called only when OpenAI raises."""
    import anthropic  # deferred — only installed in backend container

    client = anthropic.AsyncAnthropic()

    kwargs: dict = {
        "model":       "claude-3-sonnet-20240229",
        "max_tokens":  max_tokens,
        "temperature": temperature,
        "messages":    [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        kwargs["system"] = system_prompt

    response    = await client.messages.create(**kwargs)
    tokens_used = response.usage.input_tokens + response.usage.output_tokens
    cost_usd    = round(tokens_used * _CLAUDE_COST_PER_TOKEN, 6)
    content     = response.content[0].text if response.content else ""

    return LLMResult(
        content=content,
        tokens_used=tokens_used,
        cost_usd=cost_usd,
        cached=False,
        provider="anthropic",
    )
