"""PSX price fetcher — scrapes dps.psx.com.pk/company/{SYMBOL} in parallel."""
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time, timezone

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
# <div class="quote__sector"><span>COMMERCIAL BANKS</span></div>
SECTOR_RE   = re.compile(r'class="quote__sector"><span>([^<]+)</span>')
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


INTRADAY_CACHE_SECS = 60


def should_use_cache(db) -> bool:
    """Return True when cache is still valid.

    After hours: reuse today's cache until next market open.
    During market hours: reuse if the cache is less than INTRADAY_CACHE_SECS old.
    """
    cached = db.get_cached_prices()
    if not cached:
        return False

    today_str = _now_pkt().strftime("%Y-%m-%d")

    if not is_market_open():
        return any(v["market_date"] == today_str for v in cached.values())

    # During market hours: use cache if freshly updated within the last 60 s
    sample = next(iter(cached.values()))
    updated_at = sample.get("updated_at")
    if not updated_at:
        return False
    try:
        cache_time = datetime.fromisoformat(updated_at).replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - cache_time).total_seconds()
        return age < INTRADAY_CACHE_SECS
    except (ValueError, TypeError):
        return False


def _fetch_one(symbol: str) -> tuple[str, float | None, float | None, str | None]:
    try:
        resp = requests.get(BASE_URL.format(symbol=symbol), timeout=10)
        resp.raise_for_status()
        html = resp.text
        pm = PRICE_RE.search(html)
        lm = LDCP_RE.search(html)
        sm = SECTOR_RE.search(html)
        price  = float(pm.group(1).replace(",", "")) if pm else None
        ldcp   = float(lm.group(1).replace(",", "")) if lm else None
        sector = sm.group(1).strip() if sm else None
        return symbol, price, ldcp, sector
    except Exception:
        return symbol, None, None, None


def _fetch_all(symbols: list[str]) -> tuple[dict[str, float], dict[str, float], dict[str, str]]:
    prices:  dict[str, float] = {}
    ldcps:   dict[str, float] = {}
    sectors: dict[str, str]   = {}
    with ThreadPoolExecutor(max_workers=min(20, len(symbols))) as pool:
        futures = {pool.submit(_fetch_one, sym): sym for sym in symbols}
        for future in as_completed(futures):
            sym, price, ldcp, sector = future.result()
            if price is not None:
                prices[sym] = price
            if ldcp is not None:
                ldcps[sym] = ldcp
            if sector is not None:
                sectors[sym] = sector
    return prices, ldcps, sectors


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

    fresh_prices, fresh_ldcps, fresh_sectors = _fetch_all(symbols)

    if fresh_prices:
        market_date = _now_pkt().strftime("%Y-%m-%d")
        db.update_price_cache(fresh_prices, fresh_ldcps, market_date)
    if fresh_sectors:
        db.update_symbol_sectors(fresh_sectors)

    prices: dict[str, float] = {}
    ldcps:  dict[str, float] = {}
    for sym in symbols:
        prices[sym] = fresh_prices.get(sym) or cached_prices.get(sym, 0)
        ldcps[sym]  = fresh_ldcps.get(sym)  or cached_ldcps.get(sym, 0)

    return prices, ldcps
