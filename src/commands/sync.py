"""sync command — fetch broker emails and sync trades to SQLite."""
import logging
import os
import sys

import click

from helpers import _load_config, console, get_db


@click.command()
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
