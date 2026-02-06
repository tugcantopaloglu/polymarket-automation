from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import mean, stdev
from typing import Protocol

from ..data.database import db
from ..utils.logging import get_logger

log = get_logger(__name__)

@dataclass
class BacktestTrade:
    timestamp: datetime
    market_id: str
    market_name: str
    side: str
    outcome: str
    size: float
    entry_price: float
    exit_price: float | None = None
    exit_timestamp: datetime | None = None
    pnl: float = 0.0
    strategy: str = ""

@dataclass
class BacktestResult:
    strategy: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    avg_trade_pnl: float
    avg_winner: float
    avg_loser: float
    largest_winner: float
    largest_loser: float
    avg_holding_period: float
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)

class StrategyProtocol(Protocol):
    def should_enter(self, market_data: dict, portfolio: dict) -> tuple[bool, str, float]: ...
    def should_exit(self, position: dict, market_data: dict) -> bool: ...

class BacktestEngine:
    def __init__(self, initial_capital: float = 1000.0):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.positions: dict[str, BacktestTrade] = {}
        self.closed_trades: list[BacktestTrade] = []
        self.equity_curve: list[dict] = []

    async def run(
        self,
        strategy: str,
        start_date: str | None = None,
        end_date: str | None = None,
        markets: list[str] | None = None
    ) -> dict:
        self.capital = self.initial_capital
        self.positions = {}
        self.closed_trades = []
        self.equity_curve = []

        end = datetime.fromisoformat(end_date) if end_date else datetime.now(UTC)
        start = datetime.fromisoformat(start_date) if start_date else end - timedelta(days=30)

        strategy_impl = self._get_strategy(strategy)

        historical_data = await self._load_historical_data(start, end, markets)

        current_date = start
        while current_date <= end:
            day_data = [d for d in historical_data if d.get("date", "").startswith(current_date.strftime("%Y-%m-%d"))]

            for market_data in day_data:
                self._update_positions(market_data)

                for pos_id, position in list(self.positions.items()):
                    if strategy_impl.should_exit(position.__dict__, market_data):
                        self._close_position(pos_id, market_data)

                portfolio_state = {
                    "capital": self.capital,
                    "positions": len(self.positions),
                    "exposure": self._calculate_exposure()
                }

                should_enter, side, size = strategy_impl.should_enter(market_data, portfolio_state)
                if should_enter and self._can_open_position(size):
                    self._open_position(market_data, side, size, strategy)

            self.equity_curve.append({
                "date": current_date.isoformat(),
                "value": self._calculate_portfolio_value(),
                "pnl": self._calculate_portfolio_value() - self.initial_capital
            })

            current_date += timedelta(days=1)

        for pos_id in list(self.positions.keys()):
            self._close_position(pos_id, historical_data[-1] if historical_data else {})

        return self._generate_result(strategy, start.isoformat(), end.isoformat())

    def _get_strategy(self, strategy_name: str) -> StrategyProtocol:
        strategies = {
            "arbitrage": ArbitrageBacktestStrategy(),
            "bonding": BondingBacktestStrategy(),
            "momentum": MomentumBacktestStrategy(),
            "value": ValueBacktestStrategy(),
        }
        return strategies.get(strategy_name, ArbitrageBacktestStrategy())

    async def _load_historical_data(
        self,
        start: datetime,
        end: datetime,
        markets: list[str] | None
    ) -> list[dict]:
        snapshots = db.get_market_snapshots(
            start_date=start.isoformat(),
            end_date=end.isoformat()
        )
        return [
            {
                "date": s.timestamp.isoformat() if hasattr(s, 'timestamp') else s.get('timestamp', ''),
                "market_id": s.condition_id if hasattr(s, 'condition_id') else s.get('condition_id', ''),
                "market_name": s.question if hasattr(s, 'question') else s.get('question', ''),
                "yes_price": s.yes_price if hasattr(s, 'yes_price') else s.get('yes_price', 0.5),
                "no_price": s.no_price if hasattr(s, 'no_price') else s.get('no_price', 0.5),
                "volume": s.volume if hasattr(s, 'volume') else s.get('volume', 0),
                "liquidity": s.liquidity if hasattr(s, 'liquidity') else s.get('liquidity', 0)
            }
            for s in snapshots
            if not markets or (s.condition_id if hasattr(s, 'condition_id') else s.get('condition_id', '')) in markets
        ]

    def _open_position(self, market_data: dict, side: str, size: float, strategy: str):
        price = market_data.get("yes_price" if side == "YES" else "no_price", 0.5)
        cost = size * price

        if cost > self.capital:
            size = self.capital / price
            cost = size * price

        trade = BacktestTrade(
            timestamp=datetime.fromisoformat(market_data.get("date", datetime.now(UTC).isoformat())),
            market_id=market_data.get("market_id", ""),
            market_name=market_data.get("market_name", ""),
            side="BUY",
            outcome=side,
            size=size,
            entry_price=price,
            strategy=strategy
        )

        self.positions[f"{market_data.get('market_id')}_{side}"] = trade
        self.capital -= cost

    def _close_position(self, position_id: str, market_data: dict):
        if position_id not in self.positions:
            return

        position = self.positions.pop(position_id)
        exit_price = market_data.get(f"{position.outcome.lower()}_price", position.entry_price)

        position.exit_price = exit_price
        position.exit_timestamp = datetime.fromisoformat(market_data.get("date", datetime.now(UTC).isoformat()))
        position.pnl = position.size * (exit_price - position.entry_price)

        self.capital += position.size * exit_price
        self.closed_trades.append(position)

    def _update_positions(self, market_data: dict):
        for _pos_id, position in self.positions.items():
            if market_data.get("market_id") == position.market_id:
                pass

    def _can_open_position(self, size: float) -> bool:
        return self.capital >= size * 0.1 and self._calculate_exposure() < 0.8

    def _calculate_exposure(self) -> float:
        position_value = sum(p.size * p.entry_price for p in self.positions.values())
        total_value = self.capital + position_value
        return position_value / total_value if total_value > 0 else 0

    def _calculate_portfolio_value(self) -> float:
        position_value = sum(p.size * p.entry_price for p in self.positions.values())
        return self.capital + position_value

    def _generate_result(self, strategy: str, start_date: str, end_date: str) -> dict:
        final_capital = self._calculate_portfolio_value()
        total_return = (final_capital - self.initial_capital) / self.initial_capital

        winners = [t for t in self.closed_trades if t.pnl > 0]
        losers = [t for t in self.closed_trades if t.pnl < 0]

        win_rate = len(winners) / len(self.closed_trades) if self.closed_trades else 0

        gross_profit = sum(t.pnl for t in winners)
        gross_loss = abs(sum(t.pnl for t in losers))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

        returns = [e.get("pnl", 0) / self.initial_capital for e in self.equity_curve if e.get("pnl")]
        sharpe_ratio = self._calculate_sharpe(returns)
        sortino_ratio = self._calculate_sortino(returns)
        max_drawdown = self._calculate_max_drawdown()

        holding_periods = [
            (t.exit_timestamp - t.timestamp).total_seconds() / 3600
            for t in self.closed_trades
            if t.exit_timestamp
        ]

        result = BacktestResult(
            strategy=strategy,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=final_capital,
            total_return=total_return,
            total_trades=len(self.closed_trades),
            winning_trades=len(winners),
            losing_trades=len(losers),
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            sortino_ratio=sortino_ratio,
            avg_trade_pnl=mean([t.pnl for t in self.closed_trades]) if self.closed_trades else 0,
            avg_winner=mean([t.pnl for t in winners]) if winners else 0,
            avg_loser=mean([t.pnl for t in losers]) if losers else 0,
            largest_winner=max([t.pnl for t in winners]) if winners else 0,
            largest_loser=min([t.pnl for t in losers]) if losers else 0,
            avg_holding_period=mean(holding_periods) if holding_periods else 0,
            trades=[{
                "timestamp": t.timestamp.isoformat(),
                "market": t.market_name,
                "side": t.side,
                "outcome": t.outcome,
                "size": t.size,
                "entryPrice": t.entry_price,
                "exitPrice": t.exit_price,
                "pnl": t.pnl
            } for t in self.closed_trades[-50:]],
            equity_curve=self.equity_curve
        )

        return result.__dict__

    def _calculate_sharpe(self, returns: list[float], risk_free: float = 0.0) -> float:
        if not returns or len(returns) < 2:
            return 0.0
        excess_returns = [r - risk_free / 252 for r in returns]
        avg_return = mean(excess_returns)
        std_return = stdev(excess_returns)
        return (avg_return / std_return) * (252 ** 0.5) if std_return > 0 else 0

    def _calculate_sortino(self, returns: list[float], risk_free: float = 0.0) -> float:
        if not returns or len(returns) < 2:
            return 0.0
        excess_returns = [r - risk_free / 252 for r in returns]
        downside_returns = [r for r in excess_returns if r < 0]
        if not downside_returns:
            return float('inf')
        avg_return = mean(excess_returns)
        downside_std = stdev(downside_returns) if len(downside_returns) > 1 else 0.001
        return (avg_return / downside_std) * (252 ** 0.5)

    def _calculate_max_drawdown(self) -> float:
        if not self.equity_curve:
            return 0.0

        peak = self.initial_capital
        max_dd = 0.0

        for point in self.equity_curve:
            value = point.get("value", self.initial_capital)
            peak = max(peak, value)
            dd = (peak - value) / peak
            max_dd = max(max_dd, dd)

        return max_dd


class ArbitrageBacktestStrategy:
    def should_enter(self, market_data: dict, portfolio: dict) -> tuple[bool, str, float]:
        yes_price = market_data.get("yes_price", 0.5)
        no_price = market_data.get("no_price", 0.5)
        spread = 1.0 - (yes_price + no_price)

        if spread > 0.02 and portfolio.get("exposure", 0) < 0.5:
            return True, "YES" if yes_price < no_price else "NO", 20.0
        return False, "", 0

    def should_exit(self, position: dict, market_data: dict) -> bool:
        yes_price = market_data.get("yes_price", 0.5)
        no_price = market_data.get("no_price", 0.5)
        spread = 1.0 - (yes_price + no_price)
        return spread < 0.005


class BondingBacktestStrategy:
    def should_enter(self, market_data: dict, portfolio: dict) -> tuple[bool, str, float]:
        yes_price = market_data.get("yes_price", 0.5)
        no_price = market_data.get("no_price", 0.5)

        if yes_price > 0.92 and portfolio.get("exposure", 0) < 0.5:
            return True, "YES", 25.0
        if no_price > 0.92 and portfolio.get("exposure", 0) < 0.5:
            return True, "NO", 25.0
        return False, "", 0

    def should_exit(self, position: dict, market_data: dict) -> bool:
        entry = position.get("entry_price", 0.5)
        outcome = position.get("outcome", "YES")
        current = market_data.get(f"{outcome.lower()}_price", entry)

        pnl_pct = (current - entry) / entry
        return pnl_pct > 0.05 or pnl_pct < -0.15


class MomentumBacktestStrategy:
    def should_enter(self, market_data: dict, portfolio: dict) -> tuple[bool, str, float]:
        return False, "", 0

    def should_exit(self, position: dict, market_data: dict) -> bool:
        return True


class ValueBacktestStrategy:
    def should_enter(self, market_data: dict, portfolio: dict) -> tuple[bool, str, float]:
        yes_price = market_data.get("yes_price", 0.5)

        if 0.3 < yes_price < 0.7 and portfolio.get("exposure", 0) < 0.3:
            expected_value = (0.5 - yes_price) * 0.3
            if expected_value > 0.02:
                return True, "YES" if yes_price < 0.5 else "NO", 15.0
        return False, "", 0

    def should_exit(self, position: dict, market_data: dict) -> bool:
        entry = position.get("entry_price", 0.5)
        outcome = position.get("outcome", "YES")
        current = market_data.get(f"{outcome.lower()}_price", entry)

        pnl_pct = (current - entry) / entry
        return pnl_pct > 0.15 or pnl_pct < -0.10
