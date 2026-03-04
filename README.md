# PSX Portfolio Tracker

A local CLI tool for tracking a Pakistani stock exchange (PSX) portfolio. Automatically syncs trading confirmations from broker emails, stores everything in a local SQLite database, and provides portfolio analytics with live prices.

## Features

- Fetches daily confirmation emails from Gmail (Next Capital broker)
- Extracts transactions from PDF attachments, calculates net price per share
- Stores trades, dividends, and deposits in a local SQLite database
- Live prices scraped from dps.psx.com.pk (cached after market close)
- Portfolio dashboard with P&L, CAGR, XIRR, cash balance, and sector allocation
- Shariah compliance view — debt ratio and dividend purification amounts
- Terminal charts for NLV history and cumulative deposits vs KSE100
- Manual entry for dividends and deposits

## Project Structure

```
psx-auto-update/
├── src/
│   ├── cli.py              # Thin CLI entry point
│   ├── helpers.py          # Shared utilities (DB, config, Shariah helpers)
│   ├── commands/
│   │   ├── sync.py         # sync command
│   │   ├── dashboard.py    # dashboard command + sector allocation
│   │   ├── positions.py    # positions command
│   │   ├── trades.py       # trades + history commands
│   │   ├── dividends.py    # dividends command
│   │   ├── chart.py        # chart group (nlv, deposits)
│   │   ├── add.py          # add group (dividend, deposit)
│   │   └── import_.py      # import + import-kse commands
│   ├── database.py         # SQLite wrapper
│   ├── price_fetcher.py    # Live price scraping with caching
│   ├── portfolio.py        # P&L and summary calculations
│   ├── gmail_client.py     # Gmail API integration
│   ├── pdf_parser.py       # Broker PDF parsing
│   ├── state_manager.py    # Last-run timestamp tracking
│   └── models.py           # Data models
├── scripts/
│   └── import_from_sheets.py  # One-time migration from Google Sheets
├── config/
│   ├── config.yaml         # API credentials paths, email filters
│   └── sectors.yaml        # Symbol → sector mapping
├── credentials/            # OAuth tokens (gitignored)
├── data/                   # SQLite DB, state file, failed PDFs (gitignored)
├── logs/                   # Rotating logs (gitignored)
├── psx                     # Shell script — run from project root
└── pyproject.toml
```

## Setup

### Prerequisites

- Python 3.10+
- [`uv`](https://github.com/astral-sh/uv) package manager
- Google Cloud project with Gmail API enabled

### 1. Install dependencies

```bash
uv sync
```

### 2. Google API credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Enable the **Gmail API**
3. Create an OAuth 2.0 Desktop credential
4. Download and save to `credentials/gmail_credentials.json`
5. Add your email as a test user on the OAuth consent screen

On first run, a browser window will open for authorization. The token is saved automatically.

### 3. Configure

Edit `config/config.yaml`:

```yaml
gmail:
  sender_email: broker@example.com
  subject_filter: "Confirmation Note"
  credentials_path: credentials/gmail_credentials.json
  token_path: credentials/gmail_token.json

state:
  state_file: data/state.json
  lookback_days: 30
```

Edit `config/sectors.yaml` to map your stock symbols to sectors (used in the dashboard allocation view).

## Usage

All commands are run via the `./psx` script from the project root.

### Sync emails → database

```bash
./psx sync              # fetch new broker emails and write trades to DB
./psx sync --dry-run    # preview without writing
```

### Portfolio dashboard

```bash
./psx dashboard
```

Shows net liquidating value, invested amount, cash balance, total deposits, P&L (absolute, CAGR, XIRR), daily P&L, dividends, and sector allocation with per-sector CAGR and XIRR. Saves a daily portfolio snapshot after market close.

### Current positions

```bash
./psx positions                          # sorted by market value (default)
./psx positions --sort [value|symbol|day|abs|cagr|xirr]
./psx positions --shariah                # add D/A ratio column (AAOIFI compliance)
./psx positions --shariah path/to.pdf    # use a specific Shariah screening PDF
```

Shows each open position with average buy price, current live price, market value, day P&L, unrealized P&L, CAGR, and XIRR. The `--shariah` flag adds a debt-to-assets ratio column — green if below 33.33% (AAOIFI compliant), red if above.

### Trade history

```bash
./psx trades                    # all trades
./psx trades --symbol DGKC      # one symbol
./psx trades --mode BUY         # filter by mode
```

### Symbol history (trades + dividends)

```bash
./psx history DGKC
```

### Dividends

```bash
./psx dividends                          # detail view — all dividends
./psx dividends --symbol EFERT           # filter by symbol
./psx dividends --summary                # one row per symbol with yield on cost
./psx dividends --summary --shariah      # add purification % and amount
```

The `--shariah` flag reads non-compliant income percentages from the KMIALL screening PDF and calculates purification amounts per dividend received. Parsed data is cached in SQLite for 90 days.

### Terminal charts

```bash
./psx chart nlv         # historical NLV, invested amount, and total deposits
./psx chart deposits    # cumulative deposits overlaid with KSE100 index
```

### Manual entries

```bash
# Dividend: symbol  date(YYYY-MM-DD)  after-tax-total  shares
./psx add dividend DGKC 2025-06-30 12500 1000

# Deposit: amount  date  [broker]
./psx add deposit 500000 2025-01-15 --broker NextCapital
```

### One-time migration from Google Sheets

```bash
./psx import --dry-run    # preview what would be imported
./psx import              # write to DB
```

Reads trades and deposits from the Entry tab (columns B–G, J–L) and dividends from the Dividends tab (columns B–G).

### Import historical KSE100 data

```bash
./psx import-kse                            # default: ~/Downloads/Karachi 100 Historical Data.csv
./psx import-kse path/to/kse100.csv        # custom path
```

Downloads historical KSE100 data from Investing.com as CSV, then imports it for use in `chart deposits`.

## Prices

Prices are fetched live from `dps.psx.com.pk` in parallel (one request per symbol). After market close (15:30 PKT, Mon–Fri), the last fetched prices are cached in the database and reused until the next market open.

## Scheduled sync

Add to crontab to sync daily at 16:00 PKT:

```bash
crontab -e
```

```
0 11 * * 1-5 cd /path/to/psx-auto-update && ./psx sync >> logs/cron.log 2>&1
```

(11:00 UTC = 16:00 PKT)

## Troubleshooting

**Authentication error** — delete `credentials/*_token.json` and re-run to re-authorize.

**PDF parsing failures** — failed PDFs are saved to `data/failed_pdfs/` for manual review.

**No emails found** — check `gmail.sender_email` and `gmail.subject_filter` in `config.yaml`, and verify `data/state.json` has the expected `last_run` timestamp.

**Stale prices** — delete the `price_cache` rows in `data/portfolio.db` to force a fresh fetch:
```bash
sqlite3 data/portfolio.db "DELETE FROM price_cache;"
```

**Shariah PDF not found** — place the KMIALL screening PDF in the project root or pass its path explicitly via `--shariah path/to/file.pdf`. Cached data can be cleared with:
```bash
sqlite3 data/portfolio.db "DELETE FROM shariah_cache;"
```
