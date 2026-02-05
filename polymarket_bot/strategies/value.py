from typing import Optional, List, AsyncGenerator
from datetime import datetime, timezone

from .base import Strategy, StrategyResult, StrategyType
from ..client import PolymarketClient, MarketInfo, OrderBook
from ..portfolio import PortfolioManager
from ..analysis.market_analyzer import market_analyzer
from ..config import config
from ..utils.logging import get_logger

log = get_logger(__name__)

class ValueStrategy(Strategy):
    def __init__(
        self,
        client: PolymarketClient,
        portfolio: PortfolioManager,
        min_edge: float = 0.05,
        min_liquidity: float = 200,
        kelly_multiplier: float = 0.25
    ):
        super().__init__(client, portfolio, "Value")
        self.min_edge = min_edge
        self.min_liquidity = min_liquidity
        self.kelly_multiplier = kelly_multiplier
    
    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.VALUE
    
    async def scan(self, markets: List[MarketInfo]) -> AsyncGenerator[StrategyResult, None]:
        self._last_scan = datetime.now(timezone.utc)
        
        for market in markets:
            if market.liquidity < self.min_liquidity:
                continue
            
            result = await self.evaluate(market)
            
            if result and result.is_actionable:
                self._opportunities_found += 1
                yield result
    
    async def evaluate(self, market: MarketInfo, book: OrderBook = None) -> Optional[StrategyResult]:
        if not book:
            book = await self.client.get_order_book(market.yes_token.token_id)
        
        metrics = market_analyzer.analyze_market(market, book)
        
        yes_fair_value = self._estimate_fair_value(market, metrics, "YES")
        no_fair_value = self._estimate_fair_value(market, metrics, "NO")
        
        yes_edge = yes_fair_value - market.yes_token.price
        no_edge = no_fair_value - market.no_token.price
        
        if yes_edge > self.min_edge and yes_edge > no_edge:
            side = "YES"
            price = market.yes_token.price
            edge = yes_edge
            fair_value = yes_fair_value
        elif no_edge > self.min_edge:
            side = "NO"
            price = market.no_token.price
            edge = no_edge
            fair_value = no_fair_value
        else:
            return None
        
        risk_metrics = market_analyzer.calculate_risk_metrics(
            market, metrics, side, confidence_override=fair_value
        )
        
        if risk_metrics.expected_value <= 0:
            return None
        
        kelly = risk_metrics.kelly_fraction * self.kelly_multiplier
        available_capital = self.portfolio.client.get_balance()
        position_size = min(
            available_capital * kelly,
            config.trading.max_position_usd,
            market.liquidity * 0.05
        )
        
        confidence = self._calculate_confidence(edge, metrics, risk_metrics)
        
        if confidence < 0.5:
            return None
        
        expected_profit = position_size * risk_metrics.expected_value
        
        return StrategyResult(
            strategy=self.strategy_type,
            market=market,
            action="BUY",
            side=side,
            size=position_size,
            price=price,
            expected_profit=expected_profit,
            confidence=confidence,
            reason=f"Value: {edge:+.1%} edge, EV {risk_metrics.expected_value:+.2f}, Kelly {kelly:.1%}",
            metadata={
                "edge": edge,
                "fair_value": fair_value,
                "market_price": price,
                "expected_value": risk_metrics.expected_value,
                "kelly_fraction": risk_metrics.kelly_fraction,
                "win_probability": risk_metrics.win_probability,
                "risk_reward": risk_metrics.risk_reward_ratio
            }
        )
    
    def _estimate_fair_value(
        self,
        market: MarketInfo,
        metrics: MarketMetrics,
        side: str
    ) -> float:
        market_price = market.yes_token.price if side == "YES" else market.no_token.price
        
        base_estimate = market_price
        
        momentum_adj = metrics.momentum_24h * 0.2
        if side == "NO":
            momentum_adj = -momentum_adj
        
        liquidity_adj = 0
        if metrics.bid_ask_ratio > 1.3:
            liquidity_adj = 0.02 if side == "YES" else -0.02
        elif metrics.bid_ask_ratio < 0.7:
            liquidity_adj = -0.02 if side == "YES" else 0.02
        
        volatility_adj = metrics.volatility_24h * 0.5
        
        mean_reversion_adj = metrics.mean_reversion_signal * 0.05
        if side == "YES":
            mean_reversion_adj = mean_reversion_adj
        else:
            mean_reversion_adj = -mean_reversion_adj
        
        fair_value = (
            base_estimate +
            momentum_adj +
            liquidity_adj +
            mean_reversion_adj
        )
        
        fair_value = max(0.05, min(0.95, fair_value))
        
        return fair_value
    
    def _calculate_confidence(
        self,
        edge: float,
        metrics: MarketMetrics,
        risk_metrics: RiskMetrics
    ) -> float:
        edge_score = min(1.0, edge / 0.15)
        
        ev_score = min(1.0, max(0, risk_metrics.expected_value / 0.3))
        
        kelly_score = min(1.0, risk_metrics.kelly_fraction / 0.2)
        
        liquidity_score = metrics.liquidity_score
        
        volatility_penalty = min(0.2, metrics.volatility_24h * 2)
        
        confidence = (
            edge_score * 0.3 +
            ev_score * 0.25 +
            kelly_score * 0.2 +
            liquidity_score * 0.15 +
            0.1 -
            volatility_penalty
        )
        
        return max(0.0, min(1.0, confidence))

from ..analysis.market_analyzer import MarketMetrics, RiskMetrics
