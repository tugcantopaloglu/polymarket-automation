import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ..config import config
from ..utils.logging import get_logger

log = get_logger(__name__)

@dataclass
class PriceRecord:
    token_id: str
    market_id: str
    price: float
    volume: float
    timestamp: datetime

@dataclass
class TradeRecord:
    id: int
    market_id: str
    token_id: str
    side: str
    price: float
    size: float
    profit: float
    strategy: str
    timestamp: datetime
    metadata: dict

@dataclass
class AlertRecord:
    id: int
    market_id: str
    alert_type: str
    message: str
    triggered_at: datetime
    acknowledged: bool

class Database:
    def __init__(self, db_path: str = None):
        self.db_path = Path(db_path or config.database.path)
        self._init_db()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    price REAL NOT NULL,
                    volume REAL DEFAULT 0,
                    timestamp TEXT NOT NULL,
                    UNIQUE(token_id, timestamp)
                );

                CREATE INDEX IF NOT EXISTS idx_price_token_time
                ON price_history(token_id, timestamp);

                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    token_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    price REAL NOT NULL,
                    size REAL NOT NULL,
                    profit REAL DEFAULT 0,
                    strategy TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_trades_time
                ON trades(timestamp);

                CREATE TABLE IF NOT EXISTS portfolio (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id TEXT NOT NULL UNIQUE,
                    market_id TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    size REAL NOT NULL,
                    avg_entry_price REAL NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    triggered_at TEXT NOT NULL,
                    acknowledged INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS market_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    market_id TEXT NOT NULL,
                    question TEXT,
                    yes_price REAL,
                    no_price REAL,
                    volume_24h REAL,
                    liquidity REAL,
                    timestamp TEXT NOT NULL,
                    UNIQUE(market_id, timestamp)
                );

                CREATE TABLE IF NOT EXISTS whale_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wallet_address TEXT NOT NULL,
                    market_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size REAL NOT NULL,
                    price REAL NOT NULL,
                    timestamp TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS strategy_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy TEXT NOT NULL,
                    date TEXT NOT NULL,
                    trades INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0,
                    total_profit REAL DEFAULT 0,
                    avg_profit REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    UNIQUE(strategy, date)
                );
            """)
        log.info("database_initialized", path=str(self.db_path))

    def record_price(self, token_id: str, market_id: str, price: float, volume: float = 0):
        timestamp = datetime.now(UTC).isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO price_history
                (token_id, market_id, price, volume, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (token_id, market_id, price, volume, timestamp))

    def get_price_history(
        self,
        token_id: str,
        hours: int = 24,
        limit: int = 1000
    ) -> list[PriceRecord]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM price_history
                WHERE token_id = ?
                AND timestamp >= datetime('now', ?)
                ORDER BY timestamp DESC
                LIMIT ?
            """, (token_id, f'-{hours} hours', limit)).fetchall()

        return [
            PriceRecord(
                token_id=row["token_id"],
                market_id=row["market_id"],
                price=row["price"],
                volume=row["volume"],
                timestamp=datetime.fromisoformat(row["timestamp"])
            )
            for row in rows
        ]

    def record_trade(
        self,
        market_id: str,
        token_id: str,
        side: str,
        price: float,
        size: float,
        profit: float,
        strategy: str,
        metadata: dict = None
    ):
        timestamp = datetime.now(UTC).isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO trades
                (market_id, token_id, side, price, size, profit, strategy, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (market_id, token_id, side, price, size, profit, strategy, timestamp,
                  json.dumps(metadata or {})))

    def get_trades(
        self,
        strategy: str = None,
        hours: int = 24,
        limit: int = 100
    ) -> list[TradeRecord]:
        with self._get_conn() as conn:
            if strategy:
                rows = conn.execute("""
                    SELECT * FROM trades
                    WHERE strategy = ?
                    AND timestamp >= datetime('now', ?)
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (strategy, f'-{hours} hours', limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM trades
                    WHERE timestamp >= datetime('now', ?)
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (f'-{hours} hours', limit)).fetchall()

        return [
            TradeRecord(
                id=row["id"],
                market_id=row["market_id"],
                token_id=row["token_id"],
                side=row["side"],
                price=row["price"],
                size=row["size"],
                profit=row["profit"],
                strategy=row["strategy"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=json.loads(row["metadata"])
            )
            for row in rows
        ]

    def update_portfolio(
        self,
        token_id: str,
        market_id: str,
        outcome: str,
        size: float,
        avg_entry_price: float
    ):
        timestamp = datetime.now(UTC).isoformat()
        with self._get_conn() as conn:
            if size <= 0:
                conn.execute("DELETE FROM portfolio WHERE token_id = ?", (token_id,))
            else:
                conn.execute("""
                    INSERT OR REPLACE INTO portfolio
                    (token_id, market_id, outcome, size, avg_entry_price, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (token_id, market_id, outcome, size, avg_entry_price, timestamp))

    def get_portfolio(self) -> list[dict]:
        with self._get_conn() as conn:
            rows = conn.execute("SELECT * FROM portfolio").fetchall()
        return [dict(row) for row in rows]

    def record_alert(self, market_id: str, alert_type: str, message: str):
        timestamp = datetime.now(UTC).isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO alerts (market_id, alert_type, message, triggered_at)
                VALUES (?, ?, ?, ?)
            """, (market_id, alert_type, message, timestamp))

    def get_unacknowledged_alerts(self, limit: int = 50) -> list[AlertRecord]:
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT * FROM alerts
                WHERE acknowledged = 0
                ORDER BY triggered_at DESC
                LIMIT ?
            """, (limit,)).fetchall()

        return [
            AlertRecord(
                id=row["id"],
                market_id=row["market_id"],
                alert_type=row["alert_type"],
                message=row["message"],
                triggered_at=datetime.fromisoformat(row["triggered_at"]),
                acknowledged=bool(row["acknowledged"])
            )
            for row in rows
        ]

    def acknowledge_alert(self, alert_id: int):
        with self._get_conn() as conn:
            conn.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))

    def record_market_snapshot(
        self,
        market_id: str,
        question: str,
        yes_price: float,
        no_price: float,
        volume_24h: float,
        liquidity: float
    ):
        timestamp = datetime.now(UTC).replace(second=0, microsecond=0).isoformat()
        with self._get_conn() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO market_snapshots
                (market_id, question, yes_price, no_price, volume_24h, liquidity, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (market_id, question, yes_price, no_price, volume_24h, liquidity, timestamp))

    def update_strategy_performance(
        self,
        strategy: str,
        profit: float,
        is_win: bool
    ):
        date = datetime.now(UTC).strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            conn.execute("""
                INSERT INTO strategy_performance (strategy, date, trades, wins, losses, total_profit)
                VALUES (?, ?, 1, ?, ?, ?)
                ON CONFLICT(strategy, date) DO UPDATE SET
                    trades = trades + 1,
                    wins = wins + ?,
                    losses = losses + ?,
                    total_profit = total_profit + ?
            """, (strategy, date, 1 if is_win else 0, 0 if is_win else 1, profit,
                  1 if is_win else 0, 0 if is_win else 1, profit))

    def get_strategy_stats(self, strategy: str = None, days: int = 30) -> list[dict]:
        with self._get_conn() as conn:
            if strategy:
                rows = conn.execute("""
                    SELECT * FROM strategy_performance
                    WHERE strategy = ?
                    AND date >= date('now', ?)
                    ORDER BY date DESC
                """, (strategy, f'-{days} days')).fetchall()
            else:
                rows = conn.execute("""
                    SELECT strategy,
                           SUM(trades) as total_trades,
                           SUM(wins) as total_wins,
                           SUM(losses) as total_losses,
                           SUM(total_profit) as total_profit,
                           AVG(total_profit) as avg_daily_profit
                    FROM strategy_performance
                    WHERE date >= date('now', ?)
                    GROUP BY strategy
                """, (f'-{days} days',)).fetchall()
        return [dict(row) for row in rows]

    def cleanup_old_data(self, days: int = 90):
        with self._get_conn() as conn:
            conn.execute("""
                DELETE FROM price_history
                WHERE timestamp < datetime('now', ?)
            """, (f'-{days} days',))

            conn.execute("""
                DELETE FROM market_snapshots
                WHERE timestamp < datetime('now', ?)
            """, (f'-{days} days',))

            deleted = conn.total_changes
            log.info("cleaned_old_data", deleted_rows=deleted)
        return deleted

db = Database()
