"""One-time migration: Google Sheets to SQLite.

Reads from:
  Entry tab      — columns B:G  (Symbol, Date, Mode, Shares, _, Trade Price)
  Entry tab      — columns J:L  (Deposit Amount, Deposit Date, Broker)
  Dividends tab  — columns B:G  (Symbol, After-Tax Amount, Date, Activity, Shares, Per Share)

Writes to data/portfolio.db via Database.
"""
import os
import sys
from datetime import datetime

# Allow import of src modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import gspread
import yaml
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from database import Database
from models import Deposit, Dividend, Transaction

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _authenticate(credentials_path: str, token_path: str):
    creds = None
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())
    return gspread.authorize(creds)


def _parse_float(val) -> float:
    if val is None or val == "":
        return 0.0
    cleaned = str(val).replace(",", "").replace("Rs", "").strip()
    return float(cleaned)


def _parse_int(val) -> int:
    if val is None or val == "":
        return 0
    return int(str(val).replace(",", "").strip())


def _parse_date(val: str) -> str:
    if not val or not val.strip():
        return ""
    from dateutil import parser as dp
    return dp.parse(val.strip(), dayfirst=True).strftime("%Y-%m-%d")


def import_trades(worksheet, db: Database, dry_run: bool = False) -> int:
    """Import trades from columns B:G of the Entry tab."""
    symbols    = worksheet.col_values(2)[1:]   # B
    dates      = worksheet.col_values(3)[1:]   # C
    modes      = worksheet.col_values(4)[1:]   # D
    shares_col = worksheet.col_values(5)[1:]   # E
    prices_col = worksheet.col_values(7)[1:]   # G (column F is skipped/empty)

    count = 0
    for i in range(len(symbols)):
        sym   = symbols[i].strip()   if i < len(symbols)    else ""
        dt    = dates[i].strip()     if i < len(dates)      else ""
        mode  = modes[i].strip()     if i < len(modes)      else ""
        shrs  = shares_col[i]        if i < len(shares_col) else ""
        price = prices_col[i]        if i < len(prices_col) else ""

        if not sym or not dt or mode.upper() not in ("BUY", "SELL"):
            continue

        try:
            date_str = _parse_date(dt)
            t = Transaction(
                symbol=sym.upper(),
                date=datetime.fromisoformat(date_str),
                mode=mode.upper(),
                shares=_parse_int(shrs),
                trade_price=_parse_float(price),
            )
            if dry_run:
                print(f"  [trade]   {t.mode} {t.symbol} ×{t.shares} @ Rs {t.trade_price:.4f}  ({date_str})")
            else:
                db.add_trade(t)
            count += 1
        except Exception as exc:
            print(f"  [trades] Skipping row {i + 2}: {exc}")

    return count


def import_deposits(worksheet, db: Database, dry_run: bool = False) -> int:
    """Import deposits from columns J:L of the Entry tab."""
    amounts  = worksheet.col_values(10)[1:]   # J
    dates    = worksheet.col_values(11)[1:]   # K
    brokers  = worksheet.col_values(12)[1:]   # L

    count = 0
    for i in range(len(amounts)):
        amt    = amounts[i]  if i < len(amounts)  else ""
        dt     = dates[i]    if i < len(dates)    else ""
        broker = brokers[i]  if i < len(brokers)  else ""

        if not amt or not dt:
            continue

        try:
            date_str = _parse_date(str(dt))
            dep = Deposit(
                amount=_parse_float(amt),
                date=date_str,
                broker=str(broker).strip(),
            )
            if dry_run:
                print(f"  [deposit] Rs {dep.amount:,.0f}  {date_str}  {dep.broker}")
            else:
                db.add_deposit(dep)
            count += 1
        except Exception as exc:
            print(f"  [deposits] Skipping row {i + 2}: {exc}")

    return count


def import_dividends(worksheet, db: Database, dry_run: bool = False) -> int:
    """Import dividends from the Dividends tab.

    Layout (headers at row 26, data from row 27):
      B = Symbol, C = After Tax Dividend, D = Date,
      E = Activity, F = Shares, G = Dividend per Share
    """
    symbols = worksheet.col_values(2)   # B
    amounts = worksheet.col_values(3)   # C
    dates   = worksheet.col_values(4)   # D
    shares_c = worksheet.col_values(6)  # F
    per_sh   = worksheet.col_values(7)  # G

    # Find the header row by locating "Symbol" in the symbol column,
    # then start reading from the row after it.
    header_idx = next(
        (i for i, v in enumerate(symbols) if str(v).strip().lower() == "symbol"),
        0,  # fallback: skip only row 1
    )
    start = header_idx + 1

    count = 0
    for i in range(start, len(symbols)):
        sym = symbols[i].strip()  if i < len(symbols)  else ""
        dt  = dates[i].strip()    if i < len(dates)    else ""
        if not sym or not dt:
            continue

        try:
            date_str = _parse_date(dt)
            amt   = _parse_float(amounts[i]  if i < len(amounts)  else 0)
            shrs  = _parse_int(shares_c[i]   if i < len(shares_c) else 0)
            per_s = _parse_float(per_sh[i]   if i < len(per_sh)   else 0)
            if per_s == 0 and shrs > 0:
                per_s = amt / shrs
            div = Dividend(
                symbol=sym.upper(),
                date=date_str,
                after_tax_amount=amt,
                shares=shrs,
                per_share=per_s,
            )
            if dry_run:
                print(f"  [dividend] {div.symbol}  {date_str}  Rs {div.after_tax_amount:,.0f}  ({div.shares:,} shares @ Rs {div.per_share:.4f}/sh)")
            else:
                db.add_dividend(div)
            count += 1
        except Exception as exc:
            print(f"  [dividends] Skipping row {i + 1}: {exc}")

    return count


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Import Google Sheets data into SQLite")
    ap.add_argument("--dry-run", "-d", action="store_true", help="Preview rows without writing to DB")
    args = ap.parse_args()
    dry_run = args.dry_run

    config_path = "config/config.yaml"
    if not os.path.exists(config_path):
        print(f"Config not found: {config_path}")
        sys.exit(1)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    print("Authenticating with Google Sheets…")
    client = _authenticate(
        config["sheets"]["credentials_path"],
        config["sheets"]["token_path"],
    )

    spreadsheet = client.open_by_key(config["sheets"]["spreadsheet_id"])
    db = Database("data/portfolio.db")

    if dry_run:
        print("\n[DRY RUN] No data will be written to the database.\n")

    # ── Entry tab ──────────────────────────────────────────────────────────────
    entry_tab_name = config["sheets"].get("tab_name", "Entry")
    label = "Previewing" if dry_run else "Importing"
    print(f"{label} trades and deposits from '{entry_tab_name}' tab…")
    try:
        entry_ws = spreadsheet.worksheet(entry_tab_name)
        n_trades   = import_trades(entry_ws, db, dry_run)
        n_deposits = import_deposits(entry_ws, db, dry_run)
        print(f"  Trades:   {n_trades}")
        print(f"  Deposits: {n_deposits}")
    except Exception as exc:
        print(f"  Error reading Entry tab: {exc}")

    # ── Dividends tab ─────────────────────────────────────────────────────────
    div_tab_name = config["sheets"].get("dividends_tab_name", "Dividends")
    print(f"\n{label} dividends from '{div_tab_name}' tab…")
    try:
        div_ws = spreadsheet.worksheet(div_tab_name)
        n_divs = import_dividends(div_ws, db, dry_run)
        print(f"  Dividends: {n_divs}")
    except Exception as exc:
        print(f"  Note: Could not read '{div_tab_name}' tab: {exc}")

    if dry_run:
        print("\n[DRY RUN] Nothing written. Re-run without --dry-run to import.")
    else:
        print("\nImport complete. Run 'psx dashboard' to verify.")


if __name__ == "__main__":
    main()
