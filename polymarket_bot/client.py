import asyncio
import contextlib
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime

import aiohttp
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

from .config import config, keystore
from .utils.logging import get_logger, metrics
from .utils.rate_limiter import (
    CircuitBreaker,
    RateLimiter,
    RetryableError,
    RetryConfig,
    retry_with_backoff,
)

log = get_logger(__name__)

@dataclass
class TokenInfo:
    token_id: str
    outcome: str
    price: float
    volume_24h: float = 0.0
    price_change_24h: float = 0.0

@dataclass
class MarketInfo:
    condition_id: str
    question: str
    yes_token: TokenInfo
    no_token: TokenInfo
    volume_24h: float = 0.0
    liquidity: float = 0.0
    end_date: datetime | None = None
    category: str = ""

    @property
    def spread(self) -> float:
        return 1.0 - (self.yes_token.price + self.no_token.price)

    @property
    def is_arbitrage(self) -> bool:
        return self.spread > config.trading.min_profit_margin

    @property
    def days_to_resolution(self) -> float | None:
        if self.end_date:
            delta = self.end_date - datetime.now(UTC)
            return delta.total_seconds() / 86400
        return None

@dataclass
class OrderBook:
    bids: list
    asks: list
    best_bid: float
    best_ask: float
    bid_liquidity: float
    ask_liquidity: float
    mid_price: float
    spread: float

    @classmethod
    def from_raw(cls, book: dict) -> 'OrderBook':
        bids = book.get("bids", [])
        asks = book.get("asks", [])

        best_bid = float(bids[0]["price"]) if bids else 0
        best_ask = float(asks[0]["price"]) if asks else 1

        bid_liq = sum(float(b.get("size", 0)) * float(b.get("price", 0)) for b in bids[:10])
        ask_liq = sum(float(a.get("size", 0)) * float(a.get("price", 0)) for a in asks[:10])

        mid = (best_bid + best_ask) / 2 if best_bid and best_ask < 1 else 0.5
        spread = best_ask - best_bid

        return cls(
            bids=bids,
            asks=asks,
            best_bid=best_bid,
            best_ask=best_ask,
            bid_liquidity=bid_liq,
            ask_liquidity=ask_liq,
            mid_price=mid,
            spread=spread
        )

@dataclass
class Position:
    token_id: str
    market_id: str
    outcome: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    timestamp: datetime

class PolymarketClient:
    def __init__(self, private_key: str | None = None, funder: str | None = None):
        self.private_key = private_key or keystore.load_private_key()
        self.funder = funder
        self._clob: ClobClient | None = None
        self._session: aiohttp.ClientSession | None = None
        self._rate_limiter = RateLimiter(
            requests_per_second=config.rate_limit.requests_per_second,
            burst_limit=config.rate_limit.burst_limit
        )
        self._circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        self._retry_config = RetryConfig(
            max_attempts=config.rate_limit.retry_attempts,
            base_delay=config.rate_limit.retry_delay_base,
            max_delay=config.rate_limit.retry_delay_max
        )

    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=30)
        self._session = aiohttp.ClientSession(timeout=timeout)
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()

    @property
    def clob(self) -> ClobClient:
        if self._clob is None:
            if self.private_key:
                self._clob = ClobClient(
                    config.host,
                    key=self.private_key,
                    chain_id=config.chain_id,
                    signature_type=0,
                    funder=self.funder
                )
                self._clob.set_api_creds(self._clob.create_or_derive_api_creds())
            else:
                self._clob = ClobClient(config.host)
        return self._clob

    async def _request(self, method: str, url: str, **kwargs) -> dict:
        await self._rate_limiter.acquire()
        metrics.increment("api_requests", tags={"method": method})

        async def _do_request():
            async with self._session.request(method, url, **kwargs) as resp:
                if resp.status == 429:
                    metrics.increment("rate_limit_hits")
                    raise RetryableError("Rate limited")
                if resp.status >= 500:
                    raise RetryableError(f"Server error: {resp.status}")
                if resp.status != 200:
                    return None
                return await resp.json()

        try:
            return await self._circuit_breaker.call(
                retry_with_backoff,
                _do_request,
                config=self._retry_config
            )
        except Exception as e:
            metrics.increment("api_errors", tags={"error": type(e).__name__})
            log.error("api_request_failed", url=url, error=str(e))
            return None

    async def get_markets(self, active: bool = True, limit: int = 200) -> list[dict]:
        params = {"closed": str(not active).lower(), "limit": limit}
        data = await self._request("GET", f"{config.gamma_host}/markets", params=params)
        return data if isinstance(data, list) else []

    async def get_events(self, active: bool = True, limit: int = 200) -> list[dict]:
        params = {"active": str(active).lower(), "limit": limit}
        data = await self._request("GET", f"{config.gamma_host}/events", params=params)
        return data if isinstance(data, list) else []

    async def get_market_info(self, condition_id: str) -> MarketInfo | None:
        data = await self._request("GET", f"{config.gamma_host}/markets/{condition_id}")
        if not data:
            return None

        tokens = data.get("tokens", [])
        if len(tokens) < 2:
            return None

        yes_token = next((t for t in tokens if t["outcome"] == "Yes"), None)
        no_token = next((t for t in tokens if t["outcome"] == "No"), None)

        if not yes_token or not no_token:
            return None

        end_date = None
        if end_str := data.get("end_date_iso") or data.get("endDate"):
            with contextlib.suppress(ValueError):
                end_date = datetime.fromisoformat(end_str.replace('Z', '+00:00'))

        return MarketInfo(
            condition_id=condition_id,
            question=data.get("question", ""),
            yes_token=TokenInfo(
                token_id=yes_token["token_id"],
                outcome="Yes",
                price=float(yes_token.get("price", 0)),
                volume_24h=float(yes_token.get("volume", 0)),
                price_change_24h=float(yes_token.get("price_change_24h", 0))
            ),
            no_token=TokenInfo(
                token_id=no_token["token_id"],
                outcome="No",
                price=float(no_token.get("price", 0)),
                volume_24h=float(no_token.get("volume", 0)),
                price_change_24h=float(no_token.get("price_change_24h", 0))
            ),
            volume_24h=float(data.get("volume", 0)),
            liquidity=float(data.get("liquidity", 0)),
            end_date=end_date,
            category=data.get("category", "")
        )

    async def get_order_book(self, token_id: str) -> OrderBook | None:
        data = await self._request("GET", f"{config.host}/book", params={"token_id": token_id})
        if not data:
            return None
        return OrderBook.from_raw(data)

    async def get_order_books_batch(self, token_ids: list[str]) -> dict[str, OrderBook]:
        tasks = [self.get_order_book(tid) for tid in token_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {
            tid: result for tid, result in zip(token_ids, results, strict=False)
            if isinstance(result, OrderBook)
        }

    async def get_price_history(self, token_id: str, interval: str = "1h", limit: int = 168) -> list[dict]:
        params = {"market": token_id, "interval": interval, "limit": limit}
        data = await self._request("GET", f"{config.gamma_host}/prices", params=params)
        return data if isinstance(data, list) else []

    def get_midpoint(self, token_id: str) -> float | None:
        try:
            return float(self.clob.get_midpoint(token_id))
        except Exception:
            return None

    def place_market_order(self, token_id: str, amount: float, side: str) -> dict:
        metrics.increment("orders_placed", tags={"type": "market", "side": side})
        order_side = BUY if side.upper() == "BUY" else SELL
        order = MarketOrderArgs(
            token_id=token_id,
            amount=amount,
            side=order_side,
            order_type=OrderType.FOK
        )
        signed = self.clob.create_market_order(order)
        result = self.clob.post_order(signed, OrderType.FOK)
        if result.get("success"):
            metrics.increment("orders_filled", tags={"type": "market"})
        return result

    def place_limit_order(self, token_id: str, price: float, size: float, side: str) -> dict:
        metrics.increment("orders_placed", tags={"type": "limit", "side": side})
        order_side = BUY if side.upper() == "BUY" else SELL
        order = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=order_side
        )
        signed = self.clob.create_order(order)
        return self.clob.post_order(signed, OrderType.GTC)

    def cancel_order(self, order_id: str) -> bool:
        try:
            self.clob.cancel(order_id)
            return True
        except Exception:
            return False

    def cancel_all_orders(self) -> bool:
        try:
            self.clob.cancel_all()
            return True
        except Exception:
            return False

    def get_balance(self) -> float:
        try:
            bal = self.clob.get_balance_allowance()
            balance = float(bal.get("balance", 0)) if bal else 0
            metrics.gauge("wallet_balance", balance)
            return balance
        except Exception:
            return 0

    def get_positions(self) -> list[Position]:
        try:
            positions = []
            return positions
        except Exception:
            return []

    async def stream_prices(self, token_ids: list[str], callback) -> AsyncGenerator[dict, None]:
        while True:
            for token_id in token_ids:
                book = await self.get_order_book(token_id)
                if book:
                    await callback({
                        "token_id": token_id,
                        "mid_price": book.mid_price,
                        "best_bid": book.best_bid,
                        "best_ask": book.best_ask,
                        "timestamp": datetime.now(UTC).isoformat()
                    })
            await asyncio.sleep(1)
