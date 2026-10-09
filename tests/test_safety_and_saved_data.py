import asyncio
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from polymarket_bot.api.server import APIServer
from polymarket_bot.backtesting.engine import BacktestEngine
from polymarket_bot.bot import PolymarketBot, monitor_mode
from polymarket_bot.client import OrderBook, PolymarketClient
from polymarket_bot.config import TradingConfig, config
from polymarket_bot.data.database import Database
from polymarket_bot.portfolio import PortfolioManager
from polymarket_bot.strategies.arbitrage import ArbitrageStrategy
from polymarket_bot.strategies.base import StrategyResult, StrategyType
from polymarket_bot.utils.rate_limiter import RateLimiter


def test_read_only_client_never_loads_or_uses_wallet():
    with patch("polymarket_bot.client.keystore") as store, patch("polymarket_bot.client.ClobClient") as clob:
        client = PolymarketClient("unused-key", funder="unused-funder", read_only=True)
        store.load_private_key.assert_not_called()
        assert client.private_key is None
        assert client.funder is None
        assert client.get_balance() == 0
        clob.assert_not_called()
        assert client.clob is clob.return_value
        clob.assert_called_once_with(config.host)
        clob.return_value.create_or_derive_api_creds.assert_not_called()


@pytest.mark.asyncio
async def test_dry_run_starts_with_read_only_client():
    bot = PolymarketBot(dry_run=True)
    bot._run_loop = AsyncMock()
    with patch("polymarket_bot.bot.PolymarketClient") as client, patch("polymarket_bot.bot.keystore") as store, patch("polymarket_bot.bot.alert_manager.send_alert", new_callable=AsyncMock):
        client.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
        client.return_value.__aexit__ = AsyncMock(return_value=None)
        await bot.start()
        client.assert_called_once_with(None, None, read_only=True)
        store.load_private_key.assert_not_called()


@pytest.mark.asyncio
async def test_monitor_starts_with_read_only_client():
    public_client = MagicMock()
    public_client.get_events = AsyncMock(return_value=[])
    with patch("polymarket_bot.bot.PolymarketClient") as client, patch("polymarket_bot.bot.asyncio.sleep", new_callable=AsyncMock, side_effect=asyncio.CancelledError):
        client.return_value.__aenter__ = AsyncMock(return_value=public_client)
        client.return_value.__aexit__ = AsyncMock(return_value=None)
        with pytest.raises(asyncio.CancelledError):
            await monitor_mode()
        client.assert_called_once_with(read_only=True)


@pytest.mark.parametrize("operation", [
    lambda client: client.place_market_order("token", 1, "BUY"),
    lambda client: client.place_limit_order("token", 0.5, 1, "BUY"),
    lambda client: client.cancel_order("order"),
    lambda client: client.cancel_all_orders(),
])
def test_read_only_wallet_operations_fail_before_sdk(operation):
    with patch("polymarket_bot.client.ClobClient") as clob:
        with pytest.raises(PermissionError):
            operation(PolymarketClient(read_only=True))
        clob.assert_not_called()


@pytest.mark.parametrize("amount,side", [(0, "BUY"), (-1, "BUY"), (float("nan"), "BUY"), (True, "BUY"), (1, "BOTH")])
def test_invalid_order_never_reaches_sdk(amount, side):
    with patch("polymarket_bot.client.ClobClient") as clob:
        client = PolymarketClient("unused-key")
        with pytest.raises(ValueError):
            client.place_market_order("token", amount, side)
        clob.assert_not_called()


def test_order_book_best_prices_and_depth_do_not_depend_on_response_order():
    book = OrderBook.from_raw({
        "bids": [{"price": "0.2", "size": "10"}, {"price": "0.48", "size": "20"}],
        "asks": [{"price": "0.8", "size": "10"}, {"price": "0.5", "size": "20"}],
    })
    assert book.best_bid == 0.48
    assert book.best_ask == 0.5
    assert book.mid_price == 0.49
    assert book.bid_liquidity == pytest.approx(11.6)
    assert book.ask_liquidity == 18


@pytest.mark.parametrize("price,size", [("nan", "1"), ("1.1", "1"), ("0.5", "-1"), ("0.5", "inf")])
def test_malformed_order_book_is_rejected(price, size):
    with pytest.raises(ValueError):
        OrderBook.from_raw({"asks": [{"price": price, "size": size}]})


@pytest.mark.asyncio
async def test_generic_arbitrage_execution_does_not_record_both_as_no():
    client, portfolio = MagicMock(), MagicMock()
    portfolio.open_position = AsyncMock()
    result = StrategyResult(StrategyType.ARBITRAGE, MagicMock(), "BUY", "BOTH", 10, 0.95, 0.5, 0.9, "fixture")
    assert not await ArbitrageStrategy(client, portfolio).execute(result)
    portfolio.open_position.assert_not_called()
    client.place_market_order.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("side,size,price", [("BOTH", 1, 0.5), ("YES", 0, 0.5), ("YES", 1, float("nan"))])
async def test_invalid_local_positions_do_not_mutate_database(side, size, price):
    with patch("polymarket_bot.portfolio.db") as database:
        assert not await PortfolioManager(MagicMock()).open_position(MagicMock(), side, size, price, "value")
        database.update_portfolio.assert_not_called()
        database.record_trade.assert_not_called()


def test_database_time_windows_compare_times_on_the_cutoff_date(tmp_path):
    database = Database(str(tmp_path / "history.db"))
    now = datetime.now(UTC)
    database.record_price("token", "market", 0.5)
    database.record_trade("market", "token", "BUY", 0.5, 10, 0, "value")
    hours = now.hour + 1
    old = (now - timedelta(hours=hours + 1)).isoformat()
    with database._get_conn() as conn:
        conn.execute("UPDATE price_history SET timestamp = ?", (old,))
        conn.execute("UPDATE trades SET timestamp = ?", (old,))
    assert database.get_price_history("token", hours=hours) == []
    assert database.get_trades(hours=hours) == []
    assert len(database.get_price_history("token", hours=hours + 2)) == 1
    assert len(database.get_trades(hours=hours + 2)) == 1


@pytest.mark.asyncio
async def test_backtest_saved_database_keeps_markets_and_cash_separate(tmp_path):
    database = Database(str(tmp_path / "backtest.db"))
    snapshots = json.loads((Path(__file__).parent / "fixtures" / "backtest_snapshots.json").read_text())
    with database._get_conn() as conn:
        for snapshot in snapshots:
            conn.execute(
                "INSERT INTO market_snapshots (market_id, question, yes_price, no_price, volume_24h, liquidity, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (snapshot["market_id"], snapshot["question"], snapshot["yes_price"], snapshot["no_price"], 1000, 1000, snapshot["timestamp"]),
            )
    engine = BacktestEngine(1000)
    with patch("polymarket_bot.backtesting.engine.db", database):
        result = await engine.run("value", "2024-01-01", "2024-01-04")
        assert result["final_capital"] == pytest.approx(1001.05)
        assert result["total_trades"] == 2
        assert result["equity_curve"][1]["value"] == pytest.approx(1000.75)
        assert result["equity_curve"][-1]["value"] == pytest.approx(result["final_capital"])
        assert {trade["market"]: trade["exitPrice"] for trade in result["trades"]} == {"Market A": 0.40, "Market B": 0.37}
        json.dumps(result, allow_nan=False)
        filtered = await engine.run("value", "2024-01-01", "2024-01-04", ["market-b"])
        assert filtered["total_trades"] == 1
        assert filtered["final_capital"] == pytest.approx(1000.30)


@pytest.mark.asyncio
async def test_backtest_never_exits_a_position_using_another_market():
    engine = BacktestEngine(1000)
    snapshots = [
        {"date": "2024-01-01T01:00:00Z", "market_id": "a", "yes_price": 0.35, "no_price": 0.65},
        {"date": "2024-01-01T02:00:00Z", "market_id": "b", "yes_price": 0.35, "no_price": 0.65},
        {"date": "2024-01-02T01:00:00Z", "market_id": "b", "yes_price": 0.65, "no_price": 0.35},
        {"date": "2024-01-03T01:00:00Z", "market_id": "a", "yes_price": 0.35, "no_price": 0.65},
    ]
    with patch.object(engine, "_load_historical_data", new_callable=AsyncMock, return_value=snapshots):
        result = await engine.run("value", "2024-01-01", "2024-01-04")
    assert result["final_capital"] == pytest.approx(1004.5)
    assert sorted(trade["pnl"] for trade in result["trades"]) == [0, pytest.approx(4.5)]


@pytest.mark.asyncio
async def test_backtest_constant_downside_returns_are_json_safe():
    engine = BacktestEngine(20)
    prices = [0.35, (19.6875 - 14.75) / 15, (19.3798828125 - 14.75) / 15]
    snapshots = [
        {"date": f"2024-01-0{day}T00:00:00Z", "market_id": "saved-market", "yes_price": price, "no_price": 1 - price}
        for day, price in enumerate(prices, start=1)
    ]
    with patch.object(engine, "_load_historical_data", new_callable=AsyncMock, return_value=snapshots):
        result = await engine.run("value", "2024-01-01", "2024-01-03")
    assert result["final_capital"] == pytest.approx(19.3798828125)
    assert [point["value"] for point in result["equity_curve"]] == pytest.approx([20, 19.6875, 19.3798828125])
    assert result["sortino_ratio"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.asyncio
async def test_backtest_endpoint_returns_valid_json_for_empty_history(aiohttp_client, tmp_path):
    client = await aiohttp_client(APIServer().app)
    with patch("polymarket_bot.backtesting.engine.db", Database(str(tmp_path / "empty.db"))):
        response = await client.post("/api/backtest", json={
            "strategy": "value", "startDate": "2024-01-01", "endDate": "2024-01-02", "initialCapital": 1000,
        })
    assert response.status == 200
    result = await response.json()
    assert result["final_capital"] == 1000
    assert result["profit_factor"] is None
    assert result["sortino_ratio"] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize("capital", [0, -1, float("inf"), float("nan"), True, "100"])
def test_invalid_backtest_capital(capital):
    with pytest.raises(ValueError):
        BacktestEngine(capital)


@pytest.mark.asyncio
@pytest.mark.parametrize("strategy,start,end", [
    ("unknown", "2024-01-01", "2024-01-02"),
    ("value", "2024-01-02", "2024-01-01"),
    ("value", "2000-01-01", "2024-01-01"),
])
async def test_invalid_backtest_request_rejected_before_loading_data(strategy, start, end):
    engine = BacktestEngine()
    with patch.object(engine, "_load_historical_data", new_callable=AsyncMock) as load:
        with pytest.raises(ValueError):
            await engine.run(strategy, start, end)
        load.assert_not_called()


@pytest.mark.asyncio
async def test_settings_validation_is_atomic(aiohttp_client):
    original = config.trading
    original_values = asdict(original)
    client = await aiohttp_client(APIServer().app)
    try:
        for settings in (
            {"maxPositionUsd": 75, "stopLossPct": -1},
            {"maxPositionUsd": "75"},
            {"maxPositionUsd": True},
            {"kellyFraction": float("nan")},
            {"__class__": "invalid"},
        ):
            response = await client.put("/api/settings", json={"trading": settings})
            assert response.status == 400
            assert asdict(config.trading) == original_values
        response = await client.put("/api/settings", json={"trading": {"maxPositionUsd": 75, "stopLossPct": 0.2}})
        assert response.status == 200
        assert config.trading.max_position_usd == 75
        assert config.trading.stop_loss_pct == 0.2
    finally:
        config.trading = original


@pytest.mark.parametrize("updates", [{"max_position_usd": -1}, {"max_slippage": 2}, {"cooldown_seconds": 1.5}])
def test_invalid_trading_config(updates):
    with pytest.raises(ValueError):
        TradingConfig(**updates)


def test_take_profit_fraction_can_exceed_one():
    assert TradingConfig(take_profit_pct=2).take_profit_pct == 2


@pytest.mark.asyncio
async def test_rate_limiter_records_acquisition_after_wait():
    clock = [0.0]

    async def advance(seconds):
        clock[0] += seconds

    limiter = RateLimiter(requests_per_second=2)
    acquired = []
    with patch("polymarket_bot.utils.rate_limiter.time.monotonic", side_effect=lambda: clock[0]), patch("polymarket_bot.utils.rate_limiter.asyncio.sleep", side_effect=advance):
        for _ in range(5):
            await limiter.acquire()
            acquired.append(clock[0])
    assert acquired == [0, 0, 1, 1, 2]
