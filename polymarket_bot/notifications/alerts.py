import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

import aiohttp

from ..client import MarketInfo
from ..config import config
from ..data.database import db
from ..utils.logging import get_logger

log = get_logger(__name__)

class AlertType(Enum):
    PRICE_CHANGE = "price_change"
    VOLUME_SPIKE = "volume_spike"
    ARBITRAGE = "arbitrage"
    WHALE_ACTIVITY = "whale_activity"
    POSITION_UPDATE = "position_update"
    RISK_WARNING = "risk_warning"
    TRADE_EXECUTED = "trade_executed"
    MARKET_RESOLVED = "market_resolved"

@dataclass
class Alert:
    alert_type: AlertType
    title: str
    message: str
    market_id: str = ""
    severity: str = "INFO"
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def send(self, alert: Alert) -> bool:
        if not self.bot_token or not self.chat_id:
            return False

        emoji = self._get_emoji(alert)
        severity_label = f"[{alert.severity}]" if alert.severity != "INFO" else ""

        text = f"{emoji} *{alert.title}* {severity_label}\n\n{alert.message}"

        if alert.data:
            details = "\n".join(f"• {k}: `{v}`" for k, v in alert.data.items())
            text += f"\n\n{details}"

        text += f"\n\n🕐 {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"

        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True
                }
            ) as resp:
                if resp.status == 200:
                    log.debug("telegram_sent", alert_type=alert.alert_type.value)
                    return True
                else:
                    log.warning("telegram_failed", status=resp.status)
                    return False
        except Exception as e:
            log.error("telegram_error", error=str(e))
            return False

    def _get_emoji(self, alert: Alert) -> str:
        emoji_map = {
            AlertType.PRICE_CHANGE: "📊",
            AlertType.VOLUME_SPIKE: "📈",
            AlertType.ARBITRAGE: "💰",
            AlertType.WHALE_ACTIVITY: "🐋",
            AlertType.POSITION_UPDATE: "📋",
            AlertType.RISK_WARNING: "⚠️",
            AlertType.TRADE_EXECUTED: "✅",
            AlertType.MARKET_RESOLVED: "🏁"
        }
        return emoji_map.get(alert.alert_type, "ℹ️")

    async def close(self):
        if self._session:
            await self._session.close()

class DiscordNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def send(self, alert: Alert) -> bool:
        if not self.webhook_url:
            return False

        color = self._get_color(alert)

        embed = {
            "title": f"{self._get_emoji(alert)} {alert.title}",
            "description": alert.message,
            "color": color,
            "timestamp": alert.timestamp.isoformat(),
            "footer": {"text": f"Polymarket Bot | {alert.severity}"}
        }

        if alert.data:
            embed["fields"] = [
                {"name": k, "value": str(v), "inline": True}
                for k, v in list(alert.data.items())[:25]
            ]

        try:
            session = await self._get_session()
            async with session.post(
                self.webhook_url,
                json={"embeds": [embed]}
            ) as resp:
                if resp.status in (200, 204):
                    log.debug("discord_sent", alert_type=alert.alert_type.value)
                    return True
                else:
                    log.warning("discord_failed", status=resp.status)
                    return False
        except Exception as e:
            log.error("discord_error", error=str(e))
            return False

    def _get_color(self, alert: Alert) -> int:
        color_map = {
            "INFO": 0x3498db,
            "WARNING": 0xf39c12,
            "ERROR": 0xe74c3c,
            "SUCCESS": 0x2ecc71
        }
        return color_map.get(alert.severity, 0x3498db)

    def _get_emoji(self, alert: Alert) -> str:
        emoji_map = {
            AlertType.PRICE_CHANGE: "📊",
            AlertType.VOLUME_SPIKE: "📈",
            AlertType.ARBITRAGE: "💰",
            AlertType.WHALE_ACTIVITY: "🐋",
            AlertType.POSITION_UPDATE: "📋",
            AlertType.RISK_WARNING: "⚠️",
            AlertType.TRADE_EXECUTED: "✅",
            AlertType.MARKET_RESOLVED: "🏁"
        }
        return emoji_map.get(alert.alert_type, "ℹ️")

    async def close(self):
        if self._session:
            await self._session.close()

@dataclass
class PriceAlert:
    market_id: str
    token_id: str
    condition: str
    target_price: float
    current_price: float
    triggered: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

class AlertManager:
    def __init__(self):
        self.telegram = TelegramNotifier(
            config.alerts.telegram_bot_token,
            config.alerts.telegram_chat_id
        )
        self.discord = DiscordNotifier(config.alerts.discord_webhook_url)
        self.price_alerts: list[PriceAlert] = []
        self._price_cache: dict[str, float] = {}
        self._alert_cooldowns: dict[str, datetime] = {}
        self._cooldown_minutes = 5

    def _is_on_cooldown(self, key: str) -> bool:
        if key not in self._alert_cooldowns:
            return False
        elapsed = datetime.now(UTC) - self._alert_cooldowns[key]
        return elapsed < timedelta(minutes=self._cooldown_minutes)

    def _set_cooldown(self, key: str):
        self._alert_cooldowns[key] = datetime.now(UTC)

    async def send_alert(self, alert: Alert, force: bool = False):
        cooldown_key = f"{alert.alert_type.value}:{alert.market_id}"

        if not force and self._is_on_cooldown(cooldown_key):
            log.debug("alert_cooldown", key=cooldown_key)
            return

        db.record_alert(alert.market_id, alert.alert_type.value, alert.message)

        await asyncio.gather(
            self.telegram.send(alert),
            self.discord.send(alert),
            return_exceptions=True
        )

        self._set_cooldown(cooldown_key)
        log.info("alert_sent", type=alert.alert_type.value, severity=alert.severity)

    def add_price_alert(
        self,
        market_id: str,
        token_id: str,
        condition: str,
        target_price: float,
        current_price: float
    ):
        alert = PriceAlert(
            market_id=market_id,
            token_id=token_id,
            condition=condition,
            target_price=target_price,
            current_price=current_price
        )
        self.price_alerts.append(alert)
        log.info("price_alert_added", token_id=token_id, condition=condition, target=target_price)

    async def check_price_alerts(self, token_id: str, current_price: float):
        for alert in self.price_alerts:
            if alert.token_id != token_id or alert.triggered:
                continue

            triggered = False
            if alert.condition == "above" and current_price >= alert.target_price:
                triggered = True
            elif alert.condition == "below" and current_price <= alert.target_price:
                triggered = True

            if triggered:
                alert.triggered = True
                await self.send_alert(Alert(
                    alert_type=AlertType.PRICE_CHANGE,
                    title="Price Alert Triggered",
                    message=f"Price is now {alert.condition} {alert.target_price:.3f}",
                    market_id=alert.market_id,
                    severity="INFO",
                    data={
                        "Token": token_id[:16] + "...",
                        "Target": f"${alert.target_price:.3f}",
                        "Current": f"${current_price:.3f}",
                        "Condition": alert.condition.upper()
                    }
                ), force=True)

    async def check_price_movement(
        self,
        market: MarketInfo,
        previous_price: float,
        current_price: float
    ):
        if previous_price <= 0:
            return

        change = (current_price - previous_price) / previous_price

        if abs(change) >= config.alerts.price_change_threshold:
            direction = "📈 UP" if change > 0 else "📉 DOWN"
            await self.send_alert(Alert(
                alert_type=AlertType.PRICE_CHANGE,
                title=f"Significant Price Movement {direction}",
                message=f"{market.question[:100]}",
                market_id=market.condition_id,
                severity="WARNING" if abs(change) > 0.1 else "INFO",
                data={
                    "Previous": f"${previous_price:.3f}",
                    "Current": f"${current_price:.3f}",
                    "Change": f"{change:+.1%}"
                }
            ))

    async def alert_arbitrage_opportunity(
        self,
        market: MarketInfo,
        margin: float,
        expected_profit: float
    ):
        if expected_profit < config.alerts.opportunity_min_profit:
            return

        await self.send_alert(Alert(
            alert_type=AlertType.ARBITRAGE,
            title="Arbitrage Opportunity Detected",
            message=f"{market.question[:100]}",
            market_id=market.condition_id,
            severity="SUCCESS",
            data={
                "Margin": f"{margin:.2%}",
                "Expected Profit": f"${expected_profit:.2f}",
                "Yes Price": f"${market.yes_token.price:.3f}",
                "No Price": f"${market.no_token.price:.3f}"
            }
        ))

    async def alert_trade_executed(
        self,
        market: MarketInfo,
        side: str,
        size: float,
        price: float,
        profit: float,
        strategy: str
    ):
        await self.send_alert(Alert(
            alert_type=AlertType.TRADE_EXECUTED,
            title="Trade Executed",
            message=f"{market.question[:80]}",
            market_id=market.condition_id,
            severity="SUCCESS" if profit >= 0 else "WARNING",
            data={
                "Side": side,
                "Size": f"${size:.2f}",
                "Price": f"${price:.3f}",
                "Profit": f"${profit:+.2f}",
                "Strategy": strategy
            }
        ), force=True)

    async def alert_risk_warning(
        self,
        title: str,
        message: str,
        data: dict = None
    ):
        await self.send_alert(Alert(
            alert_type=AlertType.RISK_WARNING,
            title=title,
            message=message,
            severity="WARNING",
            data=data or {}
        ), force=True)

    async def alert_whale_activity(
        self,
        wallet: str,
        market: MarketInfo,
        side: str,
        size: float,
        price: float
    ):
        await self.send_alert(Alert(
            alert_type=AlertType.WHALE_ACTIVITY,
            title="Whale Activity Detected",
            message=f"{market.question[:80]}",
            market_id=market.condition_id,
            severity="INFO",
            data={
                "Wallet": wallet[:10] + "...",
                "Side": side,
                "Size": f"${size:.2f}",
                "Price": f"${price:.3f}"
            }
        ))

    def update_price_cache(self, token_id: str, price: float):
        previous = self._price_cache.get(token_id)
        self._price_cache[token_id] = price
        return previous

    async def close(self):
        await self.telegram.close()
        await self.discord.close()

alert_manager = AlertManager()
