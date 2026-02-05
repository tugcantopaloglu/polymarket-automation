from .arbitrage import ArbitrageStrategy as ArbitrageStrategy
from .base import Strategy as Strategy
from .base import StrategyResult as StrategyResult
from .base import StrategyType as StrategyType
from .bonding import BondingStrategy as BondingStrategy
from .momentum import MeanReversionStrategy as MeanReversionStrategy
from .momentum import MomentumStrategy as MomentumStrategy
from .value import ValueStrategy as ValueStrategy
from .whale import WhaleFollowingStrategy as WhaleFollowingStrategy

WhaleStrategy = WhaleFollowingStrategy

__all__ = [
    "ArbitrageStrategy",
    "Strategy",
    "StrategyResult",
    "StrategyType",
    "BondingStrategy",
    "MeanReversionStrategy",
    "MomentumStrategy",
    "ValueStrategy",
    "WhaleFollowingStrategy",
    "WhaleStrategy",
]
