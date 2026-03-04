# CLAUDE.MD - PSX Auto-Update Project Context

## Project Overview

**PSX Portfolio Tracker** is a local CLI tool for tracking a Pakistani stock exchange (PSX) portfolio. It automatically syncs trading confirmations from broker emails, stores everything in a local SQLite database, and provides portfolio analytics with live prices.

**Purpose**: Eliminates manual data entry by fetching broker confirmation emails, parsing PDF attachments, and providing a full suite of portfolio analytics commands (positions, P&L, CAGR, XIRR, dividends, Shariah compliance, charts).

**Status**: Production-ready, tested, and fully functional.

## Architecture

### Data Flow
```
Gmail → GmailClient → PDF Files → PDFParser → Transaction Objects
→ Database (SQLite) → CLI commands (positions, dashboard, dividends, charts…)
                       ↑
               Live prices (dps.psx.com.pk, cached post-market)
```

### Core Components

| File | Purpose |
|------|---------|
| `src/cli.py` | Thin CLI entry point — registers all command groups |
| `src/helpers.py` | Shared utilities: `console`, `get_db`, `_load_config`, `_load_sectors`, Shariah helpers, `_group_avg_buy` |
| `src/commands/sync.py` | `sync` — fetch broker emails, parse PDFs, write trades to DB |
| `src/commands/dashboard.py` | `dashboard` — NLV, P&L, CAGR, XIRR, sector allocation |
| `src/commands/positions.py` | `positions` — open holdings with live prices, day P&L, Shariah D/A ratio |
| `src/commands/trades.py` | `trades`, `history` — trade history and per-symbol event timeline |
| `src/commands/dividends.py` | `dividends` — detail/summary views with Shariah purification |
| `src/commands/chart.py` | `chart nlv`, `chart deposits` — terminal charts via plotext |
| `src/commands/add.py` | `add dividend`, `add deposit` — manual entries |
| `src/commands/import_.py` | `import` (Sheets migration), `import-kse` (KSE100 CSV) |
| `src/database.py` | SQLite wrapper — trades, dividends, deposits, price cache, Shariah cache, index history, portfolio history |
| `src/portfolio.py` | P&L calculations: `compute_positions`, `compute_summary`, `xirr` |
| `src/price_fetcher.py` | Live price scraping from dps.psx.com.pk with post-market caching |
| `src/gmail_client.py` | Gmail API — OAuth2, fetch emails, download PDF attachments |
| `src/pdf_parser.py` | Parse broker PDFs, extract transactions, calculate net price |
| `src/state_manager.py` | Persist last-run timestamp in `data/state.json` |
| `src/models.py` | `Transaction`, `Dividend`, `Deposit` dataclasses |

## Tech Stack

- **Language**: Python 3.10+
- **Package Manager**: `uv`
- **Key Dependencies**:
  - `click` — CLI framework
  - `rich` — terminal output
  - `plotext` — terminal charts
  - `google-api-python-client` — Gmail API
  - `pdfplumber` — PDF parsing
  - `requests` + `beautifulsoup4` — price scraping
  - `PyYAML` — configuration

## Project Structure

```
psx-auto-update/
├── src/
│   ├── cli.py              # Thin entry point (~30 lines)
│   ├── helpers.py          # Shared utilities
│   ├── commands/
│   │   ├── __init__.py
│   │   ├── sync.py
│   │   ├── dashboard.py
│   │   ├── positions.py
│   │   ├── trades.py
│   │   ├── dividends.py
│   │   ├── chart.py
│   │   ├── add.py
│   │   └── import_.py
│   ├── database.py
│   ├── portfolio.py
│   ├── price_fetcher.py
│   ├── gmail_client.py
│   ├── pdf_parser.py
│   ├── state_manager.py
│   └── models.py
├── scripts/
│   ├── import_from_sheets.py   # One-time migration from Google Sheets
│   └── shariah_check.py
├── config/
│   ├── config.yaml             # Gmail credentials paths, email filters
│   └── sectors.yaml            # Symbol → sector mapping
├── credentials/                # OAuth tokens (gitignored)
├── data/                       # SQLite DB, state file, failed PDFs (gitignored)
├── logs/                       # Rotating logs (gitignored)
├── psx                         # Shell wrapper — use from project root
└── pyproject.toml
```

## Common Commands

```bash
./psx sync                          # fetch emails → parse PDFs → write trades to DB
./psx sync --dry-run                # preview without writing

./psx dashboard                     # NLV, P&L, CAGR, XIRR, sector allocation
./psx positions                     # open positions sorted by market value
./psx positions --sort xirr         # sort by: value, symbol, day, abs, cagr, xirr
./psx positions --shariah           # add D/A ratio column (AAOIFI compliance)

./psx trades                        # all trades
./psx trades --symbol DGKC --mode BUY
./psx history DGKC                  # trades + dividends for a symbol

./psx dividends                     # dividend detail view
./psx dividends --summary           # one row per symbol, yield on cost
./psx dividends --summary --shariah # add purification % and amounts

./psx chart nlv                     # NLV / invested / deposits over time
./psx chart deposits                # cumulative deposits vs KSE100

./psx add dividend DGKC 2025-06-30 12500 1000
./psx add deposit 500000 2025-01-15 --broker NextCapital

./psx import --dry-run              # preview Google Sheets migration
./psx import
./psx import-kse                    # import KSE100 CSV from ~/Downloads
```

## Database Schema

Key tables in `data/portfolio.db`:

| Table | Purpose |
|-------|---------|
| `trades` | All buy/sell transactions |
| `dividends` | Dividend payments |
| `deposits` | Cash deposits |
| `price_cache` | Last price + LDCP per symbol, invalidated at market open |
| `shariah_cache` | Debt ratio + income % per ticker, 90-day TTL |
| `index_history` | KSE100 / KMI30 daily values |
| `portfolio_history` | Daily NLV snapshots (saved post-market close) |

## Important Notes for AI Assistants

1. **Net Price Calculation**: `Net Amount ÷ Shares` — includes all brokerage fees, taxes, and charges.

2. **Modular structure**: All commands live in `src/commands/`. Shared state (`console`, `get_db`, helpers) lives in `src/helpers.py`. `src/cli.py` only registers commands.

3. **Price caching**: Prices are fetched live during market hours (Mon–Fri, before 15:30 PKT). After close, they're cached in `price_cache` and reused until next open. LDCP (last day closing price) is stored alongside the current price for day P&L calculations.

4. **Shariah data**: Parsed from a KMIALL PDF (pdfplumber) and cached in `shariah_cache` for 90 days. Default PDF path: `Merged_KMIALL_Notice_and_FinalList_June2025.pdf` in project root. Pass `--shariah path/to.pdf` to override.

5. **XIRR**: Implemented in `portfolio.py` using Newton's method on irregular cash flows. Used for both per-position and per-sector analytics.

6. **Portfolio snapshots**: `dashboard` saves a daily NLV snapshot to `portfolio_history` after market close (used by `chart nlv`).

7. **State file**: `data/state.json` tracks `last_run` timestamp. Always updated after `sync` to prevent re-processing emails.

8. **Dry-run mode**: `sync --dry-run` previews without writing to DB or updating state.

9. **Failed PDFs**: Saved to `data/failed_pdfs/` rather than stopping execution.

## Version Information

- **Python**: 3.10+
- **Status**: Production-ready
- **Last Updated**: 2026-03-04
- **License**: Private/personal project
