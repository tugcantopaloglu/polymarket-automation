"""
Polymarket Trading Bot - Professional Prediction Market Trading Tool

Features:
- Multiple trading strategies (Arbitrage, Bonding, Whale Following, Momentum, Value)
- Advanced market analysis (sentiment, momentum, volatility, Kelly criterion)
- Real-time price alerts and notifications (Telegram/Discord)
- Historical data tracking with SQLite
- Portfolio management and risk assessment
- API rate limiting and error recovery
- Comprehensive logging and monitoring
"""

__version__ = "2.0.0"
__author__ = "Tuğcan Topaloğlu"

from .alerts import AlertManager as AlertManager
from .client import PolymarketClient as PolymarketClient
from .config import Config as Config
from .config import config as config
from .portfolio import PortfolioManager as PortfolioManager

__all__ = [
    "AlertManager",
    "PolymarketClient",
    "Config",
    "config",
    "PortfolioManager",
]
