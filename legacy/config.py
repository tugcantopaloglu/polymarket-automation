from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()

@dataclass
class TradingConfig:
    min_profit_margin: float = 0.05
    max_position_usd: float = 20.0
    max_daily_loss_usd: float = 5.0
    min_liquidity_usd: float = 50.0
    max_slippage: float = 0.02
    cooldown_seconds: int = 10

@dataclass
class Config:
    host: str = "https://clob.polymarket.com"
    gamma_host: str = "https://gamma-api.polymarket.com"
    chain_id: int = 137
    trading: TradingConfig = None

    def __post_init__(self):
        if self.trading is None:
            self.trading = TradingConfig()

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
