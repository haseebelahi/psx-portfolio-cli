# PSX Email-to-Sheets Automation

Automates processing of daily stock trading confirmations from Next Capital broker (PSX) into Google Sheets tracking.

## Features

- Fetches daily confirmation emails from Gmail
- Extracts transaction data from PDF attachments
- Calculates net price per share (after taxes, brokerage, and fees)
- Automatically appends to Google Sheets
- Prevents duplicate entries
- Tracks state between runs
- Comprehensive logging

## Project Structure

```
psx-auto-update/
├── src/                     # Source code
│   ├── main.py             # Main orchestration script
│   ├── gmail_client.py     # Gmail API integration
│   ├── pdf_parser.py       # PDF parsing with pdfplumber
│   ├── sheets_client.py    # Google Sheets API integration
│   ├── state_manager.py    # State tracking
│   └── models.py           # Data models
├── config/
│   └── config.yaml         # Configuration file
├── credentials/            # API credentials (gitignored)
│   ├── gmail_credentials.json
│   ├── sheets_credentials.json
│   └── *_token.json        # Auto-generated tokens
├── data/                   # State and failed PDFs (gitignored)
│   ├── state.json
│   └── failed_pdfs/
├── logs/                   # Application logs (gitignored)
│   └── psx_automation.log
├── pyproject.toml          # Project dependencies
└── README.md
```

## Setup

### Prerequisites

- Python 3.10 or higher
- `uv` package manager (recommended) or `pip`
- Google Cloud account with Gmail and Sheets API access

### 1. Install Dependencies

Using `uv` (recommended):
```bash
cd /Users/haseebelahi/personal/psx-auto-update
uv sync
```

Using pip:
```bash
cd /Users/haseebelahi/personal/psx-auto-update
pip install -e .
```

### 2. Google API Setup

#### Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project: "PSX Email Automation"
3. Enable Gmail API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Gmail API" and enable it
4. Create OAuth credentials:
   - Go to "APIs & Services" > "Credentials"
   - Configure OAuth consent screen (External)
   - Add your email as a test user
   - Add scope: `https://www.googleapis.com/auth/gmail.readonly`
   - Create credentials > OAuth 2.0 Client ID
   - Application type: Desktop app
5. Download JSON and save as `credentials/gmail_credentials.json`

#### Google Sheets API

1. In the same project, enable Google Sheets API
2. Create OAuth credentials (or reuse Gmail credentials)
3. Add scope: `https://www.googleapis.com/auth/spreadsheets`
4. Download JSON and save as `credentials/sheets_credentials.json`
5. Share your Google Sheet with the email from the credentials file (Editor permission)
   - Sheet URL: https://docs.google.com/spreadsheets/d/1SEbkKKooBganzymX9WayuqqEJwUefDi-MZ72UoWlqIM

### 3. First Run Authentication

On the first run, the script will open a browser window for OAuth authentication:

```bash
cd /Users/haseebelahi/personal/psx-auto-update
uv run python src/main.py
```

- Authorize both Gmail and Sheets access
- Tokens will be saved automatically for future runs

## Usage

### Dry Run (Test Mode)

Test the script without writing to Google Sheets:

```bash
cd /Users/haseebelahi/personal/psx-auto-update
uv run python src/main.py --dry-run
```

This will:
- ✅ Authenticate with Gmail and Sheets
- ✅ Fetch and parse emails
- ✅ Extract transactions from PDFs
- ✅ Check for duplicates
- ✅ Show exactly what would be written
- ❌ NOT write to Google Sheets
- ❌ NOT update state file

Perfect for testing before your first real run!

### Normal Run

```bash
cd /Users/haseebelahi/personal/psx-auto-update
uv run python src/main.py
```

### Scheduled Run (Daily at 6 PM)

Add to crontab:

```bash
crontab -e
```

Add this line:
```
0 18 * * * cd /Users/haseebelahi/personal/psx-auto-update && /Users/haseebelahi/.local/bin/uv run python src/main.py >> /Users/haseebelahi/personal/psx-auto-update/logs/cron.log 2>&1
```

Note: Adjust the `uv` path if installed in a different location. Find it with: `which uv`

## Configuration

Edit `config/config.yaml` to customize:

- Email filters (sender, subject)
- Google Sheets ID and tab name
- Lookback period (default: 7 days)
- Logging settings

## How It Works

1. **Fetch Emails**: Queries Gmail for emails from broker since last run
2. **Download PDFs**: Downloads all PDF attachments from matching emails
3. **Parse Transactions**: Extracts transaction data (symbol, date, mode, shares, price)
4. **Filter Duplicates**: Checks Google Sheets for existing dates
5. **Sort by Date**: Orders transactions in ascending order (oldest first)
6. **Append Data**: Adds new transactions to the sheet
7. **Update State**: Saves timestamp for next run

### PDF Structure Expected

- Trade Date: `DD-MMM-YYYY` format
- Mode indicators: "SOLD FOR YOU AS FOLLOWS" or "PURCHASED FOR YOU AS FOLLOWS"
- Table with columns: Shares Quantity, Symbol, Net Amount Rs.
- Net price per share is automatically calculated from Net Amount ÷ Shares

### Google Sheets Format

The sheet should have a table with these columns:

| Column | Name | Format | Notes |
|--------|------|--------|-------|
| A | Trade Entries >>> | Text | Header label (not modified) |
| B | Symbol | Text | Stock symbol (e.g., DGKC) |
| C | Date | Date | Transaction date |
| D | Mode | BUY/SELL | Buy or Sell |
| E | Shares | Number | Number of shares |
| F | After Tax DPS | Number | Left empty by script |
| G | Trade Price | Price | Net price per share |

**Important Notes:**
- Column A is not modified (contains "Trade Entries >>>" label)
- Data is inserted into columns B-G
- The script finds the first empty row and inserts data there
- Never overwrites existing data
- **Transactions are sorted by date in ascending order** (oldest first)
- Date format: Script outputs YYYY-MM-DD (Google Sheets will format based on your settings)
- Mode: Outputs "BUY" or "SELL" in all caps
- Trade Price: Net price per share (after all taxes, brokerage, and fees)
- After Tax DPS column (F) is left empty by the script

## Troubleshooting

### Authentication Issues

- Delete token files in `credentials/` and re-run to re-authenticate
- Ensure credentials files have correct permissions

### PDF Parsing Failures

- Check `data/failed_pdfs/` for PDFs that couldn't be parsed
- Review logs at `logs/psx_automation.log` for error details

### No Emails Found

- Verify email filters in config.yaml
- Check if emails exist in Gmail matching the criteria
- Ensure last_run date in `data/state.json` is correct

### API Rate Limits

- Gmail: 250 quota units/day
- Sheets: 100 requests/100 seconds
- Script uses batch operations to minimize API calls

## Logging

Logs are written to `logs/psx_automation.log` with automatic rotation:

- Max size: 10MB per file
- Keeps 5 backup files
- Log level: INFO (configurable)

View recent logs:
```bash
tail -f logs/psx_automation.log
```

## Security

- Never commit `credentials/` directory (included in .gitignore)
- Tokens are stored locally and auto-refresh
- APIs use OAuth2 with read-only Gmail access

## Development

To modify the code:

1. Make changes to files in `src/`
2. Test with: `uv run python src/main.py`
3. Check logs for errors
4. Verify data in Google Sheets

