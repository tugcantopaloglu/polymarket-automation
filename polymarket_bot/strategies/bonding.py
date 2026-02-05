from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from ..client import MarketInfo, OrderBook, PolymarketClient
from ..portfolio import PortfolioManager
from ..utils.logging import get_logger
from .base import Strategy, StrategyResult, StrategyType

log = get_logger(__name__)

class BondingStrategy(Strategy):
    def __init__(
        self,
        client: PolymarketClient,
        portfolio: PortfolioManager,
        min_probability: float = 0.92,
        max_days_to_resolution: int = 14,
        min_annualized_return: float = 0.10
    ):
        super().__init__(client, portfolio, "Bonding")
        self.min_probability = min_probability
        self.max_days = max_days_to_resolution
        self.min_annualized_return = min_annualized_return

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.BONDING

    async def scan(self, markets: list[MarketInfo]) -> AsyncGenerator[StrategyResult, None]:
        self._last_scan = datetime.now(UTC)
        now = datetime.now(UTC)

        for market in markets:
            if not market.end_date:
                continue

            days_to_resolution = (market.end_date - now).total_seconds() / 86400

            if days_to_resolution < 0 or days_to_resolution > self.max_days:
                continue

            for token, outcome in [
                (market.yes_token, "YES"),
                (market.no_token, "NO")
            ]:
                if token.price < self.min_probability or token.price >= 0.99:
                    continue

                result = await self._evaluate_bonding(market, token.price, outcome, days_to_resolution)

                if result and result.is_actionable:
                    self._opportunities_found += 1
                    yield result

    async def evaluate(self, market: MarketInfo, book: OrderBook = None) -> StrategyResult | None:
        if not market.end_date:
            return None

        now = datetime.now(UTC)
        days_to_resolution = (market.end_date - now).total_seconds() / 86400

        if days_to_resolution < 0 or days_to_resolution > self.max_days:
            return None

        best_result = None
        best_return = 0

        for token, outcome in [
            (market.yes_token, "YES"),
            (market.no_token, "NO")
        ]:
            if token.price < self.min_probability or token.price >= 0.99:
                continue

            result = await self._evaluate_bonding(market, token.price, outcome, days_to_resolution)

            if result and result.metadata.get("annualized_return", 0) > best_return:
                best_result = result
                best_return = result.metadata["annualized_return"]

        return best_result

    async def _evaluate_bonding(
        self,
        market: MarketInfo,
        price: float,
        outcome: str,
        days_to_resolution: float
    ) -> StrategyResult | None:
        expected_return = (1.0 - price) / price

        days_for_calc = max(days_to_resolution, 1)
        annualized_return = expected_return * (365 / days_for_calc)

        if annualized_return < self.min_annualized_return:
            return None

        base_confidence = 0.5

        price_confidence = (price - 0.90) / 0.09

        time_confidence = 1.0 - (days_to_resolution / self.max_days)

        return_confidence = min(1.0, annualized_return / 0.5)

        confidence = (
            price_confidence * 0.4 +
            time_confidence * 0.3 +
            return_confidence * 0.2 +
            base_confidence * 0.1
        )

        limits = self.portfolio.get_risk_limits()
        position_size = min(
            limits.max_position_size,
            20.0,
            100 / (1 + annualized_return)
        )

        expected_profit = position_size * expected_return

        return StrategyResult(
            strategy=self.strategy_type,
            market=market,
            action="BUY",
            side=outcome,
            size=position_size,
            price=price,
            expected_profit=expected_profit,
            confidence=confidence,
            reason=f"Bonding: {price:.1%} prob, {days_to_resolution:.1f}d, {annualized_return:.0%} APY",
            metadata={
                "probability": price,
                "days_to_resolution": days_to_resolution,
                "expected_return": expected_return,
                "annualized_return": annualized_return,
                "confidence_breakdown": {
                    "price": price_confidence,
                    "time": time_confidence,
                    "return": return_confidence
                }
            }
        )
