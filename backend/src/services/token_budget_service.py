"""
QUALISYS — Token Budget Service
Story: 2-2-vector-embeddings-generation, 2-8-agent-execution-engine
AC: #8 — Token usage from embedding generation counted against tenant's monthly budget.
AC-17 — check_budget() enforces monthly hard limit; logs warning at 80%.

Redis key: budget:{tenant_id}:monthly
TTL:       2592000 seconds (≈30 days), set once on first INCR.
Pattern:   Atomic Lua script — identical to rate_limit middleware (no TOCTOU race).

Usage:
    total = await token_budget_service.consume_tokens(str(tenant_id), tokens_used)
    usage  = await token_budget_service.get_monthly_usage(str(tenant_id))
    await token_budget_service.check_budget(str(tenant_id), settings.monthly_token_budget)
"""

from __future__ import annotations

from src.cache import get_redis_client
from src.logger import logger
from src.patterns.llm_pattern import BudgetExceededError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MONTHLY_TTL_SECONDS = 2_592_000  # 30 days
_BUDGET_KEY_PREFIX   = "budget:"

# Atomic Lua: INCR key by delta, EXPIRE only on first call (count <= delta).
# Returns [new_total, ttl].
# NOTE: We INCR by `delta` (actual tokens) rather than 1 to match AC-08 semantics.
_CONSUME_SCRIPT = """
local key   = KEYS[1]
local delta = tonumber(ARGV[1])
local ttl   = tonumber(ARGV[2])
local count = redis.call('INCRBY', key, delta)
if count == delta then
    redis.call('EXPIRE', key, ttl)
end
return {count, redis.call('TTL', key)}
"""


def _monthly_key(tenant_id: str) -> str:
    return f"{_BUDGET_KEY_PREFIX}{tenant_id}:monthly"


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------

class TokenBudgetService:
    """
    Tracks per-tenant token consumption in Redis.
    check_budget() enforces the monthly hard limit (Story 2-8 AC-17).
    """

    async def consume_tokens(self, tenant_id: str, tokens: int) -> int:
        """
        Atomically increment the monthly token counter for `tenant_id` by `tokens`.
        Sets TTL on first write. Returns the new monthly total.
        """
        if tokens <= 0:
            return await self.get_monthly_usage(tenant_id)

        redis = get_redis_client()
        key   = _monthly_key(tenant_id)

        result = await redis.eval(  # type: ignore[arg-type]
            _CONSUME_SCRIPT,
            1,
            key,
            str(tokens),
            str(_MONTHLY_TTL_SECONDS),
        )
        new_total = int(result[0])

        logger.debug(
            "Token budget updated",
            tenant_id=tenant_id,
            tokens_added=tokens,
            monthly_total=new_total,
        )
        return new_total

    async def get_monthly_usage(self, tenant_id: str) -> int:
        """Return current monthly token usage for `tenant_id`. Returns 0 if not set."""
        redis = get_redis_client()
        raw   = await redis.get(_monthly_key(tenant_id))
        return int(raw) if raw else 0

    async def check_budget(self, tenant_id: str, monthly_limit: int) -> None:
        """
        AC-17: Check whether the tenant's monthly token usage has reached the hard limit.
        Logs a structured warning at 80%. Raises BudgetExceededError at 100%.
        """
        usage = await self.get_monthly_usage(tenant_id)
        pct = (usage / monthly_limit * 100) if monthly_limit else 0

        if usage >= monthly_limit:
            raise BudgetExceededError(tenant_id, usage, monthly_limit)

        if pct >= 80:
            logger.warning(
                "token_budget: 80% threshold reached",
                tenant_id=tenant_id,
                usage=usage,
                limit=monthly_limit,
                pct=round(pct, 1),
            )


# Module-level singleton
token_budget_service = TokenBudgetService()
