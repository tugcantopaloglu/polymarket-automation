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

from .config import Config, config
from .client import PolymarketClient
from .portfolio import PortfolioManager
from .alerts import AlertManager
