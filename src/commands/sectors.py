"""sectors command — portfolio aggregated by sector."""
from datetime import date

import click
from rich import box
from rich.table import Table

from helpers import _load_sectors, console, get_db
from portfolio import compute_positions, xirr as _xirr
from price_fetcher import get_prices

SORT_KEYS = {
    "value": lambda s, _tmv: s["market_value"],
    "pct":   lambda s,  tmv: s["market_value"] / tmv if tmv else 0,
    "name":  lambda s, _tmv: s["name"],
    "abs":   lambda s, _tmv: s["abs_ret"],
    "cagr":  lambda s, _tmv: s["cagr"],
    "xirr":  lambda s, _tmv: s["xirr"],
}


@click.command()
@click.option(
    "--sort", "-s",
    default="value",
    type=click.Choice(list(SORT_KEYS)),
    show_default=True,
    help="Sort sectors by: value, pct, name, abs, cagr, xirr",
)
@click.option("--cagr",     "show_cagr",   is_flag=True, default=False, help="Show CAGR column")
@click.option("--pct-cost", "pct_by_cost", is_flag=True, default=False, help="Show Port % by cost instead of market value")
def sectors(sort: str, show_cagr: bool, pct_by_cost: bool):
    """Show portfolio allocation aggregated by sector."""
    db = get_db()
    trades = db.get_all_trades()

    if not trades:
        console.print("[yellow]No trades found.[/yellow]")
        return

    sector_map = _load_sectors()
    db_sectors = db.get_symbol_sectors()  # scraped from PSX pages

    if not sector_map and not db_sectors:
        console.print("[yellow]No sector data available. Run ./psx fetch to populate from PSX.[/yellow]")
        return

    symbols = list({t["symbol"] for t in trades})
    with console.status("Fetching prices…"):
        prices, ldcps = get_prices(db, symbols)

    pos_list = compute_positions(trades, prices)
    if not pos_list:
        console.print("No open positions.")
        return

    # Build symbol → sector mapping
    # Priority: PSX-scraped sectors > sectors.yaml > "OTHER"
    symbol_to_sector: dict[str, str] = {}
    for sector, syms in sector_map.items():
        for sym in (syms or []):
            symbol_to_sector[sym] = sector
    symbol_to_sector.update(db_sectors)  # PSX names win

    # Aggregate positions by sector
    agg: dict[str, dict] = {}
    for pos in pos_list:
        sector = symbol_to_sector.get(pos.symbol, "OTHER")
        if sector not in agg:
            agg[sector] = {"name": sector, "holdings": 0, "cost": 0.0,
                           "market_value": 0.0, "day_pnl": 0.0, "flows": []}
        ldcp = ldcps.get(pos.symbol, pos.current_price)
        agg[sector]["holdings"]    += 1
        agg[sector]["cost"]        += pos.cost_basis
        agg[sector]["market_value"] += pos.market_value
        agg[sector]["day_pnl"]     += pos.shares * (pos.current_price - ldcp)

    # Collect trade cash flows per sector for XIRR/CAGR
    for t in trades:
        sector = symbol_to_sector.get(t["symbol"], "OTHER")
        if sector not in agg:
            continue
        amt  = t["shares"] * t["trade_price"]
        flow = -amt if t["mode"] == "BUY" else +amt
        agg[sector]["flows"].append((date.fromisoformat(t["date"]), flow))

    # Compute derived metrics per sector
    today = date.today()
    for data in agg.values():
        cost, mv = data["cost"], data["market_value"]
        data["abs_ret"] = (mv - cost) / cost * 100 if cost else 0.0

        flows = sorted(data["flows"], key=lambda f: f[0])
        if flows:
            years = (today - flows[0][0]).days / 365.25
            data["cagr"] = ((mv / cost) ** (1 / years) - 1) * 100 if years > 0 and cost > 0 else 0.0
            data["xirr"] = _xirr(flows + [(today, mv)])
        else:
            data["cagr"] = data["xirr"] = 0.0

    sector_list       = list(agg.values())
    total_market_value = sum(s["market_value"] for s in sector_list)
    total_cost         = sum(s["cost"]         for s in sector_list)

    reverse = sort != "name"
    sector_list.sort(key=lambda s: SORT_KEYS[sort](s, total_market_value), reverse=reverse)

    table = Table(title=f"Sector Allocation (sorted by {sort})", box=box.ROUNDED)
    table.add_column("Sector",       style="bold cyan")
    table.add_column("Holdings",     justify="right")
    table.add_column("Cost",         justify="right")
    table.add_column("Market Value", justify="right")
    table.add_column("Port % (cost)" if pct_by_cost else "Port %", justify="right")
    table.add_column("Day P&L",      justify="right")
    table.add_column("Day %",        justify="right")
    table.add_column("Abs Ret",      justify="right")
    if show_cagr:
        table.add_column("CAGR",     justify="right")
    table.add_column("XIRR",         justify="right")

    for s in sector_list:
        mv      = s["market_value"]
        cost    = s["cost"]
        day_pnl = s["day_pnl"]
        day_pct = day_pnl / (mv - day_pnl) * 100 if (mv - day_pnl) else 0.0
        tot_color = "green" if s["abs_ret"] >= 0 else "red"
        day_color = "green" if day_pnl >= 0 else "red"
        port_pct = (
            f"{cost / total_cost * 100:.1f}%" if (pct_by_cost and total_cost)
            else (f"{mv / total_market_value * 100:.1f}%" if total_market_value else "—")
        )
        row = [
            s["name"][:24],
            str(s["holdings"]),
            f"Rs {cost:>12,.0f}",
            f"Rs {mv:>12,.0f}",
            port_pct,
            f"[{day_color}]Rs {day_pnl:>10,.0f}[/{day_color}]",
            f"[{day_color}]{day_pct:+.2f}%[/{day_color}]",
            f"[{tot_color}]{s['abs_ret']:+.1f}%[/{tot_color}]",
        ]
        if show_cagr:
            row.append(f"[{tot_color}]{s['cagr']:+.1f}%[/{tot_color}]")
        row.append(f"[{tot_color}]{s['xirr']:+.1f}%[/{tot_color}]")
        table.add_row(*row)

    console.print(table)
