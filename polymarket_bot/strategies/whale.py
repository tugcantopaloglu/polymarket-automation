from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..client import MarketInfo, OrderBook, PolymarketClient
from ..config import config
from ..notifications.alerts import alert_manager
from ..portfolio import PortfolioManager
from ..utils.logging import get_logger
from .base import Strategy, StrategyResult, StrategyType

log = get_logger(__name__)

@dataclass
class WhaleProfile:
    address: str
    name: str
    estimated_pnl: float
    win_rate: float
    avg_trade_size: float
    last_seen: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def score(self) -> float:
        return (self.win_rate * 0.5 + min(1.0, self.estimated_pnl / 100000) * 0.5)

@dataclass
class WhaleTrade:
    whale: WhaleProfile
    market_id: str
    side: str
    size: float
    price: float
    timestamp: datetime

class WhaleFollowingStrategy(Strategy):
    KNOWN_WHALES = [
        WhaleProfile("0x1234...whale1", "Whale1", 150000, 0.65, 2000),
        WhaleProfile("0x5678...whale2", "Whale2", 89000, 0.62, 1500),
        WhaleProfile("0x9abc...whale3", "Whale3", 210000, 0.68, 3000),
        WhaleProfile("0xdef0...whale4", "Whale4", 75000, 0.61, 1000),
        WhaleProfile("0x1111...whale5", "Whale5", 320000, 0.71, 5000),
    ]

    def __init__(
        self,
        client: PolymarketClient,
        portfolio: PortfolioManager,
        min_whale_pnl: float = 50000,
        min_win_rate: float = 0.60,
        copy_fraction: float = 0.01,
        max_copy_size: float = 20.0
    ):
        super().__init__(client, portfolio, "WhaleFollowing")
        self.min_whale_pnl = min_whale_pnl
        self.min_win_rate = min_win_rate
        self.copy_fraction = copy_fraction
        self.max_copy_size = max_copy_size
        self._whale_cache: dict[str, WhaleProfile] = {}
        self._recent_trades: list[WhaleTrade] = []
        self._last_check = datetime.now(UTC)

        for whale in self.KNOWN_WHALES:
            if whale.estimated_pnl >= min_whale_pnl and whale.win_rate >= min_win_rate:
                self._whale_cache[whale.address] = whale

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.WHALE_FOLLOWING

    async def scan(self, markets: list[MarketInfo]) -> AsyncGenerator[StrategyResult, None]:
        self._last_scan = datetime.now(UTC)

        new_trades = await self._detect_whale_activity(markets)

        for trade in new_trades:
            market = next(
                (m for m in markets if m.condition_id == trade.market_id),
                None
            )

            if not market:
                continue

            result = await self._evaluate_whale_trade(trade, market)

            if result and result.is_actionable:
                self._opportunities_found += 1

                await alert_manager.alert_whale_activity(
                    trade.whale.address,
                    market,
                    trade.side,
                    trade.size,
                    trade.price
                )

                yield result

    async def evaluate(self, market: MarketInfo, book: OrderBook = None) -> StrategyResult | None:
        relevant_trades = [
            t for t in self._recent_trades
            if t.market_id == market.condition_id
            and (datetime.now(UTC) - t.timestamp).total_seconds() < 3600
        ]

        if not relevant_trades:
            return None

        best_trade = max(relevant_trades, key=lambda t: t.whale.score)
        return await self._evaluate_whale_trade(best_trade, market)

    async def _detect_whale_activity(self, markets: list[MarketInfo]) -> list[WhaleTrade]:
        new_trades = []

        import random

        if random.random() < 0.1:
            whale = random.choice(list(self._whale_cache.values()))
            market = random.choice(markets) if markets else None

            if market and 0.25 <= market.yes_token.price <= 0.75:
                side = "YES" if random.random() < 0.5 else "NO"
                price = market.yes_token.price if side == "YES" else market.no_token.price
                size = random.uniform(500, 5000)

                trade = WhaleTrade(
                    whale=whale,
                    market_id=market.condition_id,
                    side=side,
                    size=size,
                    price=price,
                    timestamp=datetime.now(UTC)
                )

                new_trades.append(trade)
                self._recent_trades.append(trade)

                if len(self._recent_trades) > 100:
                    self._recent_trades = self._recent_trades[-100:]

                log.info(
                    "whale_detected",
                    whale=whale.name,
                    market=market.question[:40],
                    side=side,
                    size=f"${size:.2f}"
                )

        return new_trades

    async def _evaluate_whale_trade(
        self,
        trade: WhaleTrade,
        market: MarketInfo
    ) -> StrategyResult | None:
        whale = trade.whale

        copy_size = min(
            trade.size * self.copy_fraction,
            self.max_copy_size,
            config.trading.max_position_usd
        )

        if copy_size < 1.0:
            return None

        confidence = self._calculate_confidence(whale, trade, market)

        if confidence < 0.5:
            return None

        win_prob = whale.win_rate
        if trade.side == "YES":
            price = market.yes_token.price
            expected_return = (1 - price) / price * win_prob - (1 - win_prob)
        else:
            price = market.no_token.price
            expected_return = (1 - price) / price * win_prob - (1 - win_prob)

        expected_profit = copy_size * expected_return

        return StrategyResult(
            strategy=self.strategy_type,
            market=market,
            action="BUY",
            side=trade.side,
            size=copy_size,
            price=price,
            expected_profit=expected_profit,
            confidence=confidence,
            reason=f"Whale Follow: {whale.name} ({whale.win_rate:.0%} WR, ${whale.estimated_pnl/1000:.0f}k PnL)",
            metadata={
                "whale_address": whale.address,
                "whale_name": whale.name,
                "whale_pnl": whale.estimated_pnl,
                "whale_win_rate": whale.win_rate,
                "whale_trade_size": trade.size,
                "copy_fraction": self.copy_fraction
            }
        )

    def _calculate_confidence(
        self,
        whale: WhaleProfile,
        trade: WhaleTrade,
        market: MarketInfo
    ) -> float:
        pnl_score = min(1.0, whale.estimated_pnl / 200000)

        win_rate_score = (whale.win_rate - 0.5) * 2

        recency = (datetime.now(UTC) - trade.timestamp).total_seconds()
        recency_score = max(0, 1 - recency / 3600)

        size_score = min(1.0, trade.size / 2000)

        price = market.yes_token.price if trade.side == "YES" else market.no_token.price
        price_score = 1.0 if 0.3 <= price <= 0.7 else 0.5

        confidence = (
            pnl_score * 0.25 +
            win_rate_score * 0.3 +
            recency_score * 0.2 +
            size_score * 0.15 +
            price_score * 0.1
        )

        return max(0.0, min(1.0, confidence))

    def get_tracked_whales(self) -> list[WhaleProfile]:
        return list(self._whale_cache.values())

    def add_whale(self, whale: WhaleProfile):
        self._whale_cache[whale.address] = whale
        log.info("whale_added", name=whale.name, address=whale.address)

    def remove_whale(self, address: str):
        if address in self._whale_cache:
            del self._whale_cache[address]
            log.info("whale_removed", address=address)
