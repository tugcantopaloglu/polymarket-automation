#!/usr/bin/env python3
import asyncio
import signal
import sys
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict

from .config import config, keystore
from .client import PolymarketClient, MarketInfo
from .portfolio import PortfolioManager
from .data.database import db
from .analysis.market_analyzer import market_analyzer
from .notifications.alerts import alert_manager, AlertType, Alert
from .strategies.base import Strategy, StrategyResult
from .strategies.arbitrage import ArbitrageStrategy
from .strategies.bonding import BondingStrategy
from .strategies.momentum import MomentumStrategy, MeanReversionStrategy
from .strategies.value import ValueStrategy
from .strategies.whale import WhaleFollowingStrategy
from .utils.logging import setup_logging, get_logger, metrics

log = get_logger(__name__)

class PolymarketBot:
    def __init__(
        self,
        private_key: str = None,
        funder: str = None,
        strategies: List[str] = None,
        dry_run: bool = False
    ):
        self.private_key = private_key
        self.funder = funder
        self.dry_run = dry_run
        self.enabled_strategies = strategies or ["arbitrage", "bonding"]
        
        self.client: Optional[PolymarketClient] = None
        self.portfolio: Optional[PortfolioManager] = None
        self.strategies: Dict[str, Strategy] = {}
        
        self._running = False
        self._markets_cache: Dict[str, MarketInfo] = {}
        self._last_full_scan = None
        self._scan_interval = 30
        self._stats_interval = 300
    
    async def start(self):
        setup_logging(config.log_level)
        
        log.info("bot_starting", config={
            "strategies": self.enabled_strategies,
            "dry_run": self.dry_run,
            "min_profit": f"{config.trading.min_profit_margin:.0%}",
            "max_position": f"${config.trading.max_position_usd}",
            "max_daily_loss": f"${config.trading.max_daily_loss_usd}"
        })
        
        if not self.dry_run:
            if not self.private_key and not keystore.has_key():
                log.error("no_private_key", msg="Run setup first or provide --key")
                return
            pk = self.private_key or keystore.load_private_key()
        else:
            pk = None
        
        async with PolymarketClient(pk, self.funder) as client:
            self.client = client
            self.portfolio = PortfolioManager(client)
            
            self._init_strategies()
            
            if not self.dry_run:
                balance = client.get_balance()
                log.info("wallet_connected", balance=f"${balance:.2f}")
                
                if balance < 5:
                    log.warning("low_balance", msg="Balance too low for trading")
            else:
                log.info("dry_run_mode", msg="No wallet connected, simulation only")
            
            await alert_manager.send_alert(Alert(
                alert_type=AlertType.POSITION_UPDATE,
                title="Bot Started",
                message="Polymarket trading bot is now running",
                severity="INFO",
                data={
                    "Strategies": ", ".join(self.enabled_strategies),
                    "Mode": "Dry Run" if self.dry_run else "Live"
                }
            ))
            
            self._running = True
            await self._run_loop()
    
    def _init_strategies(self):
        strategy_classes = {
            "arbitrage": ArbitrageStrategy,
            "bonding": BondingStrategy,
            "momentum": MomentumStrategy,
            "mean_reversion": MeanReversionStrategy,
            "value": ValueStrategy,
            "whale": WhaleFollowingStrategy
        }
        
        for name in self.enabled_strategies:
            if name in strategy_classes:
                self.strategies[name] = strategy_classes[name](
                    self.client,
                    self.portfolio
                )
                log.info("strategy_enabled", name=name)
    
    async def _run_loop(self):
        last_stats_time = datetime.now(timezone.utc)
        
        while self._running:
            try:
                await self._scan_cycle()
                
                await self.portfolio.check_stop_loss_take_profit()
                
                if (datetime.now(timezone.utc) - last_stats_time).total_seconds() >= self._stats_interval:
                    await self._report_stats()
                    last_stats_time = datetime.now(timezone.utc)
                
                await asyncio.sleep(self._scan_interval)
                
            except Exception as e:
                log.error("main_loop_error", error=str(e))
                metrics.increment("errors", tags={"type": "main_loop"})
                await asyncio.sleep(10)
    
    async def _scan_cycle(self):
        log.debug("scan_cycle_start")
        metrics.timer_start("scan_cycle")
        
        await self._refresh_markets()
        
        markets = list(self._markets_cache.values())
        
        for name, strategy in self.strategies.items():
            if not strategy.enabled:
                continue
            
            try:
                async for result in strategy.scan(markets):
                    await self._handle_opportunity(result)
            except Exception as e:
                log.error("strategy_scan_error", strategy=name, error=str(e))
                metrics.increment("errors", tags={"type": "strategy_scan", "strategy": name})
        
        elapsed = metrics.timer_stop("scan_cycle")
        log.debug("scan_cycle_complete", elapsed=f"{elapsed:.2f}s", markets=len(markets))
    
    async def _refresh_markets(self):
        should_full_refresh = (
            self._last_full_scan is None or
            (datetime.now(timezone.utc) - self._last_full_scan).total_seconds() > 300
        )
        
        if should_full_refresh:
            events = await self.client.get_events(active=True, limit=300)
            
            for event in events:
                for market_data in event.get("markets", []):
                    condition_id = market_data.get("conditionId") or market_data.get("condition_id")
                    if condition_id:
                        market = await self.client.get_market_info(condition_id)
                        if market:
                            self._markets_cache[condition_id] = market
                            
                            db.record_market_snapshot(
                                market.condition_id,
                                market.question,
                                market.yes_token.price,
                                market.no_token.price,
                                market.volume_24h,
                                market.liquidity
                            )
            
            self._last_full_scan = datetime.now(timezone.utc)
            log.info("markets_refreshed", count=len(self._markets_cache))
        else:
            for market in list(self._markets_cache.values())[:50]:
                updated = await self.client.get_market_info(market.condition_id)
                if updated:
                    old_price = market.yes_token.price
                    self._markets_cache[market.condition_id] = updated
                    
                    await alert_manager.check_price_movement(
                        updated,
                        old_price,
                        updated.yes_token.price
                    )
    
    async def _handle_opportunity(self, result: StrategyResult):
        log.info(
            "opportunity_found",
            strategy=result.strategy.value,
            market=result.market.question[:50],
            action=result.action,
            side=result.side,
            confidence=f"{result.confidence:.0%}",
            profit=f"${result.expected_profit:.2f}"
        )
        
        metrics.increment("opportunities", tags={"strategy": result.strategy.value})
        
        if result.strategy.value == "arbitrage":
            await alert_manager.alert_arbitrage_opportunity(
                result.market,
                result.metadata.get("net_margin", 0),
                result.expected_profit
            )
        
        if self.dry_run:
            log.info("dry_run_skip", msg="Would execute trade in live mode")
            return
        
        strategy = self.strategies.get(result.strategy.value)
        if strategy:
            success = await strategy.execute(result)
            
            if success:
                await alert_manager.alert_trade_executed(
                    result.market,
                    result.side,
                    result.size,
                    result.price,
                    result.expected_profit,
                    result.strategy.value
                )
    
    async def _report_stats(self):
        portfolio_stats = await self.portfolio.get_stats()
        
        strategy_stats = {name: s.get_stats() for name, s in self.strategies.items()}
        
        log.info(
            "periodic_stats",
            portfolio_value=f"${portfolio_stats.total_value:.2f}",
            positions=portfolio_stats.num_positions,
            unrealized_pnl=f"${portfolio_stats.unrealized_pnl:+.2f}",
            realized_today=f"${portfolio_stats.realized_pnl_today:+.2f}",
            win_rate=f"{portfolio_stats.win_rate:.0%}",
            exposure=f"{portfolio_stats.exposure:.0%}",
            drawdown=f"{portfolio_stats.max_drawdown:.1%}",
            sharpe=f"{portfolio_stats.sharpe_ratio:.2f}"
        )
        
        for name, stats in strategy_stats.items():
            log.info(
                "strategy_stats",
                strategy=name,
                opportunities=stats["opportunities_found"],
                trades=stats["trades_executed"]
            )
        
        db_stats = db.get_strategy_stats(days=7)
        for stat in db_stats:
            log.debug("db_strategy_stat", **stat)
    
    def stop(self):
        log.info("bot_stopping")
        self._running = False
        
        asyncio.create_task(alert_manager.send_alert(Alert(
            alert_type=AlertType.POSITION_UPDATE,
            title="Bot Stopped",
            message="Polymarket trading bot has been stopped",
            severity="WARNING"
        )))

async def monitor_mode():
    setup_logging(config.log_level)
    log.info("monitor_mode", msg="Scanning without trading (no wallet)")
    
    async with PolymarketClient() as client:
        portfolio = PortfolioManager(client)
        
        strategies = [
            ArbitrageStrategy(client, portfolio),
            BondingStrategy(client, portfolio),
        ]
        
        while True:
            events = await client.get_events(active=True, limit=200)
            markets = []
            
            for event in events:
                for market_data in event.get("markets", []):
                    condition_id = market_data.get("conditionId") or market_data.get("condition_id")
                    if condition_id:
                        market = await client.get_market_info(condition_id)
                        if market:
                            markets.append(market)
            
            for strategy in strategies:
                async for result in strategy.scan(markets):
                    log.info(
                        "monitor_opportunity",
                        strategy=result.strategy.value,
                        market=result.market.question[:60],
                        confidence=f"{result.confidence:.0%}",
                        profit=f"${result.expected_profit:.2f}",
                        **result.metadata
                    )
            
            await asyncio.sleep(60)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Polymarket Trading Bot")
    parser.add_argument("--monitor", action="store_true", help="Monitor only, no trading")
    parser.add_argument("--dry-run", action="store_true", help="Simulate trades without executing")
    parser.add_argument("--key", help="Private key (will be stored encrypted)")
    parser.add_argument("--funder", help="Funder address")
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=["arbitrage", "bonding"],
        choices=["arbitrage", "bonding", "momentum", "mean_reversion", "value", "whale"],
        help="Trading strategies to enable"
    )
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()
    
    config.log_level = args.log_level
    
    if args.key:
        keystore.store_private_key(args.key)
        log.info("private_key_stored", msg="Key encrypted and saved")
    
    bot = None
    
    def handle_signal(sig, frame):
        log.info("signal_received", signal=sig)
        if bot:
            bot.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    if args.monitor:
        asyncio.run(monitor_mode())
    else:
        bot = PolymarketBot(
            funder=args.funder,
            strategies=args.strategies,
            dry_run=args.dry_run
        )
        asyncio.run(bot.start())

if __name__ == "__main__":
    main()
