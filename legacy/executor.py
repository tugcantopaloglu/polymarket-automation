from dataclasses import dataclass, field
from datetime import datetime, timedelta

import structlog
from client import PolymarketClient
from config import config
from scanner import ArbitrageOpportunity

log = structlog.get_logger()

@dataclass
class TradeResult:
    success: bool
    opportunity: ArbitrageOpportunity
    yes_order: dict | None = None
    no_order: dict | None = None
    error: str | None = None
    actual_profit: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

@dataclass
class RiskState:
    daily_pnl: float = 0.0
    daily_trades: int = 0
    last_trade_time: datetime | None = None
    consecutive_losses: int = 0
    total_invested: float = 0.0

    def reset_daily(self):
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.consecutive_losses = 0

class TradeExecutor:
    def __init__(self, client: PolymarketClient):
        self.client = client
        self.risk = RiskState()
        self._trades: list[TradeResult] = []
        self._paused = False

    def can_trade(self, opp: ArbitrageOpportunity) -> tuple[bool, str]:
        if self._paused:
            return False, "Trading paused"

        if self.risk.daily_pnl <= -config.trading.max_daily_loss_usd:
            return False, f"Daily loss limit reached: ${self.risk.daily_pnl:.2f}"

        if self.risk.consecutive_losses >= 3:
            return False, f"Too many consecutive losses: {self.risk.consecutive_losses}"

        if self.risk.last_trade_time:
            cooldown = timedelta(seconds=config.trading.cooldown_seconds)
            if datetime.utcnow() - self.risk.last_trade_time < cooldown:
                return False, "Cooldown period active"

        balance = self.client.get_balance()
        if balance < opp.required_capital:
            return False, f"Insufficient balance: ${balance:.2f} < ${opp.required_capital:.2f}"

        return True, "OK"

    async def execute(self, opp: ArbitrageOpportunity) -> TradeResult:
        can_trade, reason = self.can_trade(opp)
        if not can_trade:
            log.warning("trade_blocked", reason=reason)
            return TradeResult(
                success=False,
                opportunity=opp,
                error=reason
            )

        log.info(
            "executing_arbitrage",
            question=opp.market.question[:40],
            margin=f"{opp.profit_margin:.2%}",
            capital=f"${opp.required_capital:.2f}"
        )

        yes_book = self.client.get_order_book(opp.market.yes_token.token_id)
        no_book = self.client.get_order_book(opp.market.no_token.token_id)

        if not yes_book or not no_book:
            return TradeResult(
                success=False,
                opportunity=opp,
                error="Could not fetch order books"
            )

        current_cost = yes_book.best_ask + no_book.best_ask
        current_margin = 1.0 - current_cost

        if current_margin < config.trading.min_profit_margin * 0.8:
            log.warning(
                "margin_degraded",
                original=f"{opp.profit_margin:.2%}",
                current=f"{current_margin:.2%}"
            )
            return TradeResult(
                success=False,
                opportunity=opp,
                error=f"Margin degraded: {current_margin:.2%}"
            )

        shares_to_buy = opp.required_capital / current_cost
        yes_amount = shares_to_buy * yes_book.best_ask
        no_amount = shares_to_buy * no_book.best_ask

        try:
            log.info("placing_yes_order", amount=f"${yes_amount:.2f}")
            yes_result = self.client.place_market_order(
                opp.market.yes_token.token_id,
                yes_amount,
                "BUY"
            )

            if not yes_result.get("success"):
                raise Exception(f"YES order failed: {yes_result}")

            log.info("placing_no_order", amount=f"${no_amount:.2f}")
            no_result = self.client.place_market_order(
                opp.market.no_token.token_id,
                no_amount,
                "BUY"
            )

            if not no_result.get("success"):
                log.error("no_order_failed", yes_filled=True)
                return TradeResult(
                    success=False,
                    opportunity=opp,
                    yes_order=yes_result,
                    no_order=no_result,
                    error="NO order failed after YES filled - EXPOSED POSITION"
                )

            actual_profit = (shares_to_buy * 1.0) - (yes_amount + no_amount)

            self.risk.last_trade_time = datetime.utcnow()
            self.risk.daily_trades += 1
            self.risk.daily_pnl += actual_profit
            self.risk.consecutive_losses = 0
            self.risk.total_invested += opp.required_capital

            result = TradeResult(
                success=True,
                opportunity=opp,
                yes_order=yes_result,
                no_order=no_result,
                actual_profit=actual_profit
            )
            self._trades.append(result)

            log.info(
                "trade_success",
                profit=f"${actual_profit:.2f}",
                daily_pnl=f"${self.risk.daily_pnl:.2f}"
            )

            return result

        except Exception as e:
            log.error("trade_error", error=str(e))
            self.risk.consecutive_losses += 1

            return TradeResult(
                success=False,
                opportunity=opp,
                error=str(e)
            )

    def pause(self):
        self._paused = True
        log.warning("trading_paused")

    def resume(self):
        self._paused = False
        log.info("trading_resumed")

    def get_stats(self) -> dict:
        return {
            "daily_pnl": self.risk.daily_pnl,
            "daily_trades": self.risk.daily_trades,
            "consecutive_losses": self.risk.consecutive_losses,
            "total_trades": len(self._trades),
            "successful_trades": sum(1 for t in self._trades if t.success),
            "total_invested": self.risk.total_invested,
            "paused": self._paused
        }
