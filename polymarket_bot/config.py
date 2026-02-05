import os
from dataclasses import dataclass, field
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

@dataclass
class TradingConfig:
    min_profit_margin: float = 0.02
    max_position_usd: float = 50.0
    max_daily_loss_usd: float = 20.0
    min_liquidity_usd: float = 100.0
    max_slippage: float = 0.02
    cooldown_seconds: int = 5
    max_portfolio_exposure: float = 0.5
    kelly_fraction: float = 0.25
    stop_loss_pct: float = 0.15
    take_profit_pct: float = 0.30

@dataclass
class AlertConfig:
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    discord_webhook_url: str = ""
    price_change_threshold: float = 0.05
    volume_spike_threshold: float = 3.0
    opportunity_min_profit: float = 1.0

@dataclass
class RateLimitConfig:
    requests_per_second: float = 5.0
    burst_limit: int = 20
    retry_attempts: int = 3
    retry_delay_base: float = 1.0
    retry_delay_max: float = 60.0

@dataclass
class DatabaseConfig:
    path: str = "polymarket_data.db"
    backup_interval_hours: int = 24

@dataclass
class Config:
    host: str = "https://clob.polymarket.com"
    gamma_host: str = "https://gamma-api.polymarket.com"
    chain_id: int = 137
    trading: TradingConfig = field(default_factory=TradingConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    log_level: str = "INFO"
    data_dir: Path = field(default_factory=lambda: Path("data"))

    def __post_init__(self):
        self.data_dir.mkdir(exist_ok=True)
        self._load_env()

    def _load_env(self):
        self.alerts.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.alerts.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.alerts.discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL", "")

        if margin := os.getenv("MIN_PROFIT_MARGIN"):
            self.trading.min_profit_margin = float(margin)
        if pos := os.getenv("MAX_POSITION_USD"):
            self.trading.max_position_usd = float(pos)
        if loss := os.getenv("MAX_DAILY_LOSS_USD"):
            self.trading.max_daily_loss_usd = float(loss)

class SecureKeyStore:
    def __init__(self, key_file: str = ".keystore"):
        self.key_file = Path(key_file)
        self._fernet = None

    def _get_or_create_encryption_key(self) -> bytes:
        enc_key_file = self.key_file.with_suffix('.enc')
        if enc_key_file.exists():
            return enc_key_file.read_bytes()
        key = Fernet.generate_key()
        enc_key_file.write_bytes(key)
        enc_key_file.chmod(0o600)
        return key

    @property
    def fernet(self) -> Fernet:
        if self._fernet is None:
            self._fernet = Fernet(self._get_or_create_encryption_key())
        return self._fernet

    def store_private_key(self, private_key: str):
        encrypted = self.fernet.encrypt(private_key.encode())
        self.key_file.write_bytes(encrypted)
        self.key_file.chmod(0o600)

    def load_private_key(self) -> str | None:
        if not self.key_file.exists():
            return None
        encrypted = self.key_file.read_bytes()
        return self.fernet.decrypt(encrypted).decode()

    def has_key(self) -> bool:
        return self.key_file.exists()

config = Config()
keystore = SecureKeyStore()
