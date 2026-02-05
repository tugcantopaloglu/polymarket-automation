import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from polymarket_bot.strategies.base import Strategy, StrategyResult, StrategyType
from polymarket_bot.strategies.arbitrage import ArbitrageStrategy
from polymarket_bot.strategies.bonding import BondingStrategy
from polymarket_bot.strategies.momentum import MomentumStrategy
from polymarket_bot.client import MarketInfo, TokenInfo, OrderBook

@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.get_balance.return_value = 100.0
    client.get_order_book = AsyncMock(return_value=OrderBook(
        bids=[], asks=[],
        best_bid=0.48, best_ask=0.50,
        bid_liquidity=500, ask_liquidity=500,
        mid_price=0.49, spread=0.02
    ))
    client.get_order_books_batch = AsyncMock(return_value={})
    return client

@pytest.fixture
def mock_portfolio():
    portfolio = MagicMock()
    portfolio.get_risk_limits.return_value = MagicMock(
        can_trade=True,
        max_position_size=50.0,
        blocked_reason=""
    )
    portfolio.client = MagicMock()
    portfolio.client.get_balance.return_value = 100.0
    return portfolio

@pytest.fixture
def sample_market_for_bonding():
    return MarketInfo(
        condition_id="bonding-market-1",
        question="Will event X happen by tomorrow?",
        yes_token=TokenInfo(
            token_id="yes-token-1",
            outcome="Yes",
            price=0.95,
            volume_24h=5000,
            price_change_24h=0.01
        ),
        no_token=TokenInfo(
            token_id="no-token-1",
            outcome="No",
            price=0.04,
            volume_24h=2000,
            price_change_24h=-0.01
        ),
        volume_24h=7000,
        liquidity=3000,
        end_date=datetime.now(timezone.utc) + timedelta(days=2),
        category="Events"
    )

@pytest.fixture
def sample_market_for_arbitrage():
    return MarketInfo(
        condition_id="arb-market-1",
        question="Will team A win?",
        yes_token=TokenInfo(
            token_id="yes-token-arb",
            outcome="Yes",
            price=0.45,
            volume_24h=10000,
            price_change_24h=0.02
        ),
        no_token=TokenInfo(
            token_id="no-token-arb",
            outcome="No",
            price=0.52,
            volume_24h=8000,
            price_change_24h=-0.02
        ),
        volume_24h=18000,
        liquidity=5000,
        end_date=datetime.now(timezone.utc) + timedelta(days=7),
        category="Sports"
    )

class TestArbitrageStrategy:
    @pytest.mark.asyncio
    async def test_evaluate_no_arbitrage(self, mock_client, mock_portfolio, sample_market_for_arbitrage):
        strategy = ArbitrageStrategy(mock_client, mock_portfolio)
        
        mock_client.get_order_book = AsyncMock(side_effect=[
            OrderBook(
                bids=[], asks=[],
                best_bid=0.49, best_ask=0.51,
                bid_liquidity=500, ask_liquidity=500,
                mid_price=0.50, spread=0.02
            ),
            OrderBook(
                bids=[], asks=[],
                best_bid=0.49, best_ask=0.51,
                bid_liquidity=500, ask_liquidity=500,
                mid_price=0.50, spread=0.02
            )
        ])
        
        result = await strategy.evaluate(sample_market_for_arbitrage)
        assert result is None or not result.is_actionable
    
    def test_strategy_type(self, mock_client, mock_portfolio):
        strategy = ArbitrageStrategy(mock_client, mock_portfolio)
        assert strategy.strategy_type == StrategyType.ARBITRAGE

class TestBondingStrategy:
    @pytest.mark.asyncio
    async def test_evaluate_high_probability(self, mock_client, mock_portfolio, sample_market_for_bonding):
        strategy = BondingStrategy(mock_client, mock_portfolio, min_probability=0.92)
        result = await strategy.evaluate(sample_market_for_bonding)
        
        assert result is not None
        assert result.side == "YES"
        assert result.confidence > 0.5
    
    @pytest.mark.asyncio
    async def test_evaluate_no_end_date(self, mock_client, mock_portfolio):
        market = MarketInfo(
            condition_id="no-end-date",
            question="Perpetual market?",
            yes_token=TokenInfo("yes", "Yes", 0.95, 1000, 0),
            no_token=TokenInfo("no", "No", 0.05, 1000, 0),
            volume_24h=2000,
            liquidity=1000,
            end_date=None,
            category="Other"
        )
        
        strategy = BondingStrategy(mock_client, mock_portfolio)
        result = await strategy.evaluate(market)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_evaluate_too_far_resolution(self, mock_client, mock_portfolio):
        market = MarketInfo(
            condition_id="far-market",
            question="Will something happen far in future?",
            yes_token=TokenInfo("yes", "Yes", 0.95, 1000, 0),
            no_token=TokenInfo("no", "No", 0.05, 1000, 0),
            volume_24h=2000,
            liquidity=1000,
            end_date=datetime.now(timezone.utc) + timedelta(days=30),
            category="Other"
        )
        
        strategy = BondingStrategy(mock_client, mock_portfolio, max_days_to_resolution=14)
        result = await strategy.evaluate(market)
        
        assert result is None
    
    def test_strategy_type(self, mock_client, mock_portfolio):
        strategy = BondingStrategy(mock_client, mock_portfolio)
        assert strategy.strategy_type == StrategyType.BONDING

class TestMomentumStrategy:
    @pytest.mark.asyncio
    async def test_evaluate_low_volume(self, mock_client, mock_portfolio):
        market = MarketInfo(
            condition_id="low-vol-market",
            question="Low volume market",
            yes_token=TokenInfo("yes", "Yes", 0.50, 100, 0.1),
            no_token=TokenInfo("no", "No", 0.50, 100, -0.1),
            volume_24h=500,
            liquidity=200,
            end_date=datetime.now(timezone.utc) + timedelta(days=7),
            category="Other"
        )
        
        strategy = MomentumStrategy(mock_client, mock_portfolio, min_volume=1000)
        result = await strategy.evaluate(market)
        
        assert result is None
    
    def test_strategy_type(self, mock_client, mock_portfolio):
        strategy = MomentumStrategy(mock_client, mock_portfolio)
        assert strategy.strategy_type == StrategyType.MOMENTUM

class TestStrategyResult:
    def test_is_actionable_buy(self):
        result = StrategyResult(
            strategy=StrategyType.ARBITRAGE,
            market=MagicMock(),
            action="BUY",
            side="YES",
            size=10.0,
            price=0.5,
            expected_profit=0.5,
            confidence=0.7,
            reason="test"
        )
        assert result.is_actionable
    
    def test_is_not_actionable_low_confidence(self):
        result = StrategyResult(
            strategy=StrategyType.ARBITRAGE,
            market=MagicMock(),
            action="BUY",
            side="YES",
            size=10.0,
            price=0.5,
            expected_profit=0.5,
            confidence=0.3,
            reason="test"
        )
        assert not result.is_actionable
    
    def test_is_not_actionable_hold(self):
        result = StrategyResult(
            strategy=StrategyType.ARBITRAGE,
            market=MagicMock(),
            action="HOLD",
            side="YES",
            size=10.0,
            price=0.5,
            expected_profit=0.5,
            confidence=0.7,
            reason="test"
        )
        assert not result.is_actionable
