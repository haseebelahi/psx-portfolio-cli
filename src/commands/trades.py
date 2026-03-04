"""trades and history commands."""
import click
from rich import box
from rich.table import Table

from helpers import console, get_db


@click.command()
@click.option("--symbol", "-s", default=None, help="Filter by symbol")
@click.option("--mode", "-m", default=None, type=click.Choice(["BUY", "SELL"]), help="Filter by mode")
def trades(symbol, mode):
    """Show trade history."""
    db = get_db()
    all_trades = db.get_all_trades()

    if symbol:
        all_trades = [t for t in all_trades if t["symbol"].upper() == symbol.upper()]
    if mode:
        all_trades = [t for t in all_trades if t["mode"] == mode]

    if not all_trades:
        console.print("No trades found.")
        return

    table = Table(title="Trade History", box=box.ROUNDED)
    table.add_column("Date")
    table.add_column("Symbol", style="bold cyan")
    table.add_column("Mode")
    table.add_column("Shares", justify="right")
    table.add_column("Price", justify="right")
    table.add_column("Total", justify="right")

    for t in all_trades:
        mode_str = "[green]BUY[/green]" if t["mode"] == "BUY" else "[red]SELL[/red]"
        total = t["shares"] * t["trade_price"]
        table.add_row(
            t["date"],
            t["symbol"],
            mode_str,
            f"{t['shares']:,}",
            f"Rs {t['trade_price']:.4f}",
            f"Rs {total:>12,.0f}",
        )

    console.print(table)


@click.command()
@click.argument("symbol")
def history(symbol):
    """Show combined trades + dividends for a single symbol."""
    db = get_db()
    sym = symbol.upper()

    sym_trades = [t for t in db.get_all_trades() if t["symbol"] == sym]
    sym_divs = [d for d in db.get_all_dividends() if d["symbol"] == sym]

    if not sym_trades and not sym_divs:
        console.print(f"No history found for [bold]{sym}[/bold].")
        return

    events = []
    for t in sym_trades:
        events.append(("trade", t["date"], t))
    for d in sym_divs:
        events.append(("dividend", d["date"], d))
    events.sort(key=lambda e: e[1])

    table = Table(title=f"History: {sym}", box=box.ROUNDED)
    table.add_column("Date")
    table.add_column("Type")
    table.add_column("Details", style="dim")
    table.add_column("Amount", justify="right")

    for evt_type, evt_date, data in events:
        if evt_type == "trade":
            type_str = "[green]BUY[/green]" if data["mode"] == "BUY" else "[red]SELL[/red]"
            details = f"{data['shares']:,} shares @ Rs {data['trade_price']:.4f}"
            amount = f"Rs {data['shares'] * data['trade_price']:>12,.0f}"
        else:
            type_str = "[yellow]DIV[/yellow]"
            details = f"{data['shares']:,} shares @ Rs {data['per_share']:.4f}/sh"
            amount = f"Rs {data['after_tax_amount']:>12,.0f}"

        table.add_row(evt_date, type_str, details, amount)

    console.print(table)
