"""positions command — current holdings with unrealized P&L."""
import click
from rich import box
from rich.table import Table

from helpers import _resolve_shariah_pdf, console, get_db
from portfolio import compute_positions
from price_fetcher import get_prices

SORT_KEYS = {
    "value":  lambda p, _ldcps, _tmv: p.market_value,
    "pct":    lambda p, _ldcps,  tmv: p.market_value / tmv if tmv else 0,
    "symbol": lambda p, _ldcps, _tmv: p.symbol,
    "day":    lambda p,  ldcps, _tmv: p.shares * (p.current_price - ldcps.get(p.symbol, p.current_price)),
    "abs":    lambda p, _ldcps, _tmv: p.unrealized_pnl_pct,
    "cagr":   lambda p, _ldcps, _tmv: p.cagr,
    "xirr":   lambda p, _ldcps, _tmv: p.xirr,
}


@click.command()
@click.option(
    "--sort", "-s",
    default="value",
    type=click.Choice(list(SORT_KEYS)),
    show_default=True,
    help="Sort positions by: value, pct, symbol, day, abs, cagr, xirr",
)
@click.option("--shariah",  "show_shariah", is_flag=True, default=False, help="Show D/A Ratio column (uses cached Shariah data)")
@click.option("--cagr",    "show_cagr",    is_flag=True, default=False, help="Show CAGR column")
@click.option("--pct-cost","pct_by_cost",  is_flag=True, default=False, help="Show Port % by cost instead of market value")
def positions(sort: str, show_shariah: bool, show_cagr: bool, pct_by_cost: bool):
    """Show current holdings with unrealized P&L."""
    db = get_db()
    trades = db.get_all_trades()

    if not trades:
        console.print("[yellow]No trades found.[/yellow]")
        return

    symbols = list({t["symbol"] for t in trades})
    with console.status("Fetching prices…"):
        prices, ldcps = get_prices(db, symbols)

    shariah_map = _resolve_shariah_pdf(None) if show_shariah else {}

    pos_list = compute_positions(trades, prices)
    if not pos_list:
        console.print("No open positions.")
        return

    total_market_value = sum(p.market_value for p in pos_list)
    total_cost         = sum(p.cost_basis   for p in pos_list)

    reverse = sort != "symbol"
    pos_list.sort(key=lambda p: SORT_KEYS[sort](p, ldcps, total_market_value), reverse=reverse)

    table = Table(title=f"Current Positions (sorted by {sort})", box=box.ROUNDED)
    table.add_column("Symbol",       style="bold cyan")
    table.add_column("Shares",       justify="right")
    table.add_column("Avg Buy",      justify="right")
    table.add_column("Current",      justify="right")
    table.add_column("Cost",         justify="right")
    table.add_column("Market Value", justify="right")
    table.add_column("Port % (cost)" if pct_by_cost else "Port %", justify="right")
    table.add_column("Day P&L",      justify="right")
    table.add_column("Day %",        justify="right")
    table.add_column("Abs Ret",      justify="right")
    if show_cagr:
        table.add_column("CAGR",     justify="right")
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
            f"Rs {pos.cost_basis:>12,.0f}",
            f"Rs {pos.market_value:>12,.0f}",
            f"{pos.cost_basis / total_cost * 100:.1f}%" if (pct_by_cost and total_cost) else (f"{pos.market_value / total_market_value * 100:.1f}%" if total_market_value else "—"),
            f"[{day_color}]Rs {day_pnl:>10,.0f}[/{day_color}]",
            f"[{day_color}]{day_pct:+.2f}%[/{day_color}]",
            f"[{tot_color}]{pos.unrealized_pnl_pct:+.1f}%[/{tot_color}]",
        ]
        if show_cagr:
            row.append(f"[{tot_color}]{pos.cagr:+.1f}%[/{tot_color}]")
        row.append(f"[{tot_color}]{pos.xirr:+.1f}%[/{tot_color}]")
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
