"""SQLite database wrapper for PSX portfolio tracker."""
import os
import sqlite3
from datetime import date

from models import Deposit, Dividend, Transaction


class Database:

    def __init__(self, db_path: str = "data/portfolio.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS trades (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol      TEXT    NOT NULL,
                    date        TEXT    NOT NULL,
                    mode        TEXT    NOT NULL,
                    shares      INTEGER NOT NULL,
                    trade_price REAL    NOT NULL,
                    created_at  TEXT    DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS dividends (
                    id               INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol           TEXT  NOT NULL,
                    date             TEXT  NOT NULL,
                    after_tax_amount REAL  NOT NULL,
                    shares           INTEGER NOT NULL,
                    per_share        REAL  NOT NULL,
                    created_at       TEXT  DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS deposits (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    amount     REAL NOT NULL,
                    date       TEXT NOT NULL,
                    broker     TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS price_cache (
                    symbol      TEXT PRIMARY KEY,
                    price       REAL NOT NULL,
                    market_date TEXT NOT NULL,
                    updated_at  TEXT DEFAULT (datetime('now'))
                );
            """)

    # ── Trades ────────────────────────────────────────────────────────────────

    def add_trade(self, trade: Transaction):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO trades (symbol, date, mode, shares, trade_price) VALUES (?, ?, ?, ?, ?)",
                (trade.symbol, trade.date.strftime('%Y-%m-%d'), trade.mode, trade.shares, trade.trade_price),
            )

    def get_existing_dates(self) -> set[date]:
        with self._conn() as conn:
            rows = conn.execute("SELECT DISTINCT date FROM trades").fetchall()
        return {date.fromisoformat(r["date"]) for r in rows}

    def get_all_trades(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT symbol, date, mode, shares, trade_price FROM trades ORDER BY date ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Dividends ─────────────────────────────────────────────────────────────

    def add_dividend(self, dividend: Dividend):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO dividends (symbol, date, after_tax_amount, shares, per_share) VALUES (?, ?, ?, ?, ?)",
                (dividend.symbol, dividend.date, dividend.after_tax_amount, dividend.shares, dividend.per_share),
            )

    def get_all_dividends(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT symbol, date, after_tax_amount, shares, per_share FROM dividends ORDER BY date ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Deposits ──────────────────────────────────────────────────────────────

    def add_deposit(self, deposit: Deposit):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO deposits (amount, date, broker) VALUES (?, ?, ?)",
                (deposit.amount, deposit.date, deposit.broker),
            )

    def get_all_deposits(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT amount, date, broker FROM deposits ORDER BY date ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Price cache ───────────────────────────────────────────────────────────

    def update_price_cache(self, prices: dict[str, float], market_date: str):
        with self._conn() as conn:
            for symbol, price in prices.items():
                conn.execute(
                    """INSERT OR REPLACE INTO price_cache (symbol, price, market_date, updated_at)
                       VALUES (?, ?, ?, datetime('now'))""",
                    (symbol, price, market_date),
                )

    def get_cached_prices(self) -> dict[str, dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT symbol, price, market_date FROM price_cache"
            ).fetchall()
        return {r["symbol"]: {"price": r["price"], "market_date": r["market_date"]} for r in rows}
