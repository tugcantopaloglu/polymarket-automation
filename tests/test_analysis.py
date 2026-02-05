import pytest
from datetime import datetime, timezone

from polymarket_bot.analysis.market_analyzer import (
    MarketAnalyzer,
    ArbitrageAnalyzer,
    MarketMetrics,
    RiskMetrics
)
from polymarket_bot.client import MarketInfo, TokenInfo, OrderBook

@pytest.fixture
def market_analyzer():
    return MarketAnalyzer()

@pytest.fixture
def arbitrage_analyzer():
    return ArbitrageAnalyzer()

@pytest.fixture
def sample_market():
    return MarketInfo(
        condition_id="test-market-1",
        question="Will Bitcoin reach $100k by end of 2024?",
        yes_token=TokenInfo(
            token_id="yes-token-1",
            outcome="Yes",
            price=0.45,
            volume_24h=10000,
            price_change_24h=0.05
        ),
        no_token=TokenInfo(
            token_id="no-token-1",
            outcome="No",
            price=0.52,
            volume_24h=8000,
            price_change_24h=-0.05
        ),
        volume_24h=18000,
        liquidity=5000,
        end_date=datetime(2024, 12, 31, tzinfo=timezone.utc),
        category="Crypto"
    )

@pytest.fixture
def sample_order_book():
    return OrderBook(
        bids=[{"price": "0.44", "size": "100"}, {"price": "0.43", "size": "200"}],
        asks=[{"price": "0.46", "size": "150"}, {"price": "0.47", "size": "250"}],
        best_bid=0.44,
        best_ask=0.46,
        bid_liquidity=100,
        ask_liquidity=150,
        mid_price=0.45,
        spread=0.02
    )

class TestMarketAnalyzer:
    def test_calculate_momentum(self, market_analyzer):
        prices = [1.0, 0.95, 0.90, 0.85, 0.80]
        momentum = market_analyzer.calculate_momentum(prices, 4)
        assert momentum == pytest.approx(0.25, rel=0.01)
    
    def test_calculate_momentum_insufficient_data(self, market_analyzer):
        prices = [1.0, 0.95]
        momentum = market_analyzer.calculate_momentum(prices, 4)
        assert momentum == 0.0
    
    def test_calculate_volatility(self, market_analyzer):
        prices = [1.0, 1.05, 0.95, 1.02, 0.98]
        volatility = market_analyzer.calculate_volatility(prices)
        assert volatility > 0
    
    def test_calculate_volatility_single_price(self, market_analyzer):
        prices = [1.0]
        volatility = market_analyzer.calculate_volatility(prices)
        assert volatility == 0.0
    
    def test_calculate_rsi(self, market_analyzer):
        prices = list(reversed([45, 46, 47, 48, 49, 50, 49, 48, 47, 46, 45, 44, 43, 42, 41, 40]))
        rsi = market_analyzer.calculate_rsi(prices)
        assert 0 <= rsi <= 100
    
    def test_calculate_kelly_criterion(self, market_analyzer):
        kelly = market_analyzer.calculate_kelly_criterion(
            win_prob=0.6,
            win_payout=1.0,
            loss_amount=1.0
        )
        assert kelly == pytest.approx(0.2, rel=0.01)
    
    def test_calculate_kelly_negative(self, market_analyzer):
        kelly = market_analyzer.calculate_kelly_criterion(
            win_prob=0.3,
            win_payout=1.0,
            loss_amount=1.0
        )
        assert kelly == 0.0
    
    def test_calculate_risk_metrics(self, market_analyzer, sample_market, sample_order_book):
        metrics = market_analyzer.analyze_market(sample_market, sample_order_book)
        risk = market_analyzer.calculate_risk_metrics(sample_market, metrics, "YES")
        
        assert 0 <= risk.win_probability <= 1
        assert 0 <= risk.loss_probability <= 1
        assert risk.win_probability + risk.loss_probability == pytest.approx(1.0)
        assert 0 <= risk.kelly_fraction <= 1
        assert risk.var_95 >= 0
        assert risk.cvar_95 >= 0

class TestArbitrageAnalyzer:
    def test_estimate_slippage(self, arbitrage_analyzer, sample_order_book):
        slippage = arbitrage_analyzer.estimate_slippage(sample_order_book, 10)
        assert slippage >= 0
        assert slippage < 0.1
    
    def test_analyze_arbitrage_opportunity(self, arbitrage_analyzer, sample_market):
        yes_book = OrderBook(
            bids=[], asks=[],
            best_bid=0.44, best_ask=0.47,
            bid_liquidity=500, ask_liquidity=500,
            mid_price=0.455, spread=0.03
        )
        no_book = OrderBook(
            bids=[], asks=[],
            best_bid=0.48, best_ask=0.50,
            bid_liquidity=500, ask_liquidity=500,
            mid_price=0.49, spread=0.02
        )
        
        analysis = arbitrage_analyzer.analyze_arbitrage(
            sample_market, yes_book, no_book, 20.0
        )
        
        assert analysis.gross_margin == pytest.approx(0.03, rel=0.01)
        assert analysis.net_margin <= analysis.gross_margin
        assert analysis.confidence in ["HIGH", "MEDIUM", "LOW", "NONE"]
    
    def test_analyze_no_arbitrage(self, arbitrage_analyzer, sample_market):
        yes_book = OrderBook(
            bids=[], asks=[],
            best_bid=0.49, best_ask=0.51,
            bid_liquidity=500, ask_liquidity=500,
            mid_price=0.50, spread=0.02
        )
        no_book = OrderBook(
            bids=[], asks=[],
            best_bid=0.49, best_ask=0.51,
            bid_liquidity=500, ask_liquidity=500,
            mid_price=0.50, spread=0.02
        )
        
        analysis = arbitrage_analyzer.analyze_arbitrage(
            sample_market, yes_book, no_book, 20.0
        )
        
        assert analysis.gross_margin < 0
        assert analysis.confidence == "NONE"
