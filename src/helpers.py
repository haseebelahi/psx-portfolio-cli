"""Shared utilities for PSX CLI commands."""
import os

import yaml
from rich.console import Console

from database import Database

console = Console()
DB_PATH = "data/portfolio.db"


def get_db() -> Database:
    return Database(DB_PATH)


def _load_config() -> dict:
    with open("config/config.yaml") as f:
        return yaml.safe_load(f)


def _load_sectors() -> dict:
    try:
        with open("config/sectors.yaml") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


_DEFAULT_SHARIAH_PDF = "Merged_KMIALL_Notice_and_FinalList_June2025.pdf"


def _parse_shariah_pdf(pdf_path: str) -> dict[str, dict]:
    """Return {ticker: {income_pct, debt_ratio}} parsed from KMIALL screening PDF.

    Column layout (0-indexed):
      1 = Ticker
      4 = Debt Ratio (D/A < 37%)
      6 = Income Ratio (NCInc/TR) — used for purification
    """
    try:
        import pdfplumber
    except ImportError:
        console.print("[red]pdfplumber is required: uv add pdfplumber[/red]")
        return {}

    result: dict[str, dict] = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if len(row) < 7:
                        continue
                    ticker = row[1]
                    if not ticker:
                        continue
                    if ticker.strip().lower() == "ticker":
                        continue
                    ticker = ticker.strip()
                    if not ticker or len(ticker) > 10 or not ticker[0].isupper():
                        continue

                    def _pct(val) -> float | None:
                        try:
                            return float(str(val).strip().replace("%", ""))
                        except (ValueError, TypeError):
                            return None

                    income_pct = _pct(row[6])
                    debt_ratio = _pct(row[4])
                    if income_pct is not None or debt_ratio is not None:
                        result[ticker] = {
                            "income_pct": income_pct,
                            "debt_ratio": debt_ratio,
                        }
    return result


def _resolve_shariah_pdf(shariah_pdf: str | None, db=None) -> dict[str, dict]:
    """Return shariah data from SQLite cache (90-day TTL), falling back to PDF parse."""
    if db is None:
        db = get_db()

    cached = db.get_shariah_cache()
    if cached:
        return cached

    pdf_path = shariah_pdf or (_DEFAULT_SHARIAH_PDF if os.path.exists(_DEFAULT_SHARIAH_PDF) else None)
    if not pdf_path:
        return {}
    if not os.path.exists(pdf_path):
        console.print(f"[red]Shariah PDF not found: {pdf_path}[/red]")
        return {}

    with console.status("Parsing Shariah PDF…"):
        data = _parse_shariah_pdf(pdf_path)

    if data:
        db.update_shariah_cache(data)
        console.print(f"[dim]Shariah data cached ({len(data)} tickers, valid for 90 days)[/dim]")

    return data


def _group_avg_buy(trades: list[dict]) -> dict[str, float]:
    """Return {symbol: avg_buy_price} weighted across all BUY trades."""
    totals: dict[str, list] = {}
    for t in trades:
        if t["mode"] != "BUY":
            continue
        sym = t["symbol"]
        if sym not in totals:
            totals[sym] = [0.0, 0]  # [cost, shares]
        totals[sym][0] += t["shares"] * t["trade_price"]
        totals[sym][1] += t["shares"]
    return {sym: v[0] / v[1] for sym, v in totals.items() if v[1] > 0}
