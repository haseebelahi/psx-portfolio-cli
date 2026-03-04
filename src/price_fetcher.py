"""PSX price fetcher — scrapes dps.psx.com.pk/company/{SYMBOL} in parallel."""
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time

import pytz
import requests

PKT = pytz.timezone("Asia/Karachi")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(15, 30)

BASE_URL    = "https://dps.psx.com.pk/company/{symbol}"
PSX_HOME    = "https://dps.psx.com.pk/"
# <div class="quote__close">Rs.209.02</div>
PRICE_RE    = re.compile(r'class="quote__close">\s*Rs\.?([\d,]+\.?\d*)')
# <div class="stats_label">LDCP</div><div class="stats_value">198.72</div>
LDCP_RE     = re.compile(r'stats_label">LDCP</div><div class="stats_value">([\d,]+\.?\d*)')
# Matches name + value + change% for each top index block
INDEX_RE    = re.compile(
    r'topIndices__item__name">(\w+)</div>'
    r'<div class="topIndices__item__val">([\d,]+\.?\d*)</div>'
    r'.*?topIndices__item__changep">\(([+-]?[\d.]+%)\)',
    re.DOTALL,
)


def _now_pkt() -> datetime:
    return datetime.now(PKT)


def is_market_open() -> bool:
    now = _now_pkt()
    if now.weekday() >= 5:
        return False
    t = now.time()
    return MARKET_OPEN <= t <= MARKET_CLOSE


def should_use_cache(db) -> bool:
    """Return True when after-hours cache is still valid for today."""
    if is_market_open():
        return False
    today_str = _now_pkt().strftime("%Y-%m-%d")
    cached = db.get_cached_prices()
    return any(v["market_date"] == today_str for v in cached.values())


def _fetch_one(symbol: str) -> tuple[str, float | None, float | None]:
    try:
        resp = requests.get(BASE_URL.format(symbol=symbol), timeout=10)
        resp.raise_for_status()
        html = resp.text
        pm = PRICE_RE.search(html)
        lm = LDCP_RE.search(html)
        price = float(pm.group(1).replace(",", "")) if pm else None
        ldcp  = float(lm.group(1).replace(",", "")) if lm else None
        return symbol, price, ldcp
    except Exception:
        return symbol, None, None


def _fetch_all(symbols: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    prices: dict[str, float] = {}
    ldcps:  dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=min(20, len(symbols))) as pool:
        futures = {pool.submit(_fetch_one, sym): sym for sym in symbols}
        for future in as_completed(futures):
            sym, price, ldcp = future.result()
            if price is not None:
                prices[sym] = price
            if ldcp is not None:
                ldcps[sym] = ldcp
    return prices, ldcps


def fetch_indices(names: list[str] = ("KSE100", "KMI30")) -> dict[str, dict]:
    """Fetch index values and day-change % from the PSX homepage.

    Returns {name: {"value": float, "change_pct": str}} for each requested index.
    """
    try:
        resp = requests.get(PSX_HOME, timeout=15)
        resp.raise_for_status()
        result = {}
        for m in INDEX_RE.finditer(resp.text):
            name = m.group(1)
            if name in names:
                result[name] = {
                    "value":      float(m.group(2).replace(",", "")),
                    "change_pct": m.group(3),
                }
        return result
    except Exception:
        return {}


def get_prices(db, symbols: list[str]) -> tuple[dict[str, float], dict[str, float]]:
    """Return (prices, ldcps) for the given symbols, using cache when appropriate."""
    cached_data   = db.get_cached_prices()
    cached_prices = {sym: d["price"] for sym, d in cached_data.items()}
    cached_ldcps  = {sym: d["ldcp"]  for sym, d in cached_data.items()}

    if should_use_cache(db):
        prices = {sym: cached_prices[sym] for sym in symbols if sym in cached_prices}
        ldcps  = {sym: cached_ldcps[sym]  for sym in symbols if sym in cached_ldcps}
        return prices, ldcps

    fresh_prices, fresh_ldcps = _fetch_all(symbols)

    if fresh_prices:
        market_date = _now_pkt().strftime("%Y-%m-%d")
        db.update_price_cache(fresh_prices, fresh_ldcps, market_date)

    prices: dict[str, float] = {}
    ldcps:  dict[str, float] = {}
    for sym in symbols:
        prices[sym] = fresh_prices.get(sym) or cached_prices.get(sym, 0)
        ldcps[sym]  = fresh_ldcps.get(sym)  or cached_ldcps.get(sym, 0)

    return prices, ldcps
