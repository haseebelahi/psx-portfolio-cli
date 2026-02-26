"""PSX price fetcher — scrapes dps.psx.com.pk/company/{SYMBOL} in parallel."""
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time

import pytz
import requests

PKT = pytz.timezone("Asia/Karachi")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(15, 30)

BASE_URL = "https://dps.psx.com.pk/company/{symbol}"
# Matches: <div class="quote__close">Rs.209.02</div>
PRICE_RE = re.compile(r'class="quote__close">\s*Rs\.?([\d,]+\.?\d*)')


def _now_pkt() -> datetime:
    return datetime.now(PKT)


def is_market_open() -> bool:
    now = _now_pkt()
    if now.weekday() >= 5:      # Saturday / Sunday
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


def _fetch_one(symbol: str) -> tuple[str, float | None]:
    try:
        url = BASE_URL.format(symbol=symbol)
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        m = PRICE_RE.search(resp.text)
        if m:
            return symbol, float(m.group(1).replace(",", ""))
    except Exception:
        pass
    return symbol, None


def _fetch_all(symbols: list[str]) -> dict[str, float]:
    prices: dict[str, float] = {}
    with ThreadPoolExecutor(max_workers=min(20, len(symbols))) as pool:
        futures = {pool.submit(_fetch_one, sym): sym for sym in symbols}
        for future in as_completed(futures):
            sym, price = future.result()
            if price is not None:
                prices[sym] = price
    return prices


def get_prices(db, symbols: list[str]) -> dict[str, float]:
    """Return symbol → price, using cache when appropriate."""
    cached_data = db.get_cached_prices()
    cached_prices = {sym: d["price"] for sym, d in cached_data.items()}

    if should_use_cache(db):
        return {sym: cached_prices[sym] for sym in symbols if sym in cached_prices}

    fresh = _fetch_all(symbols)

    if fresh:
        market_date = _now_pkt().strftime("%Y-%m-%d")
        db.update_price_cache(fresh, market_date)

    # Prefer fresh; fall back to cache for any symbol that failed
    result: dict[str, float] = {}
    for sym in symbols:
        if sym in fresh:
            result[sym] = fresh[sym]
        elif sym in cached_prices:
            result[sym] = cached_prices[sym]

    return result
