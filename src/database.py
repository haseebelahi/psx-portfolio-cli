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
                    ldcp        REAL NOT NULL DEFAULT 0,
                    market_date TEXT NOT NULL,
                    updated_at  TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS shariah_cache (
                    symbol      TEXT PRIMARY KEY,
                    debt_ratio  REAL,
                    income_pct  REAL,
                    updated_at  TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS index_history (
                    name  TEXT NOT NULL,
                    date  TEXT NOT NULL,
                    value REAL NOT NULL,
                    PRIMARY KEY (name, date)
                );
                CREATE TABLE IF NOT EXISTS portfolio_history (
                    date           TEXT PRIMARY KEY,
                    nlv            REAL NOT NULL,
                    market_value   REAL NOT NULL,
                    cash_balance   REAL NOT NULL,
                    invested       REAL NOT NULL,
                    total_deposits REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS symbol_sector (
                    symbol     TEXT PRIMARY KEY,
                    sector     TEXT NOT NULL,
                    updated_at TEXT DEFAULT (datetime('now'))
                );
            """)
            # Migrate existing price_cache tables that predate the ldcp column
            try:
                conn.execute("ALTER TABLE price_cache ADD COLUMN ldcp REAL NOT NULL DEFAULT 0")
            except Exception:
                pass

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

    def update_price_cache(self, prices: dict[str, float], ldcps: dict[str, float], market_date: str):
        with self._conn() as conn:
            for symbol, price in prices.items():
                conn.execute(
                    """INSERT OR REPLACE INTO price_cache (symbol, price, ldcp, market_date, updated_at)
                       VALUES (?, ?, ?, ?, datetime('now'))""",
                    (symbol, price, ldcps.get(symbol, 0), market_date),
                )

    def get_cached_prices(self) -> dict[str, dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT symbol, price, ldcp, market_date, updated_at FROM price_cache"
            ).fetchall()
        return {
            r["symbol"]: {
                "price": r["price"],
                "ldcp": r["ldcp"],
                "market_date": r["market_date"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        }

    # ── Symbol sectors ────────────────────────────────────────────────────────

    def update_symbol_sectors(self, sectors: dict[str, str]):
        """Upsert {symbol: sector} scraped from PSX company pages."""
        with self._conn() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO symbol_sector (symbol, sector, updated_at)
                   VALUES (?, ?, datetime('now'))""",
                list(sectors.items()),
            )

    def get_symbol_sectors(self) -> dict[str, str]:
        """Return {symbol: sector} for all known symbols."""
        with self._conn() as conn:
            rows = conn.execute("SELECT symbol, sector FROM symbol_sector").fetchall()
        return {r["symbol"]: r["sector"] for r in rows}

    # ── Shariah cache ─────────────────────────────────────────────────────────

    def update_shariah_cache(self, data: dict[str, dict]):
        with self._conn() as conn:
            for symbol, entry in data.items():
                conn.execute(
                    """INSERT OR REPLACE INTO shariah_cache (symbol, debt_ratio, income_pct, updated_at)
                       VALUES (?, ?, ?, datetime('now'))""",
                    (symbol, entry.get("debt_ratio"), entry.get("income_pct")),
                )

    # ── Index history ─────────────────────────────────────────────────────────

    def add_index_values(self, name: str, records: dict[str, float]):
        """Upsert {date: value} records for the given index name."""
        with self._conn() as conn:
            conn.executemany(
                "INSERT OR REPLACE INTO index_history (name, date, value) VALUES (?, ?, ?)",
                [(name, d, v) for d, v in records.items()],
            )

    def get_index_history(self, name: str) -> list[tuple[str, float]]:
        """Return [(date, value), ...] sorted ascending for the given index."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT date, value FROM index_history WHERE name = ? ORDER BY date ASC",
                (name,),
            ).fetchall()
        return [(r["date"], r["value"]) for r in rows]

    # ── Portfolio history ─────────────────────────────────────────────────────

    def save_portfolio_snapshot(self, date: str, nlv: float, market_value: float,
                                cash_balance: float, invested: float, total_deposits: float):
        """Insert a daily snapshot — silently skips if date already recorded."""
        with self._conn() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO portfolio_history
                   (date, nlv, market_value, cash_balance, invested, total_deposits)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (date, nlv, market_value, cash_balance, invested, total_deposits),
            )

    def get_portfolio_history(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT date, nlv, market_value, cash_balance, invested, total_deposits
                   FROM portfolio_history ORDER BY date ASC"""
            ).fetchall()
        return [dict(r) for r in rows]

    def get_shariah_cache(self, max_age_days: int = 90) -> dict[str, dict] | None:
        """Return cached shariah data if fresher than max_age_days, else None."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT symbol, debt_ratio, income_pct
                   FROM shariah_cache
                   WHERE updated_at >= datetime('now', ?)""",
                (f"-{max_age_days} days",),
            ).fetchall()
        if not rows:
            return None
        return {r["symbol"]: {"debt_ratio": r["debt_ratio"], "income_pct": r["income_pct"]} for r in rows}
