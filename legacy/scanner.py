import asyncio
import structlog
from dataclasses import dataclass
from typing import AsyncGenerator
from datetime import datetime

from config import config
from client import PolymarketClient, MarketInfo, OrderBook

log = structlog.get_logger()

@dataclass
class ArbitrageOpportunity:
    market: MarketInfo
    yes_book: OrderBook
    no_book: OrderBook
    profit_margin: float
    required_capital: float
    expected_profit: float
    timestamp: datetime
    
    @property
    def is_executable(self) -> bool:
        min_liq = config.trading.min_liquidity_usd
        return (
            self.yes_book.ask_liquidity >= min_liq and
            self.no_book.ask_liquidity >= min_liq and
            self.profit_margin >= config.trading.min_profit_margin and
            self.required_capital <= config.trading.max_position_usd
        )

class ArbitrageScanner:
    def __init__(self, client: PolymarketClient):
        self.client = client
        self._running = False
        self._scanned_markets: set[str] = set()
        
    async def scan_single_condition(self, market: MarketInfo) -> ArbitrageOpportunity | None:
        yes_book = self.client.get_order_book(market.yes_token.token_id)
        no_book = self.client.get_order_book(market.no_token.token_id)
        
        if not yes_book or not no_book:
            return None
            
        yes_ask = yes_book.best_ask
        no_ask = no_book.best_ask
        
        total_cost = yes_ask + no_ask
        profit_margin = 1.0 - total_cost
        
        if profit_margin < config.trading.min_profit_margin:
            return None
            
        max_position = config.trading.max_position_usd
        min_liq = min(yes_book.ask_liquidity, no_book.ask_liquidity)
        required_capital = min(max_position, min_liq * 0.5)
        expected_profit = required_capital * profit_margin
        
        return ArbitrageOpportunity(
            market=market,
            yes_book=yes_book,
            no_book=no_book,
            profit_margin=profit_margin,
            required_capital=required_capital,
            expected_profit=expected_profit,
            timestamp=datetime.utcnow()
        )
    
    async def scan_all_markets(self) -> AsyncGenerator[ArbitrageOpportunity, None]:
        log.info("scanning_markets")
        
        try:
            events = await self.client.get_markets(active=True, limit=200)
        except Exception as e:
            log.error("fetch_markets_error", error=str(e))
            return
            
        for event in events:
            markets = event.get("markets", [])
            for market_data in markets:
                condition_id = market_data.get("conditionId") or market_data.get("condition_id")
                if not condition_id:
                    continue
                    
                if condition_id in self._scanned_markets:
                    continue
                    
                market = await self.client.get_market_info(condition_id)
                if not market:
                    continue
                    
                if market.yes_token.price <= 0 or market.no_token.price <= 0:
                    continue
                    
                if market.yes_token.price >= 0.95 or market.no_token.price >= 0.95:
                    continue
                    
                opp = await self.scan_single_condition(market)
                if opp and opp.is_executable:
                    log.info(
                        "opportunity_found",
                        question=market.question[:50],
                        margin=f"{opp.profit_margin:.2%}",
                        capital=f"${opp.required_capital:.2f}",
                        profit=f"${opp.expected_profit:.2f}"
                    )
                    yield opp
                    
                await asyncio.sleep(0.1)
    
    async def continuous_scan(self, interval: int = 30) -> AsyncGenerator[ArbitrageOpportunity, None]:
        self._running = True
        while self._running:
            async for opp in self.scan_all_markets():
                yield opp
            
            self._scanned_markets.clear()
            log.info("scan_complete", next_scan_in=f"{interval}s")
            await asyncio.sleep(interval)
    
    def stop(self):
        self._running = False
