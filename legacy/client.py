import asyncio
import aiohttp
import structlog
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, MarketOrderArgs, OrderType, BookParams
from py_clob_client.order_builder.constants import BUY, SELL

from config import config, keystore

log = structlog.get_logger()

@dataclass
class TokenInfo:
    token_id: str
    outcome: str
    price: float
    
@dataclass
class MarketInfo:
    condition_id: str
    question: str
    yes_token: TokenInfo
    no_token: TokenInfo
    
    @property
    def spread(self) -> float:
        return 1.0 - (self.yes_token.price + self.no_token.price)
    
    @property
    def is_arbitrage(self) -> bool:
        return self.spread > config.trading.min_profit_margin

@dataclass
class OrderBook:
    bids: list
    asks: list
    best_bid: float
    best_ask: float
    bid_liquidity: float
    ask_liquidity: float

class PolymarketClient:
    def __init__(self, private_key: Optional[str] = None, funder: Optional[str] = None):
        self.private_key = private_key or keystore.load_private_key()
        self.funder = funder
        self._clob: Optional[ClobClient] = None
        self._session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self._session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()
            
    @property
    def clob(self) -> ClobClient:
        if self._clob is None:
            if self.private_key:
                self._clob = ClobClient(
                    config.host,
                    key=self.private_key,
                    chain_id=config.chain_id,
                    signature_type=0,
                    funder=self.funder
                )
                self._clob.set_api_creds(self._clob.create_or_derive_api_creds())
            else:
                self._clob = ClobClient(config.host)
        return self._clob
    
    async def get_markets(self, active: bool = True, limit: int = 100) -> list[dict]:
        params = {"active": str(active).lower(), "limit": limit}
        async with self._session.get(
            f"{config.gamma_host}/events",
            params=params
        ) as resp:
            data = await resp.json()
            return data if isinstance(data, list) else []
    
    async def get_market_info(self, condition_id: str) -> Optional[MarketInfo]:
        try:
            async with self._session.get(
                f"{config.gamma_host}/markets/{condition_id}"
            ) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
                tokens = data.get("tokens", [])
                if len(tokens) < 2:
                    return None
                    
                yes_token = next((t for t in tokens if t["outcome"] == "Yes"), None)
                no_token = next((t for t in tokens if t["outcome"] == "No"), None)
                
                if not yes_token or not no_token:
                    return None
                    
                return MarketInfo(
                    condition_id=condition_id,
                    question=data.get("question", ""),
                    yes_token=TokenInfo(
                        token_id=yes_token["token_id"],
                        outcome="Yes",
                        price=float(yes_token.get("price", 0))
                    ),
                    no_token=TokenInfo(
                        token_id=no_token["token_id"],
                        outcome="No",  
                        price=float(no_token.get("price", 0))
                    )
                )
        except Exception as e:
            log.error("get_market_info_error", error=str(e), condition_id=condition_id)
            return None
    
    def get_order_book(self, token_id: str) -> Optional[OrderBook]:
        try:
            book = self.clob.get_order_book(token_id)
            bids = book.bids or []
            asks = book.asks or []
            
            best_bid = float(bids[0].price) if bids else 0
            best_ask = float(asks[0].price) if asks else 1
            
            bid_liq = sum(float(b.size) * float(b.price) for b in bids[:5])
            ask_liq = sum(float(a.size) * float(a.price) for a in asks[:5])
            
            return OrderBook(
                bids=bids,
                asks=asks,
                best_bid=best_bid,
                best_ask=best_ask,
                bid_liquidity=bid_liq,
                ask_liquidity=ask_liq
            )
        except Exception as e:
            log.error("get_order_book_error", error=str(e), token_id=token_id)
            return None
    
    def get_midpoint(self, token_id: str) -> Optional[float]:
        try:
            return float(self.clob.get_midpoint(token_id))
        except:
            return None
            
    def place_market_order(self, token_id: str, amount: float, side: str) -> dict:
        order_side = BUY if side.upper() == "BUY" else SELL
        order = MarketOrderArgs(
            token_id=token_id,
            amount=amount,
            side=order_side,
            order_type=OrderType.FOK
        )
        signed = self.clob.create_market_order(order)
        return self.clob.post_order(signed, OrderType.FOK)
    
    def place_limit_order(self, token_id: str, price: float, size: float, side: str) -> dict:
        order_side = BUY if side.upper() == "BUY" else SELL
        order = OrderArgs(
            token_id=token_id,
            price=price,
            size=size,
            side=order_side
        )
        signed = self.clob.create_order(order)
        return self.clob.post_order(signed, OrderType.GTC)
    
    def get_balance(self) -> float:
        try:
            bal = self.clob.get_balance_allowance()
            return float(bal.get("balance", 0)) if bal else 0
        except:
            return 0
