import pytest
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from polymarket_bot.backtesting.engine import (
    BacktestEngine,
    BacktestTrade,
    ArbitrageBacktestStrategy,
    BondingBacktestStrategy,
    ValueBacktestStrategy,
)
from polymarket_bot.backtesting.mock_data import (
    generate_mock_market,
    generate_arbitrage_opportunity_market,
    generate_trending_market,
    generate_mock_dataset,
    markets_to_snapshots,
)


class TestBacktestEngine:
    @pytest.fixture
    def engine(self):
        return BacktestEngine(initial_capital=1000.0)

    @pytest.mark.asyncio
    async def test_run_returns_result_dict(self, engine):
        with patch.object(engine, '_load_historical_data', new_callable=AsyncMock) as mock_load:
            mock_load.return_value = [
                {
                    "date": datetime.now(UTC).isoformat(),
                    "market_id": "test-market",
                    "market_name": "Test Market",
                    "yes_price": 0.5,
                    "no_price": 0.5,
                    "volume": 10000,
                    "liquidity": 1000
                }
            ]

            result = await engine.run(
                strategy="arbitrage",
                start_date=(datetime.now(UTC) - timedelta(days=7)).isoformat(),
                end_date=datetime.now(UTC).isoformat()
            )

            assert isinstance(result, dict)
            assert "strategy" in result
            assert "initial_capital" in result
            assert "final_capital" in result
            assert "total_return" in result

    def test_calculate_exposure_empty_positions(self, engine):
        engine.capital = 1000.0
        engine.positions = {}
        exposure = engine._calculate_exposure()
        assert exposure == 0.0

    def test_calculate_exposure_with_positions(self, engine):
        engine.capital = 500.0
        engine.positions = {
            "pos1": MagicMock(size=100, entry_price=0.5),
            "pos2": MagicMock(size=200, entry_price=0.5)
        }
        exposure = engine._calculate_exposure()
        assert 0 < exposure < 1

    def test_calculate_portfolio_value(self, engine):
        engine.capital = 500.0
        engine.positions = {
            "pos1": MagicMock(size=100, entry_price=0.5)
        }
        value = engine._calculate_portfolio_value()
        assert value == 550.0

    def test_can_open_position_with_capital(self, engine):
        engine.capital = 1000.0
        engine.positions = {}
        assert engine._can_open_position(50.0) is True

    def test_cannot_open_position_high_exposure(self, engine):
        engine.capital = 100.0
        engine.positions = {
            f"pos{i}": MagicMock(size=100, entry_price=0.5)
            for i in range(10)
        }
        assert engine._can_open_position(50.0) is False

    def test_calculate_sharpe_ratio(self, engine):
        returns = [0.01, 0.02, -0.01, 0.015, 0.005]
        sharpe = engine._calculate_sharpe(returns)
        assert isinstance(sharpe, float)

    def test_calculate_sharpe_empty_returns(self, engine):
        sharpe = engine._calculate_sharpe([])
        assert sharpe == 0.0

    def test_calculate_max_drawdown(self, engine):
        engine.equity_curve = [
            {"value": 1000},
            {"value": 1100},
            {"value": 1050},
            {"value": 900},
            {"value": 950}
        ]
        drawdown = engine._calculate_max_drawdown()
        assert abs(drawdown - 0.1818) < 0.01


class TestArbitrageBacktestStrategy:
    @pytest.fixture
    def strategy(self):
        return ArbitrageBacktestStrategy()

    def test_should_enter_with_spread(self, strategy):
        market_data = {"yes_price": 0.45, "no_price": 0.50}
        portfolio = {"exposure": 0.2}
        
        should_enter, side, size = strategy.should_enter(market_data, portfolio)
        assert should_enter is True
        assert size > 0

    def test_should_not_enter_no_spread(self, strategy):
        market_data = {"yes_price": 0.50, "no_price": 0.50}
        portfolio = {"exposure": 0.2}
        
        should_enter, _, _ = strategy.should_enter(market_data, portfolio)
        assert should_enter is False

    def test_should_not_enter_high_exposure(self, strategy):
        market_data = {"yes_price": 0.45, "no_price": 0.50}
        portfolio = {"exposure": 0.6}
        
        should_enter, _, _ = strategy.should_enter(market_data, portfolio)
        assert should_enter is False

    def test_should_exit_when_spread_closes(self, strategy):
        position = {"outcome": "YES", "entry_price": 0.45}
        market_data = {"yes_price": 0.50, "no_price": 0.50}
        
        assert strategy.should_exit(position, market_data) is True

    def test_should_not_exit_spread_remains(self, strategy):
        position = {"outcome": "YES", "entry_price": 0.45}
        market_data = {"yes_price": 0.45, "no_price": 0.52}
        
        assert strategy.should_exit(position, market_data) is False


class TestBondingBacktestStrategy:
    @pytest.fixture
    def strategy(self):
        return BondingBacktestStrategy()

    def test_should_enter_high_yes_probability(self, strategy):
        market_data = {"yes_price": 0.95, "no_price": 0.05}
        portfolio = {"exposure": 0.2}
        
        should_enter, side, size = strategy.should_enter(market_data, portfolio)
        assert should_enter is True
        assert side == "YES"

    def test_should_enter_high_no_probability(self, strategy):
        market_data = {"yes_price": 0.05, "no_price": 0.95}
        portfolio = {"exposure": 0.2}
        
        should_enter, side, size = strategy.should_enter(market_data, portfolio)
        assert should_enter is True
        assert side == "NO"

    def test_should_not_enter_low_probability(self, strategy):
        market_data = {"yes_price": 0.60, "no_price": 0.40}
        portfolio = {"exposure": 0.2}
        
        should_enter, _, _ = strategy.should_enter(market_data, portfolio)
        assert should_enter is False

    def test_should_exit_on_profit(self, strategy):
        position = {"outcome": "YES", "entry_price": 0.90}
        market_data = {"yes_price": 0.96}
        
        assert strategy.should_exit(position, market_data) is True

    def test_should_exit_on_loss(self, strategy):
        position = {"outcome": "YES", "entry_price": 0.95}
        market_data = {"yes_price": 0.80}
        
        assert strategy.should_exit(position, market_data) is True


class TestValueBacktestStrategy:
    @pytest.fixture
    def strategy(self):
        return ValueBacktestStrategy()

    def test_should_enter_undervalued(self, strategy):
        market_data = {"yes_price": 0.35}
        portfolio = {"exposure": 0.2}
        
        should_enter, side, _ = strategy.should_enter(market_data, portfolio)
        assert should_enter is True
        assert side == "YES"

    def test_should_not_enter_overexposed(self, strategy):
        market_data = {"yes_price": 0.35}
        portfolio = {"exposure": 0.4}
        
        should_enter, _, _ = strategy.should_enter(market_data, portfolio)
        assert should_enter is False


class TestMockDataGeneration:
    def test_generate_mock_market(self):
        market = generate_mock_market(
            "test-id",
            "Test question?",
            datetime.now(UTC),
            days=7
        )
        
        assert market.condition_id == "test-id"
        assert len(market.yes_prices) == 7 * 24
        assert len(market.no_prices) == 7 * 24
        assert all(0 < p < 1 for p in market.yes_prices)

    def test_generate_arbitrage_opportunity_market(self):
        market = generate_arbitrage_opportunity_market(
            "arb-id",
            "Arb market?",
            datetime.now(UTC),
            days=7,
            opportunity_frequency=0.5
        )
        
        has_opportunity = any(
            (1 - market.yes_prices[i] - market.no_prices[i]) > 0.02
            for i in range(len(market.yes_prices))
        )
        assert has_opportunity

    def test_generate_trending_market(self):
        market = generate_trending_market(
            "trend-id",
            "Trending market?",
            datetime.now(UTC),
            days=7,
            trend_direction=0.3
        )
        
        assert market.yes_prices[-1] > market.yes_prices[0]

    def test_generate_mock_dataset(self):
        dataset = generate_mock_dataset(num_markets=5, days=7)
        assert len(dataset) == 5
        
        for market in dataset:
            assert market.condition_id
            assert market.question

    def test_markets_to_snapshots(self):
        markets = generate_mock_dataset(num_markets=2, days=1)
        snapshots = markets_to_snapshots(markets)
        
        assert len(snapshots) > 0
        assert "timestamp" in snapshots[0]
        assert "yes_price" in snapshots[0]
        
        timestamps = [s["timestamp"] for s in snapshots]
        assert timestamps == sorted(timestamps)


class TestBacktestTrade:
    def test_trade_creation(self):
        trade = BacktestTrade(
            timestamp=datetime.now(UTC),
            market_id="test",
            market_name="Test Market",
            side="BUY",
            outcome="YES",
            size=50.0,
            entry_price=0.5,
            strategy="arbitrage"
        )
        
        assert trade.pnl == 0.0
        assert trade.exit_price is None

    def test_trade_pnl_calculation(self):
        trade = BacktestTrade(
            timestamp=datetime.now(UTC),
            market_id="test",
            market_name="Test Market",
            side="BUY",
            outcome="YES",
            size=100.0,
            entry_price=0.5,
            exit_price=0.6,
            strategy="arbitrage"
        )
        trade.pnl = trade.size * (trade.exit_price - trade.entry_price)
        
        assert abs(trade.pnl - 10.0) < 0.001
