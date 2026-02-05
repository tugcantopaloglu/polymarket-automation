import math
from dataclasses import dataclass
from statistics import mean, stdev

from ..client import MarketInfo, OrderBook
from ..data.database import db
from ..utils.logging import get_logger

log = get_logger(__name__)

@dataclass
class MarketMetrics:
    token_id: str
    current_price: float
    momentum_1h: float = 0.0
    momentum_24h: float = 0.0
    volatility_24h: float = 0.0
    volume_trend: float = 0.0
    bid_ask_ratio: float = 1.0
    liquidity_score: float = 0.0
    mean_reversion_signal: float = 0.0
    trend_strength: float = 0.0

@dataclass
class RiskMetrics:
    expected_value: float
    win_probability: float
    loss_probability: float
    risk_reward_ratio: float
    kelly_fraction: float
    max_position_size: float
    confidence_score: float
    var_95: float
    cvar_95: float

@dataclass
class ArbitrageAnalysis:
    market: MarketInfo
    yes_book: OrderBook
    no_book: OrderBook
    gross_margin: float
    net_margin: float
    slippage_estimate: float
    max_executable_size: float
    expected_profit: float
    execution_risk: float
    confidence: str

class MarketAnalyzer:
    def __init__(self):
        self.price_cache = {}

    def calculate_momentum(self, prices: list[float], period: int) -> float:
        if len(prices) < period + 1:
            return 0.0
        return (prices[0] - prices[period]) / prices[period] if prices[period] > 0 else 0

    def calculate_volatility(self, prices: list[float]) -> float:
        if len(prices) < 2:
            return 0.0
        returns = [(prices[i] - prices[i+1]) / prices[i+1]
                   for i in range(len(prices) - 1) if prices[i+1] > 0]
        if not returns:
            return 0.0
        return stdev(returns) if len(returns) > 1 else 0.0

    def calculate_rsi(self, prices: list[float], period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0

        gains, losses = [], []
        for i in range(period):
            change = prices[i] - prices[i + 1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))

        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def calculate_bollinger_position(self, prices: list[float], period: int = 20) -> float:
        if len(prices) < period:
            return 0.0

        sample = prices[:period]
        sma = mean(sample)
        std = stdev(sample) if len(sample) > 1 else 0.001

        upper = sma + 2 * std
        lower = sma - 2 * std

        if upper == lower:
            return 0.0

        return (prices[0] - lower) / (upper - lower) - 0.5

    def analyze_market(self, market: MarketInfo, order_book: OrderBook = None) -> MarketMetrics:
        history = db.get_price_history(market.yes_token.token_id, hours=24)
        prices = [h.price for h in history] if history else [market.yes_token.price]

        bid_ask_ratio = 1.0
        liquidity_score = 0.0

        if order_book:
            if order_book.ask_liquidity > 0:
                bid_ask_ratio = order_book.bid_liquidity / order_book.ask_liquidity
            liquidity_score = min(1.0, (order_book.bid_liquidity + order_book.ask_liquidity) / 1000)

        momentum_1h = self.calculate_momentum(prices, 12) if len(prices) > 12 else 0
        momentum_24h = self.calculate_momentum(prices, len(prices) - 1) if len(prices) > 1 else 0
        volatility = self.calculate_volatility(prices)

        rsi = self.calculate_rsi(prices)
        mean_reversion = (50 - rsi) / 50

        self.calculate_bollinger_position(prices)
        trend_strength = abs(momentum_24h) * (1 - volatility)

        return MarketMetrics(
            token_id=market.yes_token.token_id,
            current_price=market.yes_token.price,
            momentum_1h=momentum_1h,
            momentum_24h=momentum_24h,
            volatility_24h=volatility,
            volume_trend=market.volume_24h / max(1, market.liquidity),
            bid_ask_ratio=bid_ask_ratio,
            liquidity_score=liquidity_score,
            mean_reversion_signal=mean_reversion,
            trend_strength=trend_strength
        )

    def calculate_kelly_criterion(
        self,
        win_prob: float,
        win_payout: float,
        loss_amount: float
    ) -> float:
        if win_payout <= 0 or loss_amount <= 0:
            return 0.0

        b = win_payout / loss_amount
        p = win_prob
        q = 1 - p

        kelly = (b * p - q) / b
        return max(0.0, min(1.0, kelly))

    def calculate_risk_metrics(
        self,
        market: MarketInfo,
        metrics: MarketMetrics,
        side: str,
        confidence_override: float = None
    ) -> RiskMetrics:
        price = market.yes_token.price if side.upper() == "YES" else market.no_token.price

        if confidence_override is not None:
            win_prob = confidence_override
        else:
            base_prob = price
            momentum_adj = metrics.momentum_24h * 0.1
            liquidity_adj = (metrics.liquidity_score - 0.5) * 0.05
            win_prob = max(0.1, min(0.9, base_prob + momentum_adj + liquidity_adj))

        loss_prob = 1 - win_prob

        win_payout = (1 - price) / price if price > 0 else 0
        loss_amount = 1.0

        risk_reward = win_payout * win_prob / (loss_amount * loss_prob) if loss_prob > 0 else 0

        kelly = self.calculate_kelly_criterion(win_prob, win_payout, loss_amount)

        volatility_factor = 1 - min(0.5, metrics.volatility_24h * 5)
        liquidity_factor = metrics.liquidity_score

        confidence = (win_prob * 0.4 + liquidity_factor * 0.3 + volatility_factor * 0.3)

        returns_if_win = win_payout
        returns_if_loss = -1.0

        simulated_returns = sorted([
            returns_if_win if i < int(win_prob * 100) else returns_if_loss
            for i in range(100)
        ])

        var_95 = abs(simulated_returns[4])
        cvar_95 = abs(mean(simulated_returns[:5]))

        expected_value = win_prob * win_payout - loss_prob * loss_amount

        return RiskMetrics(
            expected_value=expected_value,
            win_probability=win_prob,
            loss_probability=loss_prob,
            risk_reward_ratio=risk_reward,
            kelly_fraction=kelly,
            max_position_size=kelly * 100,
            confidence_score=confidence,
            var_95=var_95,
            cvar_95=cvar_95
        )

class ArbitrageAnalyzer:
    TAKER_FEE = 0.001
    MAKER_FEE = 0.0005

    def __init__(self, slippage_model: str = "linear"):
        self.slippage_model = slippage_model

    def estimate_slippage(self, order_book: OrderBook, size: float) -> float:
        total_liquidity = order_book.ask_liquidity
        if total_liquidity <= 0:
            return 0.1

        liquidity_ratio = size / total_liquidity

        if self.slippage_model == "linear":
            return liquidity_ratio * 0.02
        elif self.slippage_model == "sqrt":
            return math.sqrt(liquidity_ratio) * 0.015
        else:
            return liquidity_ratio ** 0.5 * 0.02

    def analyze_arbitrage(
        self,
        market: MarketInfo,
        yes_book: OrderBook,
        no_book: OrderBook,
        position_size: float
    ) -> ArbitrageAnalysis:
        yes_ask = yes_book.best_ask
        no_ask = no_book.best_ask

        gross_margin = 1.0 - (yes_ask + no_ask)

        total_fees = self.TAKER_FEE * 2

        yes_slippage = self.estimate_slippage(yes_book, position_size / 2)
        no_slippage = self.estimate_slippage(no_book, position_size / 2)
        total_slippage = yes_slippage + no_slippage

        net_margin = gross_margin - total_fees - total_slippage

        min_liq = min(yes_book.ask_liquidity, no_book.ask_liquidity)
        max_size = min_liq * 0.3

        expected_profit = position_size * max(0, net_margin)

        execution_risk = 0.0
        if yes_book.spread > 0.02:
            execution_risk += 0.2
        if no_book.spread > 0.02:
            execution_risk += 0.2
        if total_slippage > 0.01:
            execution_risk += 0.2
        if min_liq < 100:
            execution_risk += 0.2

        execution_risk = min(1.0, execution_risk)

        if net_margin >= 0.03 and execution_risk < 0.3:
            confidence = "HIGH"
        elif net_margin >= 0.015 and execution_risk < 0.5:
            confidence = "MEDIUM"
        elif net_margin > 0:
            confidence = "LOW"
        else:
            confidence = "NONE"

        return ArbitrageAnalysis(
            market=market,
            yes_book=yes_book,
            no_book=no_book,
            gross_margin=gross_margin,
            net_margin=net_margin,
            slippage_estimate=total_slippage,
            max_executable_size=max_size,
            expected_profit=expected_profit,
            execution_risk=execution_risk,
            confidence=confidence
        )

    def find_multi_market_arbitrage(
        self,
        markets: list[MarketInfo],
        books: dict
    ) -> list[ArbitrageAnalysis]:
        opportunities = []

        for market in markets:
            yes_book = books.get(market.yes_token.token_id)
            no_book = books.get(market.no_token.token_id)

            if not yes_book or not no_book:
                continue

            analysis = self.analyze_arbitrage(market, yes_book, no_book, 20.0)

            if analysis.confidence != "NONE":
                opportunities.append(analysis)

        opportunities.sort(key=lambda x: x.net_margin, reverse=True)
        return opportunities

market_analyzer = MarketAnalyzer()
arbitrage_analyzer = ArbitrageAnalyzer()
