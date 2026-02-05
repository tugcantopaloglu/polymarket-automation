from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, AsyncGenerator
from datetime import datetime, timezone
from enum import Enum

from ..client import PolymarketClient, MarketInfo, OrderBook
from ..portfolio import PortfolioManager
from ..utils.logging import get_logger

log = get_logger(__name__)

class StrategyType(Enum):
    ARBITRAGE = "arbitrage"
    BONDING = "bonding"
    MOMENTUM = "momentum"
    VALUE = "value"
    WHALE_FOLLOWING = "whale_following"
    MEAN_REVERSION = "mean_reversion"

@dataclass
class StrategyResult:
    strategy: StrategyType
    market: MarketInfo
    action: str
    side: str
    size: float
    price: float
    expected_profit: float
    confidence: float
    reason: str
    metadata: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    @property
    def is_actionable(self) -> bool:
        return self.action in ("BUY", "SELL") and self.size > 0 and self.confidence >= 0.5

class Strategy(ABC):
    def __init__(
        self,
        client: PolymarketClient,
        portfolio: PortfolioManager,
        name: str = None,
        enabled: bool = True
    ):
        self.client = client
        self.portfolio = portfolio
        self.name = name or self.__class__.__name__
        self.enabled = enabled
        self._last_scan = None
        self._opportunities_found = 0
        self._trades_executed = 0
    
    @property
    @abstractmethod
    def strategy_type(self) -> StrategyType:
        pass
    
    @abstractmethod
    async def scan(self, markets: List[MarketInfo]) -> AsyncGenerator[StrategyResult, None]:
        pass
    
    @abstractmethod
    async def evaluate(self, market: MarketInfo, book: OrderBook = None) -> Optional[StrategyResult]:
        pass
    
    def should_execute(self, result: StrategyResult) -> bool:
        if not self.enabled:
            return False
        
        limits = self.portfolio.get_risk_limits()
        if not limits.can_trade:
            log.debug("strategy_blocked", strategy=self.name, reason=limits.blocked_reason)
            return False
        
        if result.size > limits.max_position_size:
            result.size = limits.max_position_size
        
        return result.is_actionable
    
    async def execute(self, result: StrategyResult) -> bool:
        if not self.should_execute(result):
            return False
        
        log.info(
            "executing_strategy",
            strategy=self.name,
            market=result.market.question[:40],
            action=result.action,
            side=result.side,
            size=f"${result.size:.2f}"
        )
        
        if result.action == "BUY":
            success = await self.portfolio.open_position(
                market=result.market,
                side=result.side,
                size=result.size,
                price=result.price,
                strategy=self.strategy_type.value
            )
        else:
            token_id = (result.market.yes_token.token_id if result.side.upper() == "YES" 
                       else result.market.no_token.token_id)
            profit = await self.portfolio.close_position(
                token_id=token_id,
                current_price=result.price,
                reason=self.strategy_type.value
            )
            success = profit is not None
        
        if success:
            self._trades_executed += 1
        
        return success
    
    def get_stats(self) -> dict:
        return {
            "name": self.name,
            "type": self.strategy_type.value,
            "enabled": self.enabled,
            "opportunities_found": self._opportunities_found,
            "trades_executed": self._trades_executed,
            "last_scan": self._last_scan.isoformat() if self._last_scan else None
        }
