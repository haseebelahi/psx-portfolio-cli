"""positions command — current holdings with unrealized P&L."""
import click
from rich import box
from rich.table import Table

from helpers import _DEFAULT_SHARIAH_PDF, _resolve_shariah_pdf, console, get_db
from portfolio import compute_positions
from price_fetcher import get_prices

SORT_KEYS = {
    "value":  lambda p, _ldcps: p.market_value,
    "symbol": lambda p, _ldcps: p.symbol,
    "day":    lambda p,  ldcps: p.shares * (p.current_price - ldcps.get(p.symbol, p.current_price)),
    "abs":    lambda p, _ldcps: p.unrealized_pnl_pct,
    "cagr":   lambda p, _ldcps: p.cagr,
    "xirr":   lambda p, _ldcps: p.xirr,
}


@click.command()
@click.option(
    "--sort", "-s",
    default="value",
    type=click.Choice(list(SORT_KEYS)),
    show_default=True,
    help="Sort positions by: value, symbol, day, abs, cagr, xirr",
)
@click.option(
    "--shariah", "shariah_pdf",
    default=None, metavar="PDF",
    help=f"Path to KMIALL screening PDF to show debt ratio (default: {_DEFAULT_SHARIAH_PDF})",
)
def positions(sort: str, shariah_pdf):
    """Show current holdings with unrealized P&L."""
    db = get_db()
    trades = db.get_all_trades()

    if not trades:
        console.print("[yellow]No trades found.[/yellow]")
        return

    symbols = list({t["symbol"] for t in trades})
    with console.status("Fetching prices…"):
        prices, ldcps = get_prices(db, symbols)

    shariah_map = _resolve_shariah_pdf(shariah_pdf)

    pos_list = compute_positions(trades, prices)
    if not pos_list:
        console.print("No open positions.")
        return

    reverse = sort != "symbol"
    pos_list.sort(key=lambda p: SORT_KEYS[sort](p, ldcps), reverse=reverse)

    show_shariah = bool(shariah_map)
    table = Table(title=f"Current Positions (sorted by {sort})", box=box.ROUNDED)
    table.add_column("Symbol",       style="bold cyan")
    table.add_column("Shares",       justify="right")
    table.add_column("Avg Buy",      justify="right")
    table.add_column("Current",      justify="right")
    table.add_column("Market Value", justify="right")
    table.add_column("Day P&L",      justify="right")
    table.add_column("Day %",        justify="right")
    table.add_column("Abs Ret",      justify="right")
    table.add_column("CAGR",         justify="right")
    table.add_column("XIRR",         justify="right")
    if show_shariah:
        table.add_column("D/A Ratio", justify="right")

    for pos in pos_list:
        ldcp      = ldcps.get(pos.symbol, pos.current_price)
        day_pnl   = pos.shares * (pos.current_price - ldcp)
        day_pct   = ((pos.current_price - ldcp) / ldcp * 100) if ldcp else 0.0
        tot_color = "green" if pos.unrealized_pnl >= 0 else "red"
        day_color = "green" if day_pnl >= 0 else "red"
        row = [
            pos.symbol,
            f"{pos.shares:,}",
            f"Rs {pos.avg_buy_price:.2f}",
            f"Rs {pos.current_price:.2f}",
            f"Rs {pos.market_value:>12,.0f}",
            f"[{day_color}]Rs {day_pnl:>10,.0f}[/{day_color}]",
            f"[{day_color}]{day_pct:+.2f}%[/{day_color}]",
            f"[{tot_color}]{pos.unrealized_pnl_pct:+.1f}%[/{tot_color}]",
            f"[{tot_color}]{pos.cagr:+.1f}%[/{tot_color}]",
            f"[{tot_color}]{pos.xirr:+.1f}%[/{tot_color}]",
        ]
        if show_shariah:
            entry = shariah_map.get(pos.symbol, {})
            da = entry.get("debt_ratio")
            if da is not None:
                # AAOIFI standard: D/A must be < 33.33% to remain compliant
                da_color = "red" if da >= 33.33 else "green"
                row.append(f"[{da_color}]{da:.2f}%[/{da_color}]")
            else:
                row.append("[dim]N/A[/dim]")
        table.add_row(*row)

    console.print(table)
    if show_shariah:
        console.print("[dim]D/A Ratio: green < 33.33% (AAOIFI compliant), red ≥ 33.33% (non-compliant)[/dim]")
