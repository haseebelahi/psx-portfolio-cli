# Quick Reference Guide

## Common Commands

### Dry Run (Test Mode - No Writes)
```bash
cd /Users/haseebelahi/personal/psx-auto-update
uv run python src/main.py --dry-run
# or short form:
uv run python src/main.py -d
```

### Run Script Normally (Writes to Sheet)
```bash
cd /Users/haseebelahi/personal/psx-auto-update
uv run python src/main.py
```

### View Recent Logs
```bash
tail -20 logs/psx_automation.log
```

### Follow Logs in Real-Time
```bash
tail -f logs/psx_automation.log
```

### Check State
```bash
cat data/state.json | python -m json.tool
```

### Test PDF Parsing
```bash
uv run python test_pdf_parser.py
```

### List Cron Jobs
```bash
crontab -l
```

### Edit Cron Jobs
```bash
crontab -e
```

### View Cron Output
```bash
tail -f logs/cron.log
```

## File Locations

| File/Directory | Purpose |
|----------------|---------|
| `config/config.yaml` | Configuration settings |
| `credentials/gmail_credentials.json` | Gmail OAuth credentials |
| `credentials/sheets_credentials.json` | Sheets OAuth credentials |
| `credentials/gmail_token.json` | Gmail access token (auto-generated) |
| `credentials/sheets_token.json` | Sheets access token (auto-generated) |
| `data/state.json` | Last run timestamp and stats |
| `data/failed_pdfs/` | PDFs that failed to parse |
| `logs/psx_automation.log` | Main application log |
| `logs/cron.log` | Cron job output |

## Configuration Options

Edit `config/config.yaml`:

### Change Email Filters
```yaml
gmail:
  sender_email: "settlement@nextcapital.com.pk"
  subject_filter: "Daily Confirmations"
```

### Change Sheet/Tab
```yaml
sheets:
  spreadsheet_id: "1SEbkKKooBganzymX9WayuqqEJwUefDi-MZ72UoWlqIM"
  tab_name: "Entry"
```

### Change Lookback Period
```yaml
state:
  lookback_days: 7  # Change to desired number of days
```

### Change Log Level
```yaml
logging:
  log_level: "INFO"  # Options: DEBUG, INFO, WARNING, ERROR
```

## Re-authentication

If you need to re-authenticate:

```bash
cd /Users/haseebelahi/personal/psx-auto-update/credentials
rm gmail_token.json sheets_token.json
cd ..
uv run python src/main.py
```

Browser will open for OAuth flow.

## Reset State (Force Full Sync)

To re-process emails from the last N days:

```bash
cd /Users/haseebelahi/personal/psx-auto-update
rm data/state.json
# Edit config.yaml to set lookback_days if needed
uv run python src/main.py
```

Note: This won't create duplicates due to date-based deduplication.

## Check for New Emails Without Processing

Currently not supported, but you can check Gmail manually:
- From: settlement@nextcapital.com.pk
- Subject: Daily Confirmations

## Scheduled Run Times

Default: Daily at 6:00 PM

To change, edit crontab:
```bash
crontab -e
```

Cron format: `MINUTE HOUR DAY MONTH WEEKDAY COMMAND`

Examples:
- `0 18 * * *` - 6:00 PM daily
- `0 9 * * *` - 9:00 AM daily
- `0 18 * * 1-5` - 6:00 PM Monday-Friday only
- `0 */6 * * *` - Every 6 hours

## Troubleshooting Checklist

Problem: **No emails found**
1. Check date in `data/state.json`
2. Verify emails exist in Gmail
3. Check email filters in config.yaml
4. View logs for details

Problem: **PDF parsing failed**
1. Check `data/failed_pdfs/` directory
2. Review error in logs
3. Verify PDF format matches expected structure

Problem: **Cannot authenticate**
1. Check credentials files exist
2. Verify you're a test user in OAuth consent screen
3. Try re-authentication (delete token files)

Problem: **Data not appearing in sheet**
1. Check if transactions were marked as duplicates in log
2. Verify sheet ID and tab name in config.yaml
3. Check sheet permissions
4. Review Sheets API errors in log

Problem: **Cron job not running**
1. Check cron is active: `crontab -l`
2. Check uv path in cron command
3. Check macOS permissions (Full Disk Access)
4. View cron output: `tail logs/cron.log`

## Log Analysis

### Find Errors
```bash
grep ERROR logs/psx_automation.log
```

### Count Transactions Processed
```bash
grep "Successfully added" logs/psx_automation.log | tail -5
```

### See Last Run
```bash
grep "PSX Email Automation Started" logs/psx_automation.log | tail -1
```

### View Duplicates Filtered
```bash
grep "Filtered out" logs/psx_automation.log | tail -5
```

## Maintenance

### Clean Old Logs
Logs auto-rotate at 10MB, keeping 5 backups. To manually clean:
```bash
rm logs/psx_automation.log.1
rm logs/psx_automation.log.2
# etc.
```

### Clean Failed PDFs
```bash
rm -rf data/failed_pdfs/*
```

### Backup State
```bash
cp data/state.json data/state.backup.json
```

## Update Dependencies

```bash
cd /Users/haseebelahi/personal/psx-auto-update
uv sync --upgrade
```

## Sheet Column Reference

| Column | Name | Format | Example |
|--------|------|--------|---------|
| A | Trade Entries >>> | Text | (not modified) |
| B | Symbol | Text | DGKC |
| C | Date | Date | 2026-01-29 |
| D | Mode | BUY/SELL | SELL |
| E | Shares | Number | 434 |
| F | After Tax DPS | Empty | |
| G | Trade price | Decimal | Rs 224.10 |

**Notes**:
- Data is inserted into columns B-G (column A is not touched)
- Trade price is the net price per share calculated as Net Amount ÷ Shares
- Includes all taxes, brokerage fees, and charges
- Script finds first empty row and inserts there (never overwrites existing data)

## State File Format

```json
{
  "last_run": "2026-02-05T18:00:00.123456",
  "total_transactions_processed": 156
}
```

- `last_run`: ISO 8601 timestamp of last successful run
- `total_transactions_processed`: Cumulative count of all transactions added to sheet

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Fatal error (check logs) |

## Support

For issues or questions:
1. Check logs: `logs/psx_automation.log`
2. Review setup guide: `SETUP_GUIDE.md`
3. Check troubleshooting section above
