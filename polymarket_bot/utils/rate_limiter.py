import asyncio
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import wraps
from typing import ParamSpec, TypeVar

import structlog

log = structlog.get_logger()

P = ParamSpec('P')
T = TypeVar('T')

@dataclass
class RateLimiter:
    requests_per_second: float = 5.0
    burst_limit: int = 20
    _timestamps: deque = field(default_factory=deque)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            window_start = now - 1.0

            while self._timestamps and self._timestamps[0] < window_start:
                self._timestamps.popleft()

            if len(self._timestamps) >= self.requests_per_second:
                sleep_time = self._timestamps[0] - window_start
                if sleep_time > 0:
                    log.debug("rate_limit_wait", sleep=f"{sleep_time:.3f}s")
                    await asyncio.sleep(sleep_time)

            self._timestamps.append(now)

    def remaining(self) -> int:
        now = time.monotonic()
        window_start = now - 1.0
        while self._timestamps and self._timestamps[0] < window_start:
            self._timestamps.popleft()
        return max(0, int(self.requests_per_second) - len(self._timestamps))

@dataclass
class RetryConfig:
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0

class RetryableError(Exception):
    pass

async def retry_with_backoff(
    func: Callable[P, T],
    *args: P.args,
    config: RetryConfig = None,
    **kwargs: P.kwargs
) -> T:
    config = config or RetryConfig()
    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return await func(*args, **kwargs)
        except RetryableError as e:
            last_exception = e
            if attempt < config.max_attempts - 1:
                delay = min(
                    config.base_delay * (config.exponential_base ** attempt),
                    config.max_delay
                )
                log.warning(
                    "retry_attempt",
                    attempt=attempt + 1,
                    max_attempts=config.max_attempts,
                    delay=f"{delay:.1f}s",
                    error=str(e)
                )
                await asyncio.sleep(delay)
        except Exception:
            raise

    raise last_exception

def rate_limited(limiter: RateLimiter):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            await limiter.acquire()
            return await func(*args, **kwargs)
        return wrapper
    return decorator

class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_requests: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_requests = half_open_requests
        self._failures = 0
        self._last_failure_time = 0.0
        self._state = "closed"
        self._half_open_successes = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    async def call(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        async with self._lock:
            if self._state == "open":
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    log.info("circuit_breaker_half_open")
                    self._state = "half_open"
                    self._half_open_successes = 0
                else:
                    raise CircuitBreakerOpenError("Circuit breaker is open")

        try:
            result = await func(*args, **kwargs)
            async with self._lock:
                if self._state == "half_open":
                    self._half_open_successes += 1
                    if self._half_open_successes >= self.half_open_requests:
                        log.info("circuit_breaker_closed")
                        self._state = "closed"
                        self._failures = 0
                elif self._state == "closed":
                    self._failures = 0
            return result
        except Exception:
            async with self._lock:
                self._failures += 1
                self._last_failure_time = time.monotonic()
                if self._failures >= self.failure_threshold:
                    log.warning("circuit_breaker_open", failures=self._failures)
                    self._state = "open"
            raise

class CircuitBreakerOpenError(Exception):
    pass
