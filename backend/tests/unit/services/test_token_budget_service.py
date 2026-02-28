"""
Unit tests — TokenBudgetService
Story: 2-2-vector-embeddings-generation, 2-8-agent-execution-engine
Task 5.2 — 3 tests covering consume_tokens and get_monthly_usage.
Story 2-8 — 4 tests covering check_budget() (AC-17).
DoD A6: every test has a one-line comment stating the BEHAVIOUR proved.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.patterns.llm_pattern import BudgetExceededError
from src.services.token_budget_service import TokenBudgetService, _MONTHLY_TTL_SECONDS


class TestTokenBudgetService:

    def setup_method(self):
        self.svc = TokenBudgetService()

    @pytest.mark.asyncio
    async def test_consume_tokens_returns_total(self):
        # Proves: consume_tokens returns the new cumulative monthly total from Redis eval.
        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(return_value=[5000, _MONTHLY_TTL_SECONDS])

        with patch("src.services.token_budget_service.get_redis_client", return_value=mock_redis):
            total = await self.svc.consume_tokens("tenant-abc", 500)

        assert total == 5000
        mock_redis.eval.assert_called_once()
        # Verify the correct delta was passed
        call_args = mock_redis.eval.call_args
        assert call_args[0][3] == "500"

    @pytest.mark.asyncio
    async def test_consume_tokens_sets_ttl_on_first_call(self):
        # Proves: the Lua script receives the 30-day TTL constant as ARGV[2].
        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(return_value=[100, _MONTHLY_TTL_SECONDS])

        with patch("src.services.token_budget_service.get_redis_client", return_value=mock_redis):
            await self.svc.consume_tokens("tenant-xyz", 100)

        call_args = mock_redis.eval.call_args
        assert call_args[0][4] == str(_MONTHLY_TTL_SECONDS)

    @pytest.mark.asyncio
    async def test_get_monthly_usage_returns_zero_when_missing(self):
        # Proves: get_monthly_usage returns 0 when Redis key does not exist.
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=None)

        with patch("src.services.token_budget_service.get_redis_client", return_value=mock_redis):
            usage = await self.svc.get_monthly_usage("tenant-new")

        assert usage == 0

    @pytest.mark.asyncio
    async def test_get_monthly_usage_returns_value_when_set(self):
        # Proves: get_monthly_usage returns the integer stored in Redis for the tenant.
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=b"12345")

        with patch("src.services.token_budget_service.get_redis_client", return_value=mock_redis):
            usage = await self.svc.get_monthly_usage("tenant-abc")

        assert usage == 12345

    @pytest.mark.asyncio
    async def test_consume_zero_tokens_does_not_incr(self):
        # Proves: consuming 0 tokens skips the Redis eval and returns current usage via GET.
        mock_redis = MagicMock()
        mock_redis.eval = AsyncMock(return_value=[0, 0])
        mock_redis.get  = AsyncMock(return_value=b"999")

        with patch("src.services.token_budget_service.get_redis_client", return_value=mock_redis):
            usage = await self.svc.consume_tokens("tenant-abc", 0)

        mock_redis.eval.assert_not_called()
        assert usage == 999

    # ------------------------------------------------------------------
    # Story 2-8 (AC-17) — check_budget() tests
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_check_budget_within_limit(self):
        # Proves: budget within limit (5k of 100k) does not raise and returns None.
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=b"5000")

        with patch("src.services.token_budget_service.get_redis_client", return_value=mock_redis):
            result = await self.svc.check_budget("tenant-ok", 100_000)

        assert result is None

    @pytest.mark.asyncio
    async def test_check_budget_at_limit(self):
        # Proves: usage exactly at monthly_limit raises BudgetExceededError.
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=b"100000")

        with patch("src.services.token_budget_service.get_redis_client", return_value=mock_redis):
            with pytest.raises(BudgetExceededError) as exc_info:
                await self.svc.check_budget("tenant-full", 100_000)

        err = exc_info.value
        assert err.used == 100_000
        assert err.limit == 100_000

    @pytest.mark.asyncio
    async def test_check_budget_over_limit(self):
        # Proves: usage exceeding monthly_limit raises BudgetExceededError with correct attributes.
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=b"110000")

        with patch("src.services.token_budget_service.get_redis_client", return_value=mock_redis):
            with pytest.raises(BudgetExceededError) as exc_info:
                await self.svc.check_budget("tenant-over", 100_000)

        err = exc_info.value
        assert err.used == 110_000
        assert err.limit == 100_000

    @pytest.mark.asyncio
    async def test_check_budget_80_percent_logs_warning(self):
        # Proves: usage at 80% threshold logs a structured warning without raising.
        mock_redis = MagicMock()
        mock_redis.get = AsyncMock(return_value=b"80000")

        with patch("src.services.token_budget_service.get_redis_client", return_value=mock_redis), \
             patch("src.services.token_budget_service.logger") as mock_logger:
            result = await self.svc.check_budget("tenant-warn", 100_000)

        assert result is None
        mock_logger.warning.assert_called_once()
        call_kwargs = mock_logger.warning.call_args
        assert call_kwargs[1]["tenant_id"] == "tenant-warn"
        assert call_kwargs[1]["usage"] == 80_000
        assert call_kwargs[1]["limit"] == 100_000
        assert call_kwargs[1]["pct"] == 80.0
