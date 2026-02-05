from collections.abc import AsyncGenerator
from datetime import UTC, datetime

from ..analysis.market_analyzer import arbitrage_analyzer
from ..client import MarketInfo, OrderBook, PolymarketClient
from ..portfolio import PortfolioManager
from ..utils.logging import get_logger
from .base import Strategy, StrategyResult, StrategyType

log = get_logger(__name__)

class ArbitrageStrategy(Strategy):
    def __init__(
        self,
        client: PolymarketClient,
        portfolio: PortfolioManager,
        min_margin: float = 0.02,
        min_liquidity: float = 50.0,
        max_position: float = 50.0
    ):
        super().__init__(client, portfolio, "Arbitrage")
        self.min_margin = min_margin
        self.min_liquidity = min_liquidity
        self.max_position = max_position

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.ARBITRAGE

    async def scan(self, markets: list[MarketInfo]) -> AsyncGenerator[StrategyResult, None]:
        self._last_scan = datetime.now(UTC)

        token_ids = []
        token_to_market = {}

        for market in markets:
            if market.yes_token.price <= 0.05 or market.no_token.price <= 0.05:
                continue
            if market.yes_token.price >= 0.95 or market.no_token.price >= 0.95:
                continue

            spread = market.spread
            if spread >= self.min_margin * 0.5:
                token_ids.extend([market.yes_token.token_id, market.no_token.token_id])
                token_to_market[market.yes_token.token_id] = market
                token_to_market[market.no_token.token_id] = market

        if not token_ids:
            return

        books = await self.client.get_order_books_batch(token_ids)

        analyzed_markets = set()

        for token_id, _book in books.items():
            market = token_to_market.get(token_id)
            if not market or market.condition_id in analyzed_markets:
                continue

            analyzed_markets.add(market.condition_id)

            yes_book = books.get(market.yes_token.token_id)
            no_book = books.get(market.no_token.token_id)

            if not yes_book or not no_book:
                continue

            result = await self._analyze_opportunity(market, yes_book, no_book)
            if result and result.is_actionable:
                self._opportunities_found += 1
                yield result

    async def evaluate(self, market: MarketInfo, book: OrderBook = None) -> StrategyResult | None:
        yes_book = await self.client.get_order_book(market.yes_token.token_id)
        no_book = await self.client.get_order_book(market.no_token.token_id)

        if not yes_book or not no_book:
            return None

        return await self._analyze_opportunity(market, yes_book, no_book)

    async def _analyze_opportunity(
        self,
        market: MarketInfo,
        yes_book: OrderBook,
        no_book: OrderBook
    ) -> StrategyResult | None:
        analysis = arbitrage_analyzer.analyze_arbitrage(
            market, yes_book, no_book, self.max_position
        )

        if analysis.confidence == "NONE":
            return None

        if analysis.net_margin < self.min_margin:
            return None

        min_liq = min(yes_book.ask_liquidity, no_book.ask_liquidity)
        if min_liq < self.min_liquidity:
            return None

        position_size = min(
            self.max_position,
            analysis.max_executable_size,
            min_liq * 0.3
        )

        confidence_map = {"HIGH": 0.9, "MEDIUM": 0.7, "LOW": 0.5, "NONE": 0.0}
        confidence = confidence_map.get(analysis.confidence, 0.5)

        confidence *= (1 - analysis.execution_risk)

        expected_profit = position_size * analysis.net_margin

        return StrategyResult(
            strategy=self.strategy_type,
            market=market,
            action="BUY",
            side="BOTH",
            size=position_size,
            price=yes_book.best_ask + no_book.best_ask,
            expected_profit=expected_profit,
            confidence=confidence,
            reason=f"Arbitrage: {analysis.net_margin:.2%} net margin",
            metadata={
                "gross_margin": analysis.gross_margin,
                "net_margin": analysis.net_margin,
                "slippage": analysis.slippage_estimate,
                "yes_ask": yes_book.best_ask,
                "no_ask": no_book.best_ask,
                "execution_risk": analysis.execution_risk
            }
        )

    async def execute_arbitrage(self, result: StrategyResult) -> bool:
        if not self.should_execute(result):
            return False

        market = result.market
        metadata = result.metadata

        yes_size = result.size * metadata["yes_ask"] / result.price
        no_size = result.size * metadata["no_ask"] / result.price

        log.info(
            "executing_arbitrage",
            market=market.question[:40],
            yes_size=f"${yes_size:.2f}",
            no_size=f"${no_size:.2f}",
            expected_profit=f"${result.expected_profit:.2f}"
        )

        yes_result = self.client.place_market_order(
            market.yes_token.token_id,
            yes_size,
            "BUY"
        )

        if not yes_result.get("success"):
            log.error("arbitrage_yes_failed", result=yes_result)
            return False

        no_result = self.client.place_market_order(
            market.no_token.token_id,
            no_size,
            "BUY"
        )

        if not no_result.get("success"):
            log.error("arbitrage_no_failed_exposed", result=no_result)
            return False

        self._trades_executed += 1

        log.info(
            "arbitrage_executed",
            market=market.question[:40],
            profit=f"${result.expected_profit:.2f}"
        )

        return True
