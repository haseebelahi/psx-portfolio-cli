"""add command group — manual entry of dividends and deposits."""
import click

from helpers import console, get_db
from models import Deposit, Dividend


@click.group()
def add():
    """Add manual entries (dividend, deposit)."""


@add.command("dividend")
@click.argument("symbol")
@click.argument("date_str", metavar="DATE")
@click.argument("amount", type=float)
@click.argument("shares", type=int)
def add_dividend(symbol, date_str, amount, shares):
    """Add a dividend entry.

    Usage: psx add dividend SYMBOL DATE AMOUNT SHARES

    Example: psx add dividend DGKC 2025-06-30 50000 1000
    """
    per_share = amount / shares if shares else 0.0
    div = Dividend(
        symbol=symbol.upper(),
        date=date_str,
        after_tax_amount=amount,
        shares=shares,
        per_share=per_share,
    )
    get_db().add_dividend(div)
    console.print(
        f"[green]Added dividend: {symbol.upper()} {date_str}  "
        f"Rs {amount:,.0f}  ({shares:,} shares @ Rs {per_share:.4f}/sh)[/green]"
    )


@add.command("deposit")
@click.argument("amount", type=float)
@click.argument("date_str", metavar="DATE")
@click.option("--broker", default="", help="Broker name")
def add_deposit(amount, date_str, broker):
    """Add a cash deposit entry.

    Usage: psx add deposit AMOUNT DATE [--broker X]

    Example: psx add deposit 500000 2025-01-15 --broker NextCapital
    """
    dep = Deposit(amount=amount, date=date_str, broker=broker)
    get_db().add_deposit(dep)
    console.print(f"[green]Added deposit: Rs {amount:,.0f} on {date_str}[/green]")
