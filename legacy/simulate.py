#!/usr/bin/env python3
import asyncio
import json
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from pathlib import Path
import structlog

from config import config
from client import PolymarketClient
from scanner import ArbitrageScanner

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.dev.ConsoleRenderer()
    ]
)

log = structlog.get_logger()

@dataclass
class SimulatedTrade:
    timestamp: str
    question: str
    yes_price: float
    no_price: float
    total_cost: float
    profit_margin: float
    position_size: float
    theoretical_profit: float
    
@dataclass  
class SimulationResult:
    start_time: str
    end_time: str
    duration_minutes: int
    total_opportunities: int
    executable_opportunities: int
    total_theoretical_profit: float
    total_capital_needed: float
    avg_profit_per_trade: float
    avg_margin: float
    best_opportunity: dict = None
    worst_opportunity: dict = None
    trades: list = field(default_factory=list)

class Simulator:
    def __init__(self, duration_minutes: int = 120, position_size: float = 20.0):
        self.duration = timedelta(minutes=duration_minutes)
        self.position_size = position_size
        self.trades: list[SimulatedTrade] = []
        self.start_time = None
        self.opportunities_seen = 0
        
    async def run(self):
        self.start_time = datetime.utcnow()
        end_time = self.start_time + self.duration
        
        log.info(
            "simulation_started",
            duration=f"{self.duration.seconds // 60} minutes",
            position_size=f"${self.position_size}",
            end_time=end_time.isoformat()
        )
        
        async with PolymarketClient() as client:
            scanner = ArbitrageScanner(client)
            scan_count = 0
            
            while datetime.utcnow() < end_time:
                scan_count += 1
                elapsed = datetime.utcnow() - self.start_time
                remaining = end_time - datetime.utcnow()
                
                log.info(
                    "scan_cycle",
                    scan=scan_count,
                    elapsed=f"{elapsed.seconds // 60}m",
                    remaining=f"{remaining.seconds // 60}m",
                    opportunities=len(self.trades)
                )
                
                async for opp in scanner.scan_all_markets():
                    self.opportunities_seen += 1
                    
                    if not opp.is_executable:
                        continue
                    
                    trade = SimulatedTrade(
                        timestamp=datetime.utcnow().isoformat(),
                        question=opp.market.question[:80],
                        yes_price=opp.yes_book.best_ask,
                        no_price=opp.no_book.best_ask,
                        total_cost=opp.yes_book.best_ask + opp.no_book.best_ask,
                        profit_margin=opp.profit_margin,
                        position_size=min(self.position_size, opp.required_capital),
                        theoretical_profit=min(self.position_size, opp.required_capital) * opp.profit_margin
                    )
                    
                    self.trades.append(trade)
                    
                    log.info(
                        "opportunity_logged",
                        question=trade.question[:50],
                        margin=f"{trade.profit_margin:.2%}",
                        profit=f"${trade.theoretical_profit:.2f}"
                    )
                
                if datetime.utcnow() >= end_time:
                    break
                    
                await asyncio.sleep(60)
        
        return self._generate_report()
    
    def _generate_report(self) -> SimulationResult:
        end_time = datetime.utcnow()
        
        if not self.trades:
            return SimulationResult(
                start_time=self.start_time.isoformat(),
                end_time=end_time.isoformat(),
                duration_minutes=int((end_time - self.start_time).seconds / 60),
                total_opportunities=self.opportunities_seen,
                executable_opportunities=0,
                total_theoretical_profit=0,
                total_capital_needed=0,
                avg_profit_per_trade=0,
                avg_margin=0,
                trades=[]
            )
        
        total_profit = sum(t.theoretical_profit for t in self.trades)
        total_capital = sum(t.position_size for t in self.trades)
        avg_profit = total_profit / len(self.trades)
        avg_margin = sum(t.profit_margin for t in self.trades) / len(self.trades)
        
        sorted_trades = sorted(self.trades, key=lambda t: t.theoretical_profit, reverse=True)
        
        return SimulationResult(
            start_time=self.start_time.isoformat(),
            end_time=end_time.isoformat(),
            duration_minutes=int((end_time - self.start_time).seconds / 60),
            total_opportunities=self.opportunities_seen,
            executable_opportunities=len(self.trades),
            total_theoretical_profit=total_profit,
            total_capital_needed=total_capital,
            avg_profit_per_trade=avg_profit,
            avg_margin=avg_margin,
            best_opportunity=asdict(sorted_trades[0]) if sorted_trades else None,
            worst_opportunity=asdict(sorted_trades[-1]) if sorted_trades else None,
            trades=[asdict(t) for t in self.trades]
        )

async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=120, help="Duration in minutes")
    parser.add_argument("--position", type=float, default=20.0, help="Position size in USD")
    parser.add_argument("--output", default="simulation_result.json", help="Output file")
    args = parser.parse_args()
    
    sim = Simulator(duration_minutes=args.duration, position_size=args.position)
    result = await sim.run()
    
    output_path = Path(args.output)
    output_path.write_text(json.dumps(asdict(result), indent=2))
    
    print("\n" + "=" * 60)
    print("SIMULATION COMPLETE")
    print("=" * 60)
    print(f"Duration: {result.duration_minutes} minutes")
    print(f"Total opportunities scanned: {result.total_opportunities}")
    print(f"Executable opportunities: {result.executable_opportunities}")
    print(f"Total theoretical profit: ${result.total_theoretical_profit:.2f}")
    print(f"Total capital needed: ${result.total_capital_needed:.2f}")
    print(f"Average profit per trade: ${result.avg_profit_per_trade:.2f}")
    print(f"Average margin: {result.avg_margin:.2%}")
    print("=" * 60)
    
    if result.best_opportunity:
        print(f"\nBest opportunity:")
        print(f"  {result.best_opportunity['question']}")
        print(f"  Margin: {result.best_opportunity['profit_margin']:.2%}")
        print(f"  Profit: ${result.best_opportunity['theoretical_profit']:.2f}")
    
    print(f"\nFull results saved to: {args.output}")
    
    if result.total_theoretical_profit > 0:
        print(f"\n✅ PREDICTION: PROFITABLE")
        print(f"   Expected daily profit: ${result.total_theoretical_profit * (1440 / result.duration_minutes):.2f}")
    else:
        print(f"\n⚠️ PREDICTION: NO OPPORTUNITIES FOUND")
        print("   Market may be efficient or scan interval too long")

if __name__ == "__main__":
    asyncio.run(main())
