"""fetch command — refresh index values and stock prices during market hours."""
from datetime import datetime

import click
import pytz

from helpers import console, get_db
from price_fetcher import fetch_indices, _fetch_all

PKT = pytz.timezone("Asia/Karachi")


@click.command()
@click.option("--quiet", "-q", is_flag=True, help="Suppress output (for cron use)")
def fetch(quiet: bool):
    """Fetch live index values and portfolio stock prices for historical tracking."""
    db = get_db()
    now_pkt = datetime.now(PKT)
    today_str = now_pkt.strftime("%Y-%m-%d")

    # ── Index values ──────────────────────────────────────────────────────────
    indices = fetch_indices()
    if indices:
        db.add_index_values("KSE100", {today_str: indices["KSE100"]["value"]}) if "KSE100" in indices else None
        db.add_index_values("KMI30",  {today_str: indices["KMI30"]["value"]})  if "KMI30"  in indices else None
        if not quiet:
            for name, data in indices.items():
                console.print(f"  {name:8s} {data['value']:>10,.2f}  {data['change_pct']}")
    elif not quiet:
        console.print("[yellow]Could not fetch index values.[/yellow]")

    # ── Stock prices ──────────────────────────────────────────────────────────
    trades = db.get_all_trades()
    symbols = list({t["symbol"] for t in trades if t["symbol"]})

    if symbols:
        prices, ldcps = _fetch_all(symbols)
        if prices:
            db.update_price_cache(prices, ldcps, today_str)
            if not quiet:
                console.print(f"  Updated prices for {len(prices)}/{len(symbols)} symbol(s)")
        elif not quiet:
            console.print("[yellow]Could not fetch stock prices.[/yellow]")

    if not quiet:
        console.print(f"[dim]{now_pkt.strftime('%Y-%m-%d %H:%M PKT')}[/dim]")
