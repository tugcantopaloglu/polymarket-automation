import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web

from polymarket_bot.api.server import APIServer


class TestAPIServer:
    @pytest.fixture
    def mock_bot(self):
        bot = MagicMock()
        bot._running = True
        bot._markets_cache = {}
        bot.portfolio = MagicMock()
        bot.strategies = {}
        return bot

    @pytest.fixture
    def api_server(self, mock_bot):
        return APIServer(bot=mock_bot, port=8081)

    def test_server_initialization(self, api_server):
        assert api_server.host == "0.0.0.0"
        assert api_server.port == 8081
        assert api_server.app is not None

    def test_routes_registered(self, api_server):
        routes = [r.resource.canonical for r in api_server.app.router.routes()]
        assert "/api/health" in routes
        assert "/api/dashboard" in routes
        assert "/api/portfolio" in routes
        assert "/api/trades" in routes
        assert "/api/markets" in routes
        assert "/api/alerts" in routes

    def test_camel_to_snake(self, api_server):
        assert api_server._camel_to_snake("minProfitMargin") == "min_profit_margin"
        assert api_server._camel_to_snake("maxPositionUsd") == "max_position_usd"
        assert api_server._camel_to_snake("simple") == "simple"

    def test_format_trade(self, api_server):
        mock_trade = MagicMock(
            id=123,
            market_name="Test Market",
            side="BUY",
            outcome="YES",
            size=50.0,
            price=0.45,
            pnl=5.0,
            strategy="arbitrage",
            timestamp=datetime.now(UTC)
        )
        
        formatted = api_server._format_trade(mock_trade)
        
        assert formatted["id"] == "123"
        assert formatted["market"] == "Test Market"
        assert formatted["side"] == "BUY"
        assert formatted["size"] == 50.0

    def test_format_trade_dict_input(self, api_server):
        trade_dict = {
            "id": 456,
            "market_name": "Dict Market",
            "side": "SELL",
            "outcome": "NO",
            "size": 25.0,
            "price": 0.55,
            "pnl": -2.0,
            "strategy": "momentum",
            "timestamp": "2024-01-15T10:00:00"
        }
        
        formatted = api_server._format_trade(trade_dict)
        
        assert formatted["id"] == "456"
        assert formatted["market"] == "Dict Market"

    def test_format_alert(self, api_server):
        mock_alert = MagicMock(
            id=789,
            alert_type="arbitrage",
            title="Test Alert",
            message="Alert message",
            severity="info",
            timestamp=datetime.now(UTC)
        )
        
        formatted = api_server._format_alert(mock_alert)
        
        assert formatted["id"] == "789"
        assert formatted["type"] == "arbitrage"
        assert formatted["title"] == "Test Alert"

    def test_format_position(self, api_server):
        mock_position = MagicMock(
            token_id="token-123",
            market_id="market-456",
            outcome="YES",
            size=100.0,
            entry_price=0.40,
            current_price=0.45,
            unrealized_pnl=5.0
        )
        
        formatted = api_server._format_position(mock_position)
        
        assert formatted["tokenId"] == "token-123"
        assert formatted["size"] == 100.0
        assert formatted["unrealizedPnl"] == 5.0

    @pytest.mark.asyncio
    async def test_get_portfolio_data_with_bot(self, api_server, mock_bot):
        mock_stats = MagicMock(
            total_value=1000.0,
            unrealized_pnl=50.0,
            realized_pnl_today=25.0,
            win_rate=0.65,
            exposure=0.30,
            max_drawdown=0.05,
            sharpe_ratio=1.5,
            num_positions=3
        )
        mock_bot.portfolio.get_stats = AsyncMock(return_value=mock_stats)
        
        data = await api_server._get_portfolio_data()
        
        assert data["totalValue"] == 1000.0
        assert data["unrealizedPnl"] == 50.0
        assert data["winRate"] == 0.65

    @pytest.mark.asyncio
    async def test_get_portfolio_data_no_bot(self, api_server):
        api_server.bot = None
        
        data = await api_server._get_portfolio_data()
        
        assert data["totalValue"] == 0
        assert data["numPositions"] == 0

    def test_get_strategy_data_with_strategies(self, api_server, mock_bot):
        mock_strategy = MagicMock()
        mock_strategy.get_stats.return_value = {
            "trades_executed": 10,
            "opportunities_found": 50,
            "enabled": True
        }
        mock_bot.strategies = {"arbitrage": mock_strategy}
        
        with patch('polymarket_bot.api.server.db') as mock_db:
            mock_db.get_strategy_stats.return_value = [{"total_pnl": 100, "win_rate": 0.8}]
            
            data = api_server._get_strategy_data()
        
        assert len(data) == 1
        assert data[0]["name"] == "arbitrage"
        assert data[0]["trades"] == 10

    def test_get_strategy_data_no_strategies(self, api_server, mock_bot):
        mock_bot.strategies = {}
        
        data = api_server._get_strategy_data()
        
        assert data == []


@pytest.fixture
def mock_bot_for_client():
    bot = MagicMock()
    bot._running = True
    bot._markets_cache = {}
    bot.portfolio = MagicMock()
    bot.strategies = {}
    return bot


@pytest.fixture
async def api_client(aiohttp_client, mock_bot_for_client):
    server = APIServer(bot=mock_bot_for_client)
    return await aiohttp_client(server.app)


class TestAPIEndpointsIntegration:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, api_client):
        resp = await api_client.get("/api/health")
        assert resp.status == 200
        
        data = await resp.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_settings_endpoint(self, api_client):
        resp = await api_client.get("/api/settings")
        assert resp.status == 200
        
        data = await resp.json()
        assert "trading" in data
        assert "alerts" in data
        assert "rateLimit" in data

    @pytest.mark.asyncio
    async def test_markets_endpoint_empty(self, api_client):
        resp = await api_client.get("/api/markets")
        assert resp.status == 200
        
        data = await resp.json()
        assert "markets" in data
        assert "count" in data
