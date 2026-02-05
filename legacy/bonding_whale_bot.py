#!/usr/bin/env python3
"""
Bonding + Whale Following Bot
Strategy 1: High-probability bonding (95%+ markets near resolution)
Strategy 2: Whale following (track profitable wallets)
"""
import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
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
POLYTRACK_API = "https://api.polytrack.io"

@dataclass
class BondingOpp:
    timestamp: str
    market_id: str
    question: str
    current_price: float
    days_to_resolution: float
    expected_return: float
    position_size: float
    expected_profit: float
    confidence: str

@dataclass
class WhaleTrade:
    timestamp: str
    whale_address: str
    whale_pnl: float
    whale_winrate: float
    market_question: str
    side: str
    price: float
    size: float
    our_position: float
    expected_profit: float

@dataclass
class SimulationState:
    start_time: str = ""
    capital: float = 100.0
    current_balance: float = 100.0
    bonding_trades: int = 0
    bonding_profit: float = 0.0
    whale_trades: int = 0
    whale_profit: float = 0.0
    whale_wins: int = 0
    whale_losses: int = 0
    total_profit: float = 0.0
    bonding_opportunities: list = field(default_factory=list)
    whale_opportunities: list = field(default_factory=list)
    tracked_whales: list = field(default_factory=list)

class BondingScanner:
    def __init__(self, min_probability: float = 0.92, max_days: int = 7):
        self.min_probability = min_probability
        self.max_days = max_days
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def scan(self, session: aiohttp.ClientSession) -> list[BondingOpp]:
        opportunities = []
        
        try:
            async with session.get(f"{GAMMA_API}/markets?closed=false&limit=300") as resp:
                if resp.status != 200:
                    return []
                markets = await resp.json()
        except Exception as e:
            log.error("bonding_scan_error", error=str(e))
            return []
        
        now = datetime.now(timezone.utc)
        
        for market in markets:
            try:
                end_date_str = market.get("end_date_iso") or market.get("endDate")
                if not end_date_str:
                    continue
                
                end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                days_to_resolution = (end_date - now).total_seconds() / 86400
                
                if days_to_resolution < 0 or days_to_resolution > self.max_days:
                    continue
                
                tokens = market.get("tokens", [])
                if len(tokens) != 2:
                    continue
                
                for token in tokens:
                    price = float(token.get("price", 0))
                    outcome = token.get("outcome", "")
                    
                    if price >= self.min_probability and price < 0.99:
                        return_pct = (1.0 - price) / price
                        annualized = return_pct * (365 / max(days_to_resolution, 0.5))
                        
                        position_size = min(20.0, 100 / (1 + annualized))
                        expected_profit = position_size * return_pct
                        
                        confidence = "HIGH" if price >= 0.95 else "MEDIUM"
                        
                        opp = BondingOpp(
                            timestamp=now.isoformat(),
                            market_id=market.get("condition_id", ""),
                            question=f"{market.get('question', '')[:80]} → {outcome}",
                            current_price=price,
                            days_to_resolution=days_to_resolution,
                            expected_return=return_pct,
                            position_size=position_size,
                            expected_profit=expected_profit,
                            confidence=confidence
                        )
                        opportunities.append(opp)
                        
            except Exception as e:
                continue
        
        opportunities.sort(key=lambda x: x.expected_return, reverse=True)
        return opportunities[:10]

class WhaleTracker:
    KNOWN_WHALES = [
        {"address": "0x1234...whale1", "name": "Whale1", "est_pnl": 150000, "est_winrate": 0.65},
        {"address": "0x5678...whale2", "name": "Whale2", "est_pnl": 89000, "est_winrate": 0.62},
        {"address": "0x9abc...whale3", "name": "Whale3", "est_pnl": 210000, "est_winrate": 0.68},
        {"address": "0xdef0...whale4", "name": "Whale4", "est_pnl": 75000, "est_winrate": 0.61},
        {"address": "0x1111...whale5", "name": "Whale5", "est_pnl": 320000, "est_winrate": 0.71},
    ]
    
    def __init__(self, min_whale_pnl: float = 50000, min_winrate: float = 0.60):
        self.min_whale_pnl = min_whale_pnl
        self.min_winrate = min_winrate
        self.last_trades = {}
    
    async def simulate_whale_activity(self, session: aiohttp.ClientSession) -> list[WhaleTrade]:
        trades = []
        now = datetime.now(timezone.utc)
        
        import random
        
        if random.random() < 0.15:
            try:
                async with session.get(f"{GAMMA_API}/markets?closed=false&limit=50&order=volume&ascending=false") as resp:
                    if resp.status != 200:
                        return []
                    markets = await resp.json()
            except:
                return []
            
            if not markets:
                return []
            
            whale = random.choice(self.KNOWN_WHALES)
            market = random.choice(markets[:20])
            
            tokens = market.get("tokens", [])
            if len(tokens) < 2:
                return []
            
            token = random.choice(tokens)
            price = float(token.get("price", 0.5))
            
            if 0.30 <= price <= 0.70:
                side = "BUY" if random.random() < 0.5 else "SELL"
                whale_size = random.uniform(500, 5000)
                
                our_position = min(15.0, whale_size * 0.01)
                
                win_prob = whale["est_winrate"]
                is_win = random.random() < win_prob
                
                if is_win:
                    if side == "BUY":
                        expected_profit = our_position * ((1.0 / price) - 1) * 0.3
                    else:
                        expected_profit = our_position * (price / (1 - price)) * 0.3
                else:
                    expected_profit = -our_position * 0.5
                
                trade = WhaleTrade(
                    timestamp=now.isoformat(),
                    whale_address=whale["address"],
                    whale_pnl=whale["est_pnl"],
                    whale_winrate=whale["est_winrate"],
                    market_question=market.get("question", "")[:80],
                    side=side,
                    price=price,
                    size=whale_size,
                    our_position=our_position,
                    expected_profit=expected_profit
                )
                trades.append(trade)
                
                log.info("whale_trade_detected",
                         whale=whale["name"],
                         side=side,
                         market=market.get("question", "")[:40],
                         our_copy=f"${our_position:.2f}",
                         result="WIN" if is_win else "LOSS")
        
        return trades

class BondingWhaleSimulator:
    def __init__(self, capital: float = 100.0):
        self.state = SimulationState(capital=capital, current_balance=capital)
        self.bonding_scanner = BondingScanner(min_probability=0.92)
        self.whale_tracker = WhaleTracker()
        self.session: Optional[aiohttp.ClientSession] = None
        self.bonding_positions = {}
        
    async def run_until(self, end_time: datetime, output_file: str):
        self.state.start_time = datetime.now(timezone.utc).isoformat()
        self.state.tracked_whales = WhaleTracker.KNOWN_WHALES
        
        log.info("bonding_whale_sim_started",
                 capital=f"${self.state.capital}",
                 end_time=end_time.isoformat())
        
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            self.session = session
            scan_count = 0
            
            while datetime.now(timezone.utc) < end_time:
                scan_count += 1
                
                bonding_opps = await self.bonding_scanner.scan(session)
                for opp in bonding_opps[:3]:
                    if opp.market_id not in self.bonding_positions:
                        if self.state.current_balance >= opp.position_size:
                            self.bonding_positions[opp.market_id] = opp
                            self.state.bonding_opportunities.append(asdict(opp))
                            self.state.bonding_trades += 1
                            self.state.bonding_profit += opp.expected_profit
                            self.state.total_profit += opp.expected_profit
                            self.state.current_balance += opp.expected_profit
                            
                            log.info("bonding_position",
                                     question=opp.question[:50],
                                     price=f"{opp.current_price:.2%}",
                                     days=f"{opp.days_to_resolution:.1f}",
                                     profit=f"${opp.expected_profit:.2f}")
                
                whale_trades = await self.whale_tracker.simulate_whale_activity(session)
                for trade in whale_trades:
                    if self.state.current_balance >= abs(trade.our_position):
                        self.state.whale_opportunities.append(asdict(trade))
                        self.state.whale_trades += 1
                        self.state.whale_profit += trade.expected_profit
                        self.state.total_profit += trade.expected_profit
                        self.state.current_balance += trade.expected_profit
                        
                        if trade.expected_profit > 0:
                            self.state.whale_wins += 1
                        else:
                            self.state.whale_losses += 1
                
                remaining = (end_time - datetime.now(timezone.utc)).total_seconds() / 60
                log.info("scan_cycle",
                         scan=scan_count,
                         bonding_trades=self.state.bonding_trades,
                         whale_trades=self.state.whale_trades,
                         total_profit=f"${self.state.total_profit:.2f}",
                         balance=f"${self.state.current_balance:.2f}",
                         remaining=f"{remaining:.0f}m")
                
                self._save_state(output_file)
                await asyncio.sleep(60)
        
        self._save_state(output_file)
        
        whale_winrate = (self.state.whale_wins / self.state.whale_trades * 100) if self.state.whale_trades > 0 else 0
        
        log.info("simulation_complete",
                 bonding_trades=self.state.bonding_trades,
                 bonding_profit=f"${self.state.bonding_profit:.2f}",
                 whale_trades=self.state.whale_trades,
                 whale_profit=f"${self.state.whale_profit:.2f}",
                 whale_winrate=f"{whale_winrate:.1f}%",
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
    parser.add_argument("--output", default="bonding_whale_results.json")
    args = parser.parse_args()
    
    end_time = datetime.fromisoformat(args.until.replace('Z', '+00:00'))
    
    sim = BondingWhaleSimulator(capital=args.capital)
    await sim.run_until(end_time, args.output)

if __name__ == "__main__":
    asyncio.run(main())
