#!/usr/bin/env python3
import asyncio
import signal
import sys
import structlog
from datetime import datetime

from config import config, keystore
from client import PolymarketClient
from scanner import ArbitrageScanner
from executor import TradeExecutor

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer()
    ]
)

log = structlog.get_logger()

class PolymarketBot:
    def __init__(self, private_key: str = None, funder: str = None):
        self.private_key = private_key
        self.funder = funder
        self.client: PolymarketClient = None
        self.scanner: ArbitrageScanner = None
        self.executor: TradeExecutor = None
        self._running = False
        
    async def start(self):
        log.info("bot_starting", config={
            "min_profit": f"{config.trading.min_profit_margin:.0%}",
            "max_position": f"${config.trading.max_position_usd}",
            "max_daily_loss": f"${config.trading.max_daily_loss_usd}"
        })
        
        if not self.private_key and not keystore.has_key():
            log.error("no_private_key", msg="Run setup first: python setup.py")
            return
            
        pk = self.private_key or keystore.load_private_key()
        
        async with PolymarketClient(pk, self.funder) as client:
            self.client = client
            self.scanner = ArbitrageScanner(client)
            self.executor = TradeExecutor(client)
            
            balance = client.get_balance()
            log.info("wallet_connected", balance=f"${balance:.2f}")
            
            if balance < 5:
                log.warning("low_balance", msg="Balance too low for trading")
                
            self._running = True
            await self._run_loop()
    
    async def _run_loop(self):
        scan_interval = 30
        stats_interval = 300
        last_stats = datetime.utcnow()
        
        while self._running:
            try:
                async for opp in self.scanner.scan_all_markets():
                    if not self._running:
                        break
                        
                    result = await self.executor.execute(opp)
                    
                    if result.success:
                        log.info("trade_completed", profit=f"${result.actual_profit:.2f}")
                    elif result.error and "EXPOSED" in result.error:
                        log.critical("exposed_position", error=result.error)
                        self.executor.pause()
                        
                    await asyncio.sleep(config.trading.cooldown_seconds)
                
                if (datetime.utcnow() - last_stats).seconds >= stats_interval:
                    stats = self.executor.get_stats()
                    log.info("periodic_stats", **stats)
                    last_stats = datetime.utcnow()
                    
                log.debug("scan_cycle_complete", next_in=f"{scan_interval}s")
                await asyncio.sleep(scan_interval)
                
            except Exception as e:
                log.error("main_loop_error", error=str(e))
                await asyncio.sleep(10)
    
    def stop(self):
        log.info("bot_stopping")
        self._running = False
        if self.scanner:
            self.scanner.stop()
        stats = self.executor.get_stats() if self.executor else {}
        log.info("final_stats", **stats)

async def monitor_mode():
    log.info("monitor_mode", msg="Scanning without trading (no wallet)")
    
    async with PolymarketClient() as client:
        scanner = ArbitrageScanner(client)
        
        while True:
            async for opp in scanner.scan_all_markets():
                log.info(
                    "opportunity",
                    question=opp.market.question[:60],
                    margin=f"{opp.profit_margin:.2%}",
                    profit=f"${opp.expected_profit:.2f}",
                    yes_price=f"${opp.yes_book.best_ask:.3f}",
                    no_price=f"${opp.no_book.best_ask:.3f}"
                )
            await asyncio.sleep(60)

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Polymarket Arbitrage Bot")
    parser.add_argument("--monitor", action="store_true", help="Monitor only, no trading")
    parser.add_argument("--key", help="Private key (will be stored encrypted)")
    parser.add_argument("--funder", help="Funder address")
    args = parser.parse_args()
    
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
        bot = PolymarketBot(funder=args.funder)
        asyncio.run(bot.start())

if __name__ == "__main__":
    main()
