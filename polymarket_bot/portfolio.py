import math
from dataclasses import dataclass
from datetime import UTC, datetime
from statistics import mean, stdev

from .analysis.market_analyzer import RiskMetrics
from .client import MarketInfo, PolymarketClient
from .config import config
from .data.database import db
from .notifications.alerts import alert_manager
from .utils.logging import get_logger, metrics

log = get_logger(__name__)

@dataclass
class PortfolioPosition:
    token_id: str
    market_id: str
    outcome: str
    size: float
    entry_price: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    weight: float
    stop_loss: float
    take_profit: float
    entry_time: datetime

@dataclass
class PortfolioStats:
    total_value: float
    cash_balance: float
    positions_value: float
    unrealized_pnl: float
    realized_pnl_today: float
    realized_pnl_total: float
    num_positions: int
    win_rate: float
    avg_position_size: float
    max_drawdown: float
    sharpe_ratio: float
    exposure: float

@dataclass
class RiskLimits:
    max_position_size: float
    max_portfolio_exposure: float
    max_single_market_exposure: float
    max_daily_loss: float
    remaining_daily_loss: float
    can_trade: bool
    blocked_reason: str = ""

class PortfolioManager:
    def __init__(self, client: PolymarketClient):
        self.client = client
        self._positions: dict[str, PortfolioPosition] = {}
        self._daily_pnl = 0.0
        self._daily_trades = 0
        self._last_reset = datetime.now(UTC).date()
        self._peak_value = 0.0
        self._drawdown_history: list[float] = []
        self._returns_history: list[float] = []

    def _maybe_reset_daily(self):
        today = datetime.now(UTC).date()
        if today != self._last_reset:
            log.info("daily_reset", previous_pnl=f"${self._daily_pnl:.2f}")
            self._daily_pnl = 0.0
            self._daily_trades = 0
            self._last_reset = today

    async def sync_positions(self, markets: dict[str, MarketInfo]):
        portfolio_data = db.get_portfolio()

        for pos_data in portfolio_data:
            token_id = pos_data["token_id"]
            market_id = pos_data["market_id"]

            market = markets.get(market_id)
            current_price = 0.5

            if market:
                if pos_data["outcome"] == "Yes":
                    current_price = market.yes_token.price
                else:
                    current_price = market.no_token.price

            entry_price = pos_data["avg_entry_price"]
            size = pos_data["size"]

            unrealized_pnl = size * (current_price - entry_price) / entry_price if entry_price > 0 else 0
            unrealized_pnl_pct = (current_price - entry_price) / entry_price if entry_price > 0 else 0

            total_value = await self._get_total_value()
            weight = (size * current_price) / total_value if total_value > 0 else 0

            self._positions[token_id] = PortfolioPosition(
                token_id=token_id,
                market_id=market_id,
                outcome=pos_data["outcome"],
                size=size,
                entry_price=entry_price,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
                unrealized_pnl_pct=unrealized_pnl_pct,
                weight=weight,
                stop_loss=entry_price * (1 - config.trading.stop_loss_pct),
                take_profit=entry_price * (1 + config.trading.take_profit_pct),
                entry_time=datetime.fromisoformat(pos_data["updated_at"])
            )

    async def _get_total_value(self) -> float:
        cash = self.client.get_balance()
        positions_value = sum(p.size * p.current_price for p in self._positions.values())
        return cash + positions_value

    async def get_stats(self) -> PortfolioStats:
        self._maybe_reset_daily()

        cash = self.client.get_balance()
        positions_value = sum(p.size * p.current_price for p in self._positions.values())
        total_value = cash + positions_value
        unrealized_pnl = sum(p.unrealized_pnl for p in self._positions.values())

        self._returns_history.append(total_value)
        if len(self._returns_history) > 1000:
            self._returns_history = self._returns_history[-1000:]

        if total_value > self._peak_value:
            self._peak_value = total_value

        drawdown = (self._peak_value - total_value) / self._peak_value if self._peak_value > 0 else 0

        trades = db.get_trades(hours=720)
        wins = sum(1 for t in trades if t.profit > 0)
        win_rate = wins / len(trades) if trades else 0
        realized_total = sum(t.profit for t in trades)

        today_trades = db.get_trades(hours=24)
        realized_today = sum(t.profit for t in today_trades)

        returns = []
        for i in range(1, len(self._returns_history)):
            ret = (self._returns_history[i] - self._returns_history[i-1]) / self._returns_history[i-1]
            returns.append(ret)

        sharpe = 0.0
        if len(returns) > 1:
            avg_return = mean(returns)
            std_return = stdev(returns)
            if std_return > 0:
                sharpe = (avg_return * 252) / (std_return * math.sqrt(252))

        exposure = positions_value / total_value if total_value > 0 else 0
        avg_size = mean([p.size for p in self._positions.values()]) if self._positions else 0

        metrics.gauge("portfolio_value", total_value)
        metrics.gauge("portfolio_exposure", exposure)
        metrics.gauge("portfolio_drawdown", drawdown)

        return PortfolioStats(
            total_value=total_value,
            cash_balance=cash,
            positions_value=positions_value,
            unrealized_pnl=unrealized_pnl,
            realized_pnl_today=realized_today,
            realized_pnl_total=realized_total,
            num_positions=len(self._positions),
            win_rate=win_rate,
            avg_position_size=avg_size,
            max_drawdown=drawdown,
            sharpe_ratio=sharpe,
            exposure=exposure
        )

    def get_risk_limits(self) -> RiskLimits:
        self._maybe_reset_daily()

        total_value = self.client.get_balance() + sum(p.size * p.current_price for p in self._positions.values())

        exposure = sum(p.size * p.current_price for p in self._positions.values()) / total_value if total_value > 0 else 0

        max_position = min(
            config.trading.max_position_usd,
            total_value * 0.2
        )

        remaining_exposure = max(0, config.trading.max_portfolio_exposure - exposure)
        remaining_loss = config.trading.max_daily_loss_usd + self._daily_pnl

        can_trade = True
        blocked_reason = ""

        if remaining_loss <= 0:
            can_trade = False
            blocked_reason = f"Daily loss limit reached: ${-self._daily_pnl:.2f}"
        elif remaining_exposure <= 0.05:
            can_trade = False
            blocked_reason = f"Portfolio exposure limit reached: {exposure:.1%}"
        elif total_value < 5:
            can_trade = False
            blocked_reason = f"Insufficient balance: ${total_value:.2f}"

        return RiskLimits(
            max_position_size=max_position,
            max_portfolio_exposure=config.trading.max_portfolio_exposure,
            max_single_market_exposure=0.2,
            max_daily_loss=config.trading.max_daily_loss_usd,
            remaining_daily_loss=remaining_loss,
            can_trade=can_trade,
            blocked_reason=blocked_reason
        )

    def calculate_position_size(
        self,
        risk_metrics: RiskMetrics,
        available_capital: float
    ) -> float:
        kelly = risk_metrics.kelly_fraction * config.trading.kelly_fraction

        kelly_size = available_capital * kelly

        max_from_limits = min(
            config.trading.max_position_usd,
            available_capital * 0.2
        )

        var_adjusted = max_from_limits * (1 - risk_metrics.var_95)

        position_size = min(kelly_size, max_from_limits, var_adjusted)

        return max(1.0, round(position_size, 2))

    async def open_position(
        self,
        market: MarketInfo,
        side: str,
        size: float,
        price: float,
        strategy: str
    ) -> bool:
        limits = self.get_risk_limits()
        if not limits.can_trade:
            log.warning("trade_blocked", reason=limits.blocked_reason)
            return False

        if size > limits.max_position_size:
            size = limits.max_position_size
            log.info("position_size_capped", new_size=f"${size:.2f}")

        token_id = market.yes_token.token_id if side.upper() == "YES" else market.no_token.token_id
        outcome = "Yes" if side.upper() == "YES" else "No"

        if token_id in self._positions:
            existing = self._positions[token_id]
            new_size = existing.size + size
            new_avg = (existing.size * existing.entry_price + size * price) / new_size

            db.update_portfolio(
                token_id=token_id,
                market_id=market.condition_id,
                outcome=outcome,
                size=new_size,
                avg_entry_price=new_avg
            )
        else:
            db.update_portfolio(
                token_id=token_id,
                market_id=market.condition_id,
                outcome=outcome,
                size=size,
                avg_entry_price=price
            )

        db.record_trade(
            market_id=market.condition_id,
            token_id=token_id,
            side="BUY",
            price=price,
            size=size,
            profit=0,
            strategy=strategy,
            metadata={"action": "open"}
        )

        self._daily_trades += 1
        metrics.increment("positions_opened", tags={"strategy": strategy})

        log.info(
            "position_opened",
            market=market.question[:40],
            side=side,
            size=f"${size:.2f}",
            price=f"${price:.3f}",
            strategy=strategy
        )

        return True

    async def close_position(
        self,
        token_id: str,
        current_price: float,
        reason: str = "manual"
    ) -> float | None:
        if token_id not in self._positions:
            return None

        position = self._positions[token_id]
        profit = position.size * (current_price - position.entry_price) / position.entry_price

        db.update_portfolio(
            token_id=token_id,
            market_id=position.market_id,
            outcome=position.outcome,
            size=0,
            avg_entry_price=0
        )

        db.record_trade(
            market_id=position.market_id,
            token_id=token_id,
            side="SELL",
            price=current_price,
            size=position.size,
            profit=profit,
            strategy=reason,
            metadata={"action": "close", "reason": reason}
        )

        self._daily_pnl += profit
        db.update_strategy_performance(reason, profit, profit > 0)

        del self._positions[token_id]
        metrics.increment("positions_closed", tags={"reason": reason})

        log.info(
            "position_closed",
            token_id=token_id[:16],
            profit=f"${profit:+.2f}",
            reason=reason
        )

        return profit

    async def check_stop_loss_take_profit(self) -> list[str]:
        closed = []

        for token_id, position in list(self._positions.items()):
            if position.current_price <= position.stop_loss:
                profit = await self.close_position(token_id, position.current_price, "stop_loss")
                closed.append(token_id)
                await alert_manager.alert_risk_warning(
                    "Stop Loss Triggered",
                    "Position closed at loss",
                    {"Token": token_id[:16], "Loss": f"${profit:.2f}"}
                )
            elif position.current_price >= position.take_profit:
                profit = await self.close_position(token_id, position.current_price, "take_profit")
                closed.append(token_id)

        return closed

    def get_position(self, token_id: str) -> PortfolioPosition | None:
        return self._positions.get(token_id)

    def get_all_positions(self) -> list[PortfolioPosition]:
        return list(self._positions.values())

    def get_market_exposure(self, market_id: str) -> float:
        return sum(
            p.size * p.current_price
            for p in self._positions.values()
            if p.market_id == market_id
        )
