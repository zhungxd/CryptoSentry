import aiosqlite
import os
from datetime import datetime

import pandas as pd


class Storage:
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger
        self.db_path = "data/crypto.db"
        self.db = None

    async def init(self):
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.db = await aiosqlite.connect(self.db_path)
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self._create_tables()
        self.logger.info(f"数据库已初始化: {self.db_path}")

    async def _create_tables(self):
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS klines (
                symbol TEXT NOT NULL,
                interval TEXT NOT NULL,
                open_time TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (symbol, interval, open_time)
            )
        """)

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                indicator_name TEXT NOT NULL,
                indicator_value TEXT,
                price REAL,
                strength TEXT,
                triggered_at TEXT NOT NULL,
                notified INTEGER DEFAULT 0
            )
        """)

        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS price_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                direction TEXT NOT NULL,
                triggered_at TEXT NOT NULL
            )
        """)

        await self.db.commit()

    async def save_klines(self, df: pd.DataFrame):
        if df.empty:
            return
        rows = []
        for _, row in df.iterrows():
            open_time = row["open_time"]
            if isinstance(open_time, pd.Timestamp):
                open_time = open_time.isoformat()
            rows.append((
                row["symbol"], row["interval"], open_time,
                row["open"], row["high"], row["low"],
                row["close"], row["volume"]
            ))

        await self.db.executemany("""
            INSERT OR REPLACE INTO klines (symbol, interval, open_time, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        await self.db.commit()

    async def get_klines(self, symbol: str, interval: str, limit: int = 500) -> pd.DataFrame:
        cursor = await self.db.execute("""
            SELECT open_time, open, high, low, close, volume
            FROM klines
            WHERE symbol = ? AND interval = ?
            ORDER BY open_time DESC
            LIMIT ?
        """, (symbol, interval, limit))
        rows = await cursor.fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["open_time", "open", "high", "low", "close", "volume"])
        df = df.iloc[::-1].reset_index(drop=True)
        df["open_time"] = pd.to_datetime(df["open_time"])
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = df[col].astype(float)
        df["symbol"] = symbol
        df["interval"] = interval
        return df

    async def save_signal(self, symbol: str, signal_type: str, indicator_name: str,
                          indicator_value: str, price: float, strength: str):
        now = datetime.now().isoformat()
        await self.db.execute("""
            INSERT INTO signals (symbol, signal_type, indicator_name, indicator_value, price, strength, triggered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (symbol, signal_type, indicator_name, indicator_value, price, strength, now))
        await self.db.commit()

    async def get_recent_signals(self, symbol: str, minutes: int = 60) -> list:
        cursor = await self.db.execute("""
            SELECT signal_type, indicator_name, triggered_at
            FROM signals
            WHERE symbol = ? AND triggered_at >= datetime('now', ?)
            ORDER BY triggered_at DESC
        """, (symbol, f"-{minutes} minutes"))
        return await cursor.fetchall()

    async def save_price_alert(self, symbol: str, price: float, direction: str):
        now = datetime.now().isoformat()
        await self.db.execute("""
            INSERT INTO price_alerts (symbol, price, direction, triggered_at)
            VALUES (?, ?, ?, ?)
        """, (symbol, price, direction, now))
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()
            self.logger.info("数据库连接已关闭")
