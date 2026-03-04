"""import and import-kse commands."""
import csv as _csv
import os
import subprocess
import sys

import click

from helpers import console, get_db


@click.command("import")
@click.option("--dry-run", "-d", is_flag=True, help="Preview rows without writing to DB")
def import_from_sheets(dry_run: bool):
    """One-time migration: import trades, dividends, and deposits from Google Sheets."""
    script = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "import_from_sheets.py")
    script = os.path.normpath(script)
    if not os.path.exists(script):
        console.print(f"[red]Import script not found: {script}[/red]")
        sys.exit(1)

    cmd = ["uv", "run", "python", script]
    if dry_run:
        cmd.append("--dry-run")
    result = subprocess.run(cmd)
    sys.exit(result.returncode)


@click.command("import-kse")
@click.argument("csv_path", default="~/Downloads/Karachi 100 Historical Data.csv")
def import_kse_csv(csv_path: str):
    """Import historical KSE100 data from Investing.com CSV into the database."""
    path = os.path.expanduser(csv_path)
    if not os.path.exists(path):
        console.print(f"[red]File not found: {path}[/red]")
        sys.exit(1)

    db = get_db()
    records: dict[str, float] = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in _csv.DictReader(f):
            raw_date  = row.get("Date", "").strip().strip('"')
            raw_price = row.get("Price", "").strip().strip('"').replace(",", "")
            if not raw_date or not raw_price:
                continue
            try:
                # MM/DD/YYYY → YYYY-MM-DD
                m, d, y = raw_date.split("/")
                iso_date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
                records[iso_date] = float(raw_price)
            except (ValueError, AttributeError):
                continue

    if not records:
        console.print("[red]No records parsed — check CSV format.[/red]")
        sys.exit(1)

    db.add_index_values("KSE100", records)
    first, last = min(records), max(records)
    console.print(
        f"[green]Imported {len(records)} KSE100 records "
        f"({first} → {last})[/green]"
    )
