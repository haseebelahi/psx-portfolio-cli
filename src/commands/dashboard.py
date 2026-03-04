"""dashboard command — portfolio summary and sector allocation."""
from datetime import date

import click
from rich import box
from rich.panel import Panel
from rich.table import Table

from helpers import _load_sectors, console, get_db
from portfolio import compute_positions, compute_summary
from price_fetcher import fetch_indices, get_prices, is_market_open


@click.command()
def dashboard():
    """Show portfolio dashboard with summary and sector allocation."""
    db = get_db()
    trades = db.get_all_trades()

    if not trades:
        console.print("[yellow]No trades found. Run 'psx sync' or 'psx import' first.[/yellow]")
        return

    dividends = db.get_all_dividends()
    deposits = db.get_all_deposits()
    symbols = list({t["symbol"] for t in trades})

    with console.status("Fetching prices…"):
        prices, ldcps = get_prices(db, symbols)
        indices = fetch_indices()

    # Persist today's index values for historical charting
    today_str = date.today().isoformat()
    for name, data in indices.items():
        db.add_index_values(name, {today_str: data["value"]})

    positions = compute_positions(trades, prices)
    s = compute_summary(trades, dividends, deposits, positions)

    # Save end-of-day portfolio snapshot (once per day, after market close)
    if not is_market_open():
        db.save_portfolio_snapshot(
            date=today_str,
            nlv=s.nlv,
            market_value=s.market_value,
            cash_balance=s.cash_balance,
            invested=s.current_invested,
            total_deposits=s.total_deposits,
        )

    daily_pnl = sum(
        pos.shares * (prices.get(pos.symbol, 0) - ldcps.get(pos.symbol, 0))
        for pos in positions
    )

    today = date.today().strftime("%d %b %Y")
    cc = "green" if s.cash_balance >= 0 else "red"
    pc = "green" if s.pnl         >= 0 else "red"
    dc = "green" if daily_pnl     >= 0 else "red"

    def rs(amount: float, color: str = "white") -> str:
        return f"[{color}]Rs {amount:>13,.0f}[/{color}]"

    def pct(value: float, color: str = "white") -> str:
        return f"[{color}]{value:>+.2f}%[/{color}]"

    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", width=20)
    grid.add_column(justify="right", width=16)
    grid.add_column(justify="right", width=10)

    def idx_row(name: str) -> tuple:
        d = indices.get(name)
        if not d:
            return name, "", ""
        neg = "-" in d["change_pct"]
        color = "red" if neg else "green"
        return (
            name,
            f"{d['value']:>16,.2f}",
            f"[{color}]{d['change_pct']:>8}[/{color}]",
        )

    grid.add_row(f"[bold]{today}[/bold]")
    grid.add_row(*idx_row("KSE100"))
    grid.add_row(*idx_row("KMI30"))
    grid.add_row("")
    grid.add_row("Net Liq. Value",  f"[bold green]Rs {s.nlv:>13,.0f}[/bold green]")
    grid.add_row("Invested",        rs(s.current_invested))
    grid.add_row("Cash Balance",    rs(s.cash_balance, cc))
    grid.add_row("Total Deposits",  rs(s.total_deposits))
    grid.add_row("")
    grid.add_row("Profit / Loss",   rs(s.pnl, pc),         pct(s.absolute_return, pc))
    grid.add_row("CAGR",            "",                     pct(s.annualized_return, pc))
    grid.add_row("XIRR",            "",                     pct(s.xirr_return, pc))
    grid.add_row("")
    day_pct_val = daily_pnl / (s.nlv - daily_pnl) * 100 if s.nlv else 0
    grid.add_row("Day P&L",         rs(daily_pnl, dc),     pct(day_pct_val, dc))
    grid.add_row("")
    grid.add_row("Total Dividends", rs(s.total_dividends), f"[dim]{s.years_invested:.1f} yrs[/dim]")

    console.print(Panel(grid, title="[bold]Portfolio Dashboard[/bold]", border_style="blue", padding=(1, 3)))

    sectors = _load_sectors()
    if sectors and positions:
        _show_sector_allocation(positions, trades, sectors, s.market_value)


def _show_sector_allocation(positions, trades: list[dict], sectors: dict, total_market_value: float):
    from portfolio import xirr as _xirr
    from datetime import date as _date

    symbol_to_sector: dict = {}
    for sector, syms in sectors.items():
        for sym in (syms or []):
            symbol_to_sector[sym] = sector

    # Aggregate per sector
    sector_data: dict = {}
    for pos in positions:
        sector = symbol_to_sector.get(pos.symbol, "OTHER")
        if sector not in sector_data:
            sector_data[sector] = {"value": 0.0, "cost": 0.0}
        sector_data[sector]["value"] += pos.market_value
        sector_data[sector]["cost"]  += pos.cost_basis

    # Compute sector XIRR from trade cash flows
    today = _date.today()
    sector_flows: dict = {}
    for t in trades:
        sector = symbol_to_sector.get(t["symbol"], "OTHER")
        if sector not in sector_data:
            continue
        sector_flows.setdefault(sector, [])
        amt = t["shares"] * t["trade_price"]
        flow = -amt if t["mode"] == "BUY" else +amt
        sector_flows[sector].append((_date.fromisoformat(t["date"]), flow))

    console.print("\n[bold]Sector Allocation[/bold]")
    table = Table(box=box.SIMPLE, show_header=True, padding=(0, 1))
    table.add_column("Sector",   style="cyan", width=16)
    table.add_column("Value",    justify="right", width=14)
    table.add_column("Alloc",    justify="right", width=6)
    table.add_column("Abs Ret",  justify="right", width=8)
    table.add_column("CAGR",     justify="right", width=7)
    table.add_column("XIRR",     justify="right", width=7)
    table.add_column("",         width=20)  # bar

    for sector, data in sorted(sector_data.items(), key=lambda x: x[1]["value"], reverse=True):
        value = data["value"]
        cost  = data["cost"]
        pct   = (value / total_market_value * 100) if total_market_value else 0.0
        abs_r = ((value - cost) / cost * 100) if cost else 0.0

        # CAGR from first trade in sector
        flows = sector_flows.get(sector, [])
        if flows:
            first = min(f[0] for f in flows)
            years = (today - first).days / 365.25
            s_cagr = ((value / cost) ** (1 / years) - 1) * 100 if years > 0 and cost > 0 else 0.0
            xirr_flows = sorted(flows + [(today, value)], key=lambda f: f[0])
            s_xirr = _xirr(xirr_flows)
        else:
            s_cagr = s_xirr = 0.0

        color = "green" if abs_r >= 0 else "red"
        bar   = "█" * max(1, int(pct / 1.5))
        table.add_row(
            sector[:16],
            f"Rs {value:>10,.0f}",
            f"{pct:.1f}%",
            f"[{color}]{abs_r:+.1f}%[/{color}]",
            f"[{color}]{s_cagr:+.1f}%[/{color}]",
            f"[{color}]{s_xirr:+.1f}%[/{color}]",
            f"[blue]{bar}[/blue]",
        )

    console.print(table)
