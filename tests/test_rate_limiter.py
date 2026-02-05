import asyncio
import time

import pytest

from polymarket_bot.utils.rate_limiter import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    RateLimiter,
    RetryableError,
    RetryConfig,
    retry_with_backoff,
)


@pytest.fixture
def rate_limiter():
    return RateLimiter(requests_per_second=10.0, burst_limit=20)

@pytest.fixture
def circuit_breaker():
    return CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)

class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_acquire_under_limit(self, rate_limiter):
        start = time.monotonic()
        for _ in range(5):
            await rate_limiter.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_remaining_capacity(self, rate_limiter):
        assert rate_limiter.remaining() == 10
        await rate_limiter.acquire()
        assert rate_limiter.remaining() == 9

class TestRetryWithBackoff:
    @pytest.mark.asyncio
    async def test_successful_call(self):
        call_count = 0

        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await retry_with_backoff(successful_func)
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self):
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("temporary failure")
            return "success"

        config = RetryConfig(max_attempts=5, base_delay=0.01)
        result = await retry_with_backoff(flaky_func, config=config)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise RetryableError("always fails")

        config = RetryConfig(max_attempts=3, base_delay=0.01)

        with pytest.raises(RetryableError):
            await retry_with_backoff(always_fails, config=config)

        assert call_count == 3

class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_closed_state(self, circuit_breaker):
        async def success():
            return "ok"

        result = await circuit_breaker.call(success)
        assert result == "ok"
        assert circuit_breaker.state == "closed"

    @pytest.mark.asyncio
    async def test_opens_after_failures(self, circuit_breaker):
        async def always_fails():
            raise RuntimeError("fail")

        for _ in range(3):
            with pytest.raises(RuntimeError, match="fail"):
                await circuit_breaker.call(always_fails)

        assert circuit_breaker.state == "open"

    @pytest.mark.asyncio
    async def test_rejects_when_open(self, circuit_breaker):
        async def always_fails():
            raise RuntimeError("fail")

        for _ in range(3):
            with pytest.raises(RuntimeError, match="fail"):
                await circuit_breaker.call(always_fails)

        async def would_succeed():
            return "ok"

        with pytest.raises(CircuitBreakerOpenError):
            await circuit_breaker.call(would_succeed)

    @pytest.mark.asyncio
    async def test_half_open_recovery(self, circuit_breaker):
        call_count = 0

        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise RuntimeError("fail")
            return "ok"

        for _ in range(3):
            with pytest.raises(RuntimeError, match="fail"):
                await circuit_breaker.call(flaky)

        assert circuit_breaker.state == "open"

        await asyncio.sleep(1.1)

        for _ in range(3):
            result = await circuit_breaker.call(flaky)
            assert result == "ok"

        assert circuit_breaker.state == "closed"
