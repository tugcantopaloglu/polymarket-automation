from datetime import UTC, datetime
from collections.abc import AsyncGenerator
import asyncio
import json

from aiohttp import web

from ..config import config
from ..data.database import db
from ..utils.logging import get_logger

log = get_logger(__name__)

class APIServer:
    def __init__(self, bot=None, host: str = "0.0.0.0", port: int = 8080):
        self.bot = bot
        self.host = host
        self.port = port
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_get("/api/health", self.health)
        self.app.router.add_get("/api/dashboard", self.dashboard)
        self.app.router.add_get("/api/portfolio", self.portfolio)
        self.app.router.add_get("/api/trades", self.trades)
        self.app.router.add_get("/api/markets", self.markets)
        self.app.router.add_get("/api/alerts", self.alerts)
        self.app.router.add_get("/api/strategies", self.strategies)
        self.app.router.add_post("/api/backtest", self.backtest)
        self.app.router.add_get("/api/stream", self.stream)
        self.app.router.add_get("/api/settings", self.get_settings)
        self.app.router.add_put("/api/settings", self.update_settings)

    async def health(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "ok",
            "timestamp": datetime.now(UTC).isoformat(),
            "bot_running": self.bot._running if self.bot else False
        })

    async def dashboard(self, request: web.Request) -> web.Response:
        portfolio_data = await self._get_portfolio_data()
        strategy_data = self._get_strategy_data()
        recent_trades = db.get_recent_trades(limit=10)
        recent_alerts = db.get_recent_alerts(limit=5)

        return web.json_response({
            "status": "running" if (self.bot and self.bot._running) else "stopped",
            "portfolio": portfolio_data,
            "performance": self._get_performance_data(30),
            "strategies": strategy_data,
            "trades": [self._format_trade(t) for t in recent_trades],
            "alerts": [self._format_alert(a) for a in recent_alerts],
            "opportunities": self._get_opportunities()
        })

    async def portfolio(self, request: web.Request) -> web.Response:
        data = await self._get_portfolio_data()
        positions = db.get_positions()
        return web.json_response({
            **data,
            "positions": [self._format_position(p) for p in positions]
        })

    async def trades(self, request: web.Request) -> web.Response:
        limit = int(request.query.get("limit", 50))
        offset = int(request.query.get("offset", 0))
        strategy = request.query.get("strategy")

        trades = db.get_trades(limit=limit, offset=offset, strategy=strategy)
        total = db.get_trades_count(strategy=strategy)

        return web.json_response({
            "trades": [self._format_trade(t) for t in trades],
            "total": total,
            "limit": limit,
            "offset": offset
        })

    async def markets(self, request: web.Request) -> web.Response:
        if not self.bot or not self.bot._markets_cache:
            return web.json_response({"markets": [], "count": 0})

        markets = []
        for market in list(self.bot._markets_cache.values())[:100]:
            markets.append({
                "conditionId": market.condition_id,
                "question": market.question,
                "yesPrice": market.yes_token.price,
                "noPrice": market.no_token.price,
                "volume24h": market.volume_24h,
                "liquidity": market.liquidity,
                "spread": market.spread,
                "category": market.category,
                "endDate": market.end_date.isoformat() if market.end_date else None
            })

        return web.json_response({
            "markets": markets,
            "count": len(markets)
        })

    async def alerts(self, request: web.Request) -> web.Response:
        limit = int(request.query.get("limit", 20))
        alerts = db.get_recent_alerts(limit=limit)
        return web.json_response({
            "alerts": [self._format_alert(a) for a in alerts]
        })

    async def strategies(self, request: web.Request) -> web.Response:
        return web.json_response({
            "strategies": self._get_strategy_data(),
            "stats": db.get_strategy_stats(days=30)
        })

    async def backtest(self, request: web.Request) -> web.Response:
        try:
            params = await request.json()
            strategy = params.get("strategy", "arbitrage")
            start_date = params.get("startDate")
            end_date = params.get("endDate")
            initial_capital = params.get("initialCapital", 1000)

            from ..backtesting.engine import BacktestEngine
            engine = BacktestEngine(initial_capital=initial_capital)
            result = await engine.run(
                strategy=strategy,
                start_date=start_date,
                end_date=end_date
            )

            return web.json_response(result)
        except Exception as e:
            log.error("backtest_error", error=str(e))
            return web.json_response({"error": str(e)}, status=400)

    async def stream(self, request: web.Request) -> web.StreamResponse:
        response = web.StreamResponse(
            status=200,
            reason="OK",
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )
        await response.prepare(request)

        try:
            while True:
                data = {
                    "type": "update",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "portfolio": await self._get_portfolio_data(),
                    "status": "running" if (self.bot and self.bot._running) else "stopped"
                }
                await response.write(f"data: {json.dumps(data)}\n\n".encode())
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            pass

        return response

    async def get_settings(self, request: web.Request) -> web.Response:
        return web.json_response({
            "trading": {
                "minProfitMargin": config.trading.min_profit_margin,
                "maxPositionUsd": config.trading.max_position_usd,
                "maxDailyLossUsd": config.trading.max_daily_loss_usd,
                "minLiquidityUsd": config.trading.min_liquidity_usd,
                "kellyFraction": config.trading.kelly_fraction,
                "stopLossPct": config.trading.stop_loss_pct,
                "takeProfitPct": config.trading.take_profit_pct
            },
            "alerts": {
                "priceChangeThreshold": config.alerts.price_change_threshold,
                "volumeSpikeThreshold": config.alerts.volume_spike_threshold,
                "telegramEnabled": bool(config.alerts.telegram_bot_token),
                "discordEnabled": bool(config.alerts.discord_webhook_url)
            },
            "rateLimit": {
                "requestsPerSecond": config.rate_limit.requests_per_second,
                "burstLimit": config.rate_limit.burst_limit
            }
        })

    async def update_settings(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            
            if "trading" in data:
                for key, value in data["trading"].items():
                    snake_key = self._camel_to_snake(key)
                    if hasattr(config.trading, snake_key):
                        setattr(config.trading, snake_key, value)

            return web.json_response({"status": "updated"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def _get_portfolio_data(self) -> dict:
        if self.bot and self.bot.portfolio:
            stats = await self.bot.portfolio.get_stats()
            return {
                "totalValue": stats.total_value,
                "unrealizedPnl": stats.unrealized_pnl,
                "realizedPnlToday": stats.realized_pnl_today,
                "winRate": stats.win_rate,
                "exposure": stats.exposure,
                "maxDrawdown": stats.max_drawdown,
                "sharpeRatio": stats.sharpe_ratio,
                "numPositions": stats.num_positions
            }
        return {
            "totalValue": 0,
            "unrealizedPnl": 0,
            "realizedPnlToday": 0,
            "winRate": 0,
            "exposure": 0,
            "maxDrawdown": 0,
            "sharpeRatio": 0,
            "numPositions": 0
        }

    def _get_strategy_data(self) -> list:
        if not self.bot or not self.bot.strategies:
            return []

        result = []
        for name, strategy in self.bot.strategies.items():
            stats = strategy.get_stats()
            db_stats = db.get_strategy_stats(days=30, strategy=name)
            pnl = sum(s.get("total_pnl", 0) for s in db_stats)

            result.append({
                "name": name,
                "trades": stats["trades_executed"],
                "winRate": db_stats[0].get("win_rate", 0) if db_stats else 0,
                "pnl": pnl,
                "opportunities": stats["opportunities_found"],
                "enabled": stats["enabled"]
            })
        return result

    def _get_performance_data(self, days: int) -> list:
        snapshots = db.get_portfolio_snapshots(days=days)
        return [
            {
                "date": s.date.isoformat() if hasattr(s, 'date') else str(s.get('date', '')),
                "value": s.value if hasattr(s, 'value') else s.get('value', 0),
                "pnl": s.pnl if hasattr(s, 'pnl') else s.get('pnl', 0)
            }
            for s in snapshots
        ]

    def _get_opportunities(self) -> list:
        return []

    def _format_trade(self, trade) -> dict:
        return {
            "id": str(trade.id if hasattr(trade, 'id') else trade.get('id', '')),
            "market": trade.market_name if hasattr(trade, 'market_name') else trade.get('market_name', ''),
            "side": trade.side if hasattr(trade, 'side') else trade.get('side', ''),
            "outcome": trade.outcome if hasattr(trade, 'outcome') else trade.get('outcome', ''),
            "size": trade.size if hasattr(trade, 'size') else trade.get('size', 0),
            "price": trade.price if hasattr(trade, 'price') else trade.get('price', 0),
            "pnl": trade.pnl if hasattr(trade, 'pnl') else trade.get('pnl'),
            "strategy": trade.strategy if hasattr(trade, 'strategy') else trade.get('strategy', ''),
            "timestamp": (trade.timestamp.isoformat() if hasattr(trade, 'timestamp') and trade.timestamp
                         else trade.get('timestamp', ''))
        }

    def _format_alert(self, alert) -> dict:
        return {
            "id": str(alert.id if hasattr(alert, 'id') else alert.get('id', '')),
            "type": alert.alert_type if hasattr(alert, 'alert_type') else alert.get('type', ''),
            "title": alert.title if hasattr(alert, 'title') else alert.get('title', ''),
            "message": alert.message if hasattr(alert, 'message') else alert.get('message', ''),
            "severity": alert.severity if hasattr(alert, 'severity') else alert.get('severity', 'info'),
            "timestamp": (alert.timestamp.isoformat() if hasattr(alert, 'timestamp') and alert.timestamp
                         else alert.get('timestamp', ''))
        }

    def _format_position(self, position) -> dict:
        return {
            "tokenId": position.token_id if hasattr(position, 'token_id') else position.get('token_id', ''),
            "marketId": position.market_id if hasattr(position, 'market_id') else position.get('market_id', ''),
            "outcome": position.outcome if hasattr(position, 'outcome') else position.get('outcome', ''),
            "size": position.size if hasattr(position, 'size') else position.get('size', 0),
            "entryPrice": position.entry_price if hasattr(position, 'entry_price') else position.get('entry_price', 0),
            "currentPrice": position.current_price if hasattr(position, 'current_price') else position.get('current_price', 0),
            "unrealizedPnl": position.unrealized_pnl if hasattr(position, 'unrealized_pnl') else position.get('unrealized_pnl', 0)
        }

    def _camel_to_snake(self, name: str) -> str:
        import re
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    async def start(self):
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        log.info("api_server_started", host=self.host, port=self.port)
