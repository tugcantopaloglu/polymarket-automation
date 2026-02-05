#!/usr/bin/env python3
"""
Arbitrage Bot V2 - Optimized for speed
- Lower margin threshold (2%)
- Parallel market scanning
- WebSocket price updates where possible
- Sub-second opportunity detection
"""
import asyncio
import aiohttp
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import structlog

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer()
    ]
)
log = structlog.get_logger()

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

@dataclass
class ArbitrageOpp:
    timestamp: str
    market_id: str
    question: str
    yes_price: float
    no_price: float
    spread: float
    margin: float
    liquidity: float
    theoretical_profit: float
    execution_time_ms: float

@dataclass
class SimulationState:
    start_time: str = ""
    capital: float = 100.0
    current_balance: float = 100.0
    total_trades: int = 0
    winning_trades: int = 0
    total_profit: float = 0.0
    opportunities: list = field(default_factory=list)
    avg_execution_ms: float = 0.0

class FastArbitrageScanner:
    def __init__(self, min_margin: float = 0.02, max_position: float = 20.0):
        self.min_margin = min_margin
        self.max_position = max_position
        self.session: Optional[aiohttp.ClientSession] = None
        self.markets_cache = {}
        self.last_cache_update = None
        
    async def __aenter__(self):
        timeout = aiohttp.ClientTimeout(total=10)
        self.session = aiohttp.ClientSession(timeout=timeout)
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def fetch_all_markets(self) -> list:
        try:
            async with self.session.get(f"{GAMMA_API}/markets?closed=false&limit=500") as resp:
                if resp.status == 200:
                    return await resp.json()
        except Exception as e:
            log.error("fetch_markets_error", error=str(e))
        return []
    
    async def fetch_orderbook(self, token_id: str) -> Optional[dict]:
        try:
            async with self.session.get(f"{CLOB_API}/book?token_id={token_id}") as resp:
                if resp.status == 200:
                    return await resp.json()
        except:
            pass
        return None
    
    async def check_single_market(self, market: dict) -> Optional[ArbitrageOpp]:
        start = datetime.now(timezone.utc)
        
        tokens = market.get("tokens", [])
        if len(tokens) != 2:
            return None
        
        yes_token = next((t for t in tokens if t.get("outcome") == "Yes"), None)
        no_token = next((t for t in tokens if t.get("outcome") == "No"), None)
        
        if not yes_token or not no_token:
            return None
        
        yes_id = yes_token.get("token_id")
        no_id = no_token.get("token_id")
        
        if not yes_id or not no_id:
            return None
        
        yes_book, no_book = await asyncio.gather(
            self.fetch_orderbook(yes_id),
            self.fetch_orderbook(no_id)
        )
        
        if not yes_book or not no_book:
            return None
        
        yes_asks = yes_book.get("asks", [])
        no_asks = no_book.get("asks", [])
        
        if not yes_asks or not no_asks:
            return None
        
        yes_best = float(yes_asks[0].get("price", 1))
        no_best = float(no_asks[0].get("price", 1))
        yes_size = float(yes_asks[0].get("size", 0))
        no_size = float(no_asks[0].get("size", 0))
        
        total_cost = yes_best + no_best
        margin = 1.0 - total_cost
        
        exec_time = (datetime.now(timezone.utc) - start).total_seconds() * 1000
        
        if margin < self.min_margin:
            return None
        
        min_liq = min(yes_size * yes_best, no_size * no_best)
        if min_liq < 10:
            return None
        
        position = min(self.max_position, min_liq * 0.5)
        profit = position * margin
        
        return ArbitrageOpp(
            timestamp=datetime.now(timezone.utc).isoformat(),
            market_id=market.get("condition_id", ""),
            question=market.get("question", "")[:100],
            yes_price=yes_best,
            no_price=no_best,
            spread=total_cost,
            margin=margin,
            liquidity=min_liq,
            theoretical_profit=profit,
            execution_time_ms=exec_time
        )
    
    async def scan_all(self) -> list[ArbitrageOpp]:
        markets = await self.fetch_all_markets()
        log.info("scanning", market_count=len(markets))
        
        tasks = [self.check_single_market(m) for m in markets]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        opportunities = [r for r in results if isinstance(r, ArbitrageOpp)]
        return opportunities

class ArbitrageSimulatorV2:
    def __init__(self, capital: float = 100.0, min_margin: float = 0.02):
        self.state = SimulationState(capital=capital, current_balance=capital)
        self.min_margin = min_margin
        self.scanner: Optional[FastArbitrageScanner] = None
        
    async def run_until(self, end_time: datetime, output_file: str):
        self.state.start_time = datetime.now(timezone.utc).isoformat()
        
        log.info("simulation_v2_started",
                 capital=f"${self.state.capital}",
                 min_margin=f"{self.min_margin:.1%}",
                 end_time=end_time.isoformat())
        
        async with FastArbitrageScanner(min_margin=self.min_margin) as scanner:
            self.scanner = scanner
            scan_count = 0
            total_exec_time = 0
            
            while datetime.now(timezone.utc) < end_time:
                scan_count += 1
                scan_start = datetime.now(timezone.utc)
                
                opportunities = await scanner.scan_all()
                
                for opp in opportunities:
                    if self.state.current_balance >= opp.theoretical_profit / opp.margin:
                        self.state.opportunities.append(asdict(opp))
                        self.state.total_trades += 1
                        self.state.winning_trades += 1
                        self.state.total_profit += opp.theoretical_profit
                        self.state.current_balance += opp.theoretical_profit
                        total_exec_time += opp.execution_time_ms
                        
                        log.info("opportunity_found",
                                 question=opp.question[:50],
                                 margin=f"{opp.margin:.2%}",
                                 profit=f"${opp.theoretical_profit:.2f}",
                                 exec_ms=f"{opp.execution_time_ms:.0f}ms")
                
                if self.state.total_trades > 0:
                    self.state.avg_execution_ms = total_exec_time / self.state.total_trades
                
                remaining = (end_time - datetime.now(timezone.utc)).total_seconds() / 60
                log.info("scan_complete",
                         scan=scan_count,
                         found=len(opportunities),
                         total_profit=f"${self.state.total_profit:.2f}",
                         remaining=f"{remaining:.0f}m")
                
                self._save_state(output_file)
                await asyncio.sleep(30)
        
        self._save_state(output_file)
        log.info("simulation_complete",
                 total_trades=self.state.total_trades,
                 total_profit=f"${self.state.total_profit:.2f}",
                 final_balance=f"${self.state.current_balance:.2f}")
        
        return self.state
    
    def _save_state(self, output_file: str):
        Path(output_file).write_text(json.dumps(asdict(self.state), indent=2))

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--until", required=True, help="End time ISO format")
    parser.add_argument("--capital", type=float, default=100.0)
    parser.add_argument("--margin", type=float, default=0.02, help="Min margin (0.02 = 2%)")
    parser.add_argument("--output", default="arbitrage_v2_results.json")
    args = parser.parse_args()
    
    end_time = datetime.fromisoformat(args.until.replace('Z', '+00:00'))
    
    sim = ArbitrageSimulatorV2(capital=args.capital, min_margin=args.margin)
    await sim.run_until(end_time, args.output)

if __name__ == "__main__":
    asyncio.run(main())
