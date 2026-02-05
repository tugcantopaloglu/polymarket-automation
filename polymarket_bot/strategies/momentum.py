from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from ..analysis.market_analyzer import MarketMetrics, market_analyzer
from ..client import MarketInfo, OrderBook, PolymarketClient
from ..portfolio import PortfolioManager
from ..utils.logging import get_logger
from .base import Strategy, StrategyResult, StrategyType

log = get_logger(__name__)

class MomentumStrategy(Strategy):
    def __init__(
        self,
        client: PolymarketClient,
        portfolio: PortfolioManager,
        momentum_threshold: float = 0.05,
        min_volume: float = 1000,
        lookback_hours: int = 24
    ):
        super().__init__(client, portfolio, "Momentum")
        self.momentum_threshold = momentum_threshold
        self.min_volume = min_volume
        self.lookback_hours = lookback_hours

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.MOMENTUM

    async def scan(self, markets: list[MarketInfo]) -> AsyncGenerator[StrategyResult, None]:
        self._last_scan = datetime.now(UTC)

        for market in markets:
            if market.volume_24h < self.min_volume:
                continue

            if market.yes_token.price <= 0.1 or market.yes_token.price >= 0.9:
                continue

            result = await self.evaluate(market)

            if result and result.is_actionable:
                self._opportunities_found += 1
                yield result

    async def evaluate(self, market: MarketInfo, book: OrderBook = None) -> StrategyResult | None:
        if not book:
            book = await self.client.get_order_book(market.yes_token.token_id)

        metrics = market_analyzer.analyze_market(market, book)

        if abs(metrics.momentum_24h) < self.momentum_threshold:
            return None

        if metrics.trend_strength < 0.3:
            return None

        if metrics.momentum_24h > 0:
            side = "YES"
            price = market.yes_token.price
            momentum = metrics.momentum_24h
        else:
            side = "NO"
            price = market.no_token.price
            momentum = -metrics.momentum_24h

        confidence = self._calculate_confidence(metrics, momentum)

        if confidence < 0.5:
            return None

        risk_metrics = market_analyzer.calculate_risk_metrics(market, metrics, side)
        position_size = self.portfolio.calculate_position_size(
            risk_metrics,
            self.portfolio.client.get_balance()
        )

        expected_profit = position_size * momentum * 0.5

        return StrategyResult(
            strategy=self.strategy_type,
            market=market,
            action="BUY",
            side=side,
            size=position_size,
            price=price,
            expected_profit=expected_profit,
            confidence=confidence,
            reason=f"Momentum: {momentum:+.1%} 24h, trend strength {metrics.trend_strength:.2f}",
            metadata={
                "momentum_24h": metrics.momentum_24h,
                "momentum_1h": metrics.momentum_1h,
                "trend_strength": metrics.trend_strength,
                "volatility": metrics.volatility_24h,
                "volume_trend": metrics.volume_trend,
                "bid_ask_ratio": metrics.bid_ask_ratio
            }
        )

    def _calculate_confidence(self, metrics: MarketMetrics, momentum: float) -> float:
        momentum_score = min(1.0, momentum / 0.15)

        trend_score = metrics.trend_strength

        volume_score = min(1.0, metrics.volume_trend / 2.0)

        volatility_penalty = min(0.3, metrics.volatility_24h * 2)

        liquidity_score = metrics.liquidity_score

        bid_ask_score = 0.5
        if metrics.bid_ask_ratio > 1.2:
            bid_ask_score = 0.7 if momentum > 0 else 0.3
        elif metrics.bid_ask_ratio < 0.8:
            bid_ask_score = 0.3 if momentum > 0 else 0.7

        confidence = (
            momentum_score * 0.25 +
            trend_score * 0.25 +
            volume_score * 0.15 +
            liquidity_score * 0.15 +
            bid_ask_score * 0.2 -
            volatility_penalty
        )

        return max(0.0, min(1.0, confidence))

class MeanReversionStrategy(Strategy):
    def __init__(
        self,
        client: PolymarketClient,
        portfolio: PortfolioManager,
        reversion_threshold: float = 0.3,
        min_liquidity: float = 500
    ):
        super().__init__(client, portfolio, "MeanReversion")
        self.reversion_threshold = reversion_threshold
        self.min_liquidity = min_liquidity

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.MEAN_REVERSION

    async def scan(self, markets: list[MarketInfo]) -> AsyncGenerator[StrategyResult, None]:
        self._last_scan = datetime.now(UTC)

        for market in markets:
            if market.liquidity < self.min_liquidity:
                continue

            if market.yes_token.price <= 0.15 or market.yes_token.price >= 0.85:
                continue

            result = await self.evaluate(market)

            if result and result.is_actionable:
                self._opportunities_found += 1
                yield result

    async def evaluate(self, market: MarketInfo, book: OrderBook = None) -> StrategyResult | None:
        if not book:
            book = await self.client.get_order_book(market.yes_token.token_id)

        metrics = market_analyzer.analyze_market(market, book)

        if abs(metrics.mean_reversion_signal) < self.reversion_threshold:
            return None

        if metrics.volatility_24h < 0.02:
            return None

        if metrics.mean_reversion_signal > 0:
            side = "YES"
            price = market.yes_token.price
        else:
            side = "NO"
            price = market.no_token.price

        signal_strength = abs(metrics.mean_reversion_signal)

        volatility_factor = min(1.0, metrics.volatility_24h / 0.1)
        liquidity_factor = metrics.liquidity_score

        trend_penalty = 0.2 if abs(metrics.momentum_24h) > 0.1 else 0

        confidence = (
            signal_strength * 0.4 +
            volatility_factor * 0.2 +
            liquidity_factor * 0.2 +
            0.2 -
            trend_penalty
        )

        if confidence < 0.5:
            return None

        risk_metrics = market_analyzer.calculate_risk_metrics(market, metrics, side)
        position_size = self.portfolio.calculate_position_size(
            risk_metrics,
            self.portfolio.client.get_balance()
        )

        expected_reversion = signal_strength * metrics.volatility_24h * 2
        expected_profit = position_size * expected_reversion

        return StrategyResult(
            strategy=self.strategy_type,
            market=market,
            action="BUY",
            side=side,
            size=position_size,
            price=price,
            expected_profit=expected_profit,
            confidence=confidence,
            reason=f"Mean Reversion: signal {metrics.mean_reversion_signal:+.2f}, vol {metrics.volatility_24h:.1%}",
            metadata={
                "mean_reversion_signal": metrics.mean_reversion_signal,
                "volatility": metrics.volatility_24h,
                "expected_reversion": expected_reversion
            }
        )
