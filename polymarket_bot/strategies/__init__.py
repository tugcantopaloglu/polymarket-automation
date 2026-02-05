from .base import Strategy, StrategyResult, StrategyType
from .arbitrage import ArbitrageStrategy
from .bonding import BondingStrategy
from .momentum import MomentumStrategy, MeanReversionStrategy
from .value import ValueStrategy
from .whale import WhaleFollowingStrategy

WhaleStrategy = WhaleFollowingStrategy
