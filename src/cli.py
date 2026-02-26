"""PSX Portfolio Tracker CLI."""
import logging
import os
import subprocess
import sys
from datetime import date

import click
import yaml
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Allow imports from src/ when run as `python src/cli.py`
sys.path.insert(0, os.path.dirname(__file__))

from database import Database
from models import Deposit, Dividend
from portfolio import compute_positions, compute_summary
from price_fetcher import get_prices

console = Console()
DB_PATH = "data/portfolio.db"


def get_db() -> Database:
    return Database(DB_PATH)


def _load_config() -> dict:
    with open("config/config.yaml") as f:
        return yaml.safe_load(f)


def _load_sectors() -> dict:
    try:
        with open("config/sectors.yaml") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        return {}


# ── CLI group ─────────────────────────────────────────────────────────────────

@click.group()
def cli():
    """PSX Portfolio Tracker — manage trades, positions, and analytics."""


# ── sync ──────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--dry-run", "-d", is_flag=True, help="Preview without writing to DB")
def sync(dry_run: bool):
    """Fetch broker confirmation emails and sync trades to SQLite."""
    from gmail_client import GmailClient
    from pdf_parser import PDFParser
    from state_manager import StateManager
    from datetime import datetime

    config = _load_config()

    logger = logging.getLogger("psx_sync")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))
        logger.addHandler(h)

    db = get_db()
    gmail = GmailClient(config["gmail"]["credentials_path"], config["gmail"]["token_path"])
    parser = PDFParser()
    state_mgr = StateManager(config["state"]["state_file"])

    last_run = state_mgr.get_last_run_date(config["state"]["lookback_days"])
    console.print(f"Checking emails since: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")

    emails = gmail.get_emails_since(
        sender=config["gmail"]["sender_email"],
        subject=config["gmail"]["subject_filter"],
        since_date=last_run,
    )
    console.print(f"Found {len(emails)} email(s)")

    all_transactions = []
    failed_dir = "data/failed_pdfs"
    for email in emails:
        for att in gmail.list_attachments(email["id"]):
            if not att["filename"].lower().endswith(".pdf"):
                continue
            try:
                pdf_bytes = gmail.get_attachment(email["id"], att["id"])
                txns = parser.parse_pdf(pdf_bytes)
                all_transactions.extend(txns)
                console.print(f"  {att['filename']}: {len(txns)} transaction(s)")
            except Exception as exc:
                console.print(f"  [red]Failed to parse {att['filename']}: {exc}[/red]")
                os.makedirs(failed_dir, exist_ok=True)
                with open(os.path.join(failed_dir, att["filename"]), "wb") as fh:
                    fh.write(pdf_bytes)

    if not all_transactions:
        console.print("No transactions found.")
        if not dry_run:
            state_mgr.update_last_run_date(datetime.now())
        return

    existing_dates = db.get_existing_dates()
    new_txns = [t for t in all_transactions if t.date.date() not in existing_dates]
    dupes = len(all_transactions) - len(new_txns)
    if dupes:
        console.print(f"Filtered {dupes} duplicate(s)")

    new_txns.sort(key=lambda t: t.date)

    if dry_run:
        console.print(f"\n[yellow]DRY RUN — would add {len(new_txns)} transaction(s):[/yellow]")
        for t in new_txns:
            console.print(f"  {t.mode}: {t.symbol} ×{t.shares} @ Rs {t.trade_price:.4f}")
        return

    for t in new_txns:
        db.add_trade(t)
    state_mgr.update_last_run_date(datetime.now(), len(new_txns))
    console.print(f"[green]Added {len(new_txns)} transaction(s) to database.[/green]")


# ── dashboard ─────────────────────────────────────────────────────────────────

@cli.command()
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
        prices = get_prices(db, symbols)

    positions = compute_positions(trades, prices)
    s = compute_summary(trades, dividends, deposits, positions)

    today = date.today().strftime("%d %b %Y")
    cash_color = "green" if s.cash_balance >= 0 else "red"
    pnl_color = "green" if s.pnl >= 0 else "red"

    lines = [
        f"Last Updated: {today}",
        f"Cash Balance:  [{cash_color}]Rs {s.cash_balance:>14,.0f}[/{cash_color}]",
        "",
        "Net Liquidating Value",
        f"               [bold green]Rs {s.nlv:>14,.0f}[/bold green]",
        "Current Invested Amount",
        f"               Rs {s.current_invested:>14,.0f}",
        f"Total Deposits Rs {s.total_deposits:>14,.0f}",
        "",
        f"Profit / Loss  [{pnl_color}]Rs {s.pnl:>14,.0f}[/{pnl_color}]",
        f"Absolute Ret       {s.absolute_return:>8.2f}%",
        f"Annualized Ret     {s.annualized_return:>8.2f}%",
        "",
        f"Total Dividends  Rs {s.total_dividends:>12,.0f}",
        f"Since: {s.years_invested:.1f} years",
    ]

    console.print(Panel("\n".join(lines), title="[bold]Portfolio Dashboard[/bold]", border_style="blue"))

    sectors = _load_sectors()
    if sectors and positions:
        _show_sector_allocation(positions, sectors, s.market_value)


def _show_sector_allocation(positions, sectors: dict, total_market_value: float):
    symbol_to_sector: dict = {}
    for sector, symbols in sectors.items():
        for sym in (symbols or []):
            symbol_to_sector[sym] = sector

    sector_values: dict = {}
    for pos in positions:
        sector = symbol_to_sector.get(pos.symbol, "OTHER")
        sector_values[sector] = sector_values.get(sector, 0.0) + pos.market_value

    console.print("\n[bold]Sector Allocation[/bold]")
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 1))
    table.add_column("Sector", style="cyan", width=16)
    table.add_column("Value", justify="right", width=16)
    table.add_column("Pct", justify="right", width=7)
    table.add_column("Bar")

    for sector, value in sorted(sector_values.items(), key=lambda x: x[1], reverse=True):
        pct = (value / total_market_value * 100) if total_market_value else 0.0
        bar = "█" * max(1, int(pct / 1.5))
        color = "green" if pct >= 10 else "yellow"
        table.add_row(
            sector[:16],
            f"Rs {value:>12,.0f}",
            f"[{color}]{pct:.1f}%[/{color}]",
            f"[blue]{bar}[/blue]",
        )

    console.print(table)


# ── positions ─────────────────────────────────────────────────────────────────

@cli.command()
def positions():
    """Show current holdings with unrealized P&L."""
    db = get_db()
    trades = db.get_all_trades()

    if not trades:
        console.print("[yellow]No trades found.[/yellow]")
        return

    symbols = list({t["symbol"] for t in trades})
    with console.status("Fetching prices…"):
        prices = get_prices(db, symbols)

    pos_list = compute_positions(trades, prices)
    if not pos_list:
        console.print("No open positions.")
        return

    table = Table(title="Current Positions", box=box.ROUNDED)
    table.add_column("Symbol", style="bold cyan")
    table.add_column("Shares", justify="right")
    table.add_column("Avg Buy", justify="right")
    table.add_column("Current", justify="right")
    table.add_column("Market Value", justify="right")
    table.add_column("Unreal. P&L", justify="right")
    table.add_column("P&L %", justify="right")

    for pos in pos_list:
        color = "green" if pos.unrealized_pnl >= 0 else "red"
        table.add_row(
            pos.symbol,
            f"{pos.shares:,}",
            f"Rs {pos.avg_buy_price:.2f}",
            f"Rs {pos.current_price:.2f}",
            f"Rs {pos.market_value:>12,.0f}",
            f"[{color}]Rs {pos.unrealized_pnl:>12,.0f}[/{color}]",
            f"[{color}]{pos.unrealized_pnl_pct:+.1f}%[/{color}]",
        )

    console.print(table)


# ── trades ────────────────────────────────────────────────────────────────────

@cli.command()
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


# ── history ───────────────────────────────────────────────────────────────────

@cli.command()
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


# ── dividends ─────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--symbol", "-s", default=None, help="Filter by symbol")
def dividends(symbol):
    """Show dividend history and totals."""
    db = get_db()
    all_divs = db.get_all_dividends()

    if symbol:
        all_divs = [d for d in all_divs if d["symbol"].upper() == symbol.upper()]

    if not all_divs:
        console.print("No dividends found.")
        return

    table = Table(title="Dividend History", box=box.ROUNDED)
    table.add_column("Date")
    table.add_column("Symbol", style="bold cyan")
    table.add_column("Shares", justify="right")
    table.add_column("Per Share", justify="right")
    table.add_column("After-Tax Total", justify="right")

    total = 0.0
    for d in all_divs:
        table.add_row(
            d["date"],
            d["symbol"],
            f"{d['shares']:,}",
            f"Rs {d['per_share']:.4f}",
            f"Rs {d['after_tax_amount']:>12,.0f}",
        )
        total += d["after_tax_amount"]

    console.print(table)
    console.print(f"\nTotal dividends received: [bold green]Rs {total:,.0f}[/bold green]")


# ── add ───────────────────────────────────────────────────────────────────────

@cli.group()
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


# ── import ────────────────────────────────────────────────────────────────────

@cli.command("import")
@click.option("--dry-run", "-d", is_flag=True, help="Preview rows without writing to DB")
def import_from_sheets(dry_run: bool):
    """One-time migration: import trades, dividends, and deposits from Google Sheets."""
    script = os.path.join(os.path.dirname(__file__), "..", "scripts", "import_from_sheets.py")
    script = os.path.normpath(script)
    if not os.path.exists(script):
        console.print(f"[red]Import script not found: {script}[/red]")
        sys.exit(1)

    cmd = ["uv", "run", "python", script]
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    cli()
