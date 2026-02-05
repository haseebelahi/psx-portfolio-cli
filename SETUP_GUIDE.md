# Setup Guide for PSX Email-to-Sheets Automation

This guide walks you through the complete setup process.

## Step 1: Google Cloud API Setup

### Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click "Select a project" → "New Project"
3. Name: "PSX Email Automation"
4. Click "Create"

### Enable Gmail API

1. In the Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Gmail API"
3. Click on it and press "Enable"

### Enable Google Sheets API

1. In the Cloud Console, go to "APIs & Services" → "Library"
2. Search for "Google Sheets API"
3. Click on it and press "Enable"

### Configure OAuth Consent Screen

1. Go to "APIs & Services" → "OAuth consent screen"
2. Choose "External" user type (unless you have a Google Workspace)
3. Click "Create"
4. Fill in:
   - App name: "PSX Email Automation"
   - User support email: Your email
   - Developer contact email: Your email
5. Click "Save and Continue"
6. On "Scopes" page, click "Add or Remove Scopes"
   - Search and add: `https://www.googleapis.com/auth/gmail.readonly`
   - Search and add: `https://www.googleapis.com/auth/spreadsheets`
7. Click "Save and Continue"
8. On "Test users" page, click "Add Users"
   - Add your Gmail address
9. Click "Save and Continue"

### Create OAuth Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Application type: "Desktop app"
4. Name: "PSX Desktop Client"
5. Click "Create"
6. Click "Download JSON"
7. Rename the downloaded file to `gmail_credentials.json`
8. Move it to `/Users/haseebelahi/personal/psx-auto-update/credentials/`

### Create Sheets Credentials (Option 1: Reuse Gmail credentials)

The easiest approach is to copy the Gmail credentials:

```bash
cd /Users/haseebelahi/personal/psx-auto-update/credentials
cp gmail_credentials.json sheets_credentials.json
```

### Create Sheets Credentials (Option 2: Separate credentials)

If you want separate credentials for Sheets:

1. In Cloud Console, go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Application type: "Desktop app"
4. Name: "PSX Sheets Client"
5. Click "Create"
6. Download JSON and save as `sheets_credentials.json`
7. Move to `/Users/haseebelahi/personal/psx-auto-update/credentials/`

## Step 2: Share Google Sheet

1. Open your Google Sheet: https://docs.google.com/spreadsheets/d/1SEbkKKooBganzymX9WayuqqEJwUefDi-MZ72UoWlqIM
2. Verify it has a tab named "Entry"
3. Verify the "Entry" tab has these columns:
   - Column A: Symbol
   - Column B: Date
   - Column C: Mode
   - Column D: Shares
   - Column E: After Tax DPS
   - Column F: Trade price

Note: The sheet must be accessible to your Google account. If you created it with the same account, you're already set.

## Step 3: Install Dependencies

```bash
cd /Users/haseebelahi/personal/psx-auto-update
uv sync
```

If you don't have `uv` installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Step 4: First Run - Authentication

Run the script for the first time:

```bash
cd /Users/haseebelahi/personal/psx-auto-update
uv run python src/main.py
```

### What to Expect:

1. **Gmail Authentication**
   - A browser window will open
   - Sign in with your Gmail account
   - You may see a warning "Google hasn't verified this app"
   - Click "Advanced" → "Go to PSX Email Automation (unsafe)"
   - Click "Allow" to grant Gmail read access
   - The browser will show "The authentication flow has completed"
   - Close the browser window

2. **Sheets Authentication**
   - Another browser window will open
   - Sign in (if not already)
   - You may see the same warning
   - Click "Advanced" → "Go to PSX Email Automation (unsafe)"
   - Click "Allow" to grant Sheets access
   - Close the browser window

3. **Script Execution**
   - The script will now run
   - Check `logs/psx_automation.log` for results
   - It will look back 7 days on first run

### Token Files

After authentication, you'll see two new files in `credentials/`:
- `gmail_token.json` - Stores Gmail access token
- `sheets_token.json` - Stores Sheets access token

These tokens will be automatically refreshed when they expire. Keep them secure.

## Step 5: Test with Dry Run

Before writing any data, test with dry run mode:

```bash
cd /Users/haseebelahi/personal/psx-auto-update
uv run python src/main.py --dry-run
```

This will:
- Authenticate with Gmail and Sheets (if first time)
- Fetch emails and parse PDFs
- Show you exactly what would be written
- **NOT** write to Google Sheets
- **NOT** update state file

Expected output in logs:
```
============================================================
PSX Email Automation Started (DRY RUN MODE)
No data will be written to Google Sheets
============================================================
...
============================================================
DRY RUN: The following would be written to Google Sheets:
============================================================
1. DGKC | 2026-01-29 | Sell | 434 shares | $224.1038
2. FFC | 2026-01-29 | Buy | 100 shares | $598.3353
...
============================================================
DRY RUN: Would add 7 transaction(s) to sheet
DRY RUN: No data was actually written
DRY RUN: No state was updated
```

Review the output to ensure:
- Transactions are parsed correctly
- Dates are correct
- Prices make sense
- Buy/Sell modes are correct

## Step 6: Verify Everything Works (First Real Run)

Once you're happy with the dry run, do a real run:

```bash
uv run python src/main.py
```

### Check Logs

```bash
tail -f logs/psx_automation.log
```

Expected output:
```
2026-02-05 00:30:00 - psx_automation - INFO - ============================================================
2026-02-05 00:30:00 - psx_automation - INFO - PSX Email Automation Started
2026-02-05 00:30:00 - psx_automation - INFO - ============================================================
2026-02-05 00:30:00 - psx_automation - INFO - Initializing clients...
2026-02-05 00:30:01 - psx_automation - INFO - Gmail client initialized
2026-02-05 00:30:02 - psx_automation - INFO - Sheets client initialized
2026-02-05 00:30:02 - psx_automation - INFO - Checking emails since: 2026-01-29 00:30:00
2026-02-05 00:30:03 - psx_automation - INFO - Found 3 email(s)
...
```

### Check Google Sheets

1. Open your sheet
2. Go to the "Entry" tab
3. Verify new transactions were added
4. Check that dates are formatted correctly (YYYY-MM-DD)

### Check State File

```bash
cat data/state.json
```

Should contain:
```json
{
  "last_run": "2026-02-05T00:30:05.123456",
  "total_transactions_processed": 15
}
```

## Step 6: Set Up Automated Daily Run

### Find uv Path

```bash
which uv
```

Example output: `/Users/haseebelahi/.local/bin/uv`

### Add to Crontab

```bash
crontab -e
```

Add this line (replace `<UV_PATH>` with the path from above):

```
0 18 * * * cd /Users/haseebelahi/personal/psx-auto-update && <UV_PATH> run python src/main.py >> /Users/haseebelahi/personal/psx-auto-update/logs/cron.log 2>&1
```

Example (with actual path):
```
0 18 * * * cd /Users/haseebelahi/personal/psx-auto-update && /Users/haseebelahi/.local/bin/uv run python src/main.py >> /Users/haseebelahi/personal/psx-auto-update/logs/cron.log 2>&1
```

This will run daily at 6:00 PM.

### Verify Cron Job

```bash
crontab -l
```

Should show your new entry.

## Troubleshooting

### "credentials file not found"

Make sure:
- `credentials/gmail_credentials.json` exists
- `credentials/sheets_credentials.json` exists
- File permissions allow reading

### "Permission denied" during OAuth

Make sure:
- You're using a Google account that has access to the emails
- You added yourself as a test user in OAuth consent screen
- You clicked "Allow" for all requested permissions

### "No emails found"

- Check that emails exist from `settlement@nextcapital.com.pk`
- Check subject line matches "Daily Confirmations"
- Check the date range (7 days back on first run)
- Manually verify emails in Gmail

### "Failed to parse PDF"

- Check `data/failed_pdfs/` for the problematic PDF
- Check `logs/psx_automation.log` for error details
- The PDF might have a different format than expected

### "Sheet not found"

- Verify the spreadsheet ID in `config/config.yaml`
- Verify the sheet has a tab named "Entry"
- Verify you have access to the sheet

### Token expired errors

Delete the token files and re-authenticate:

```bash
rm credentials/gmail_token.json credentials/sheets_token.json
uv run python src/main.py
```

### Cron job not running

Check cron logs:
```bash
tail -f /Users/haseebelahi/personal/psx-auto-update/logs/cron.log
```

Make sure:
- The uv path is correct
- The working directory path is correct
- Cron has permissions (macOS: System Preferences → Security & Privacy → Full Disk Access)

## Testing

### Test with Sample PDF

```bash
cd /Users/haseebelahi/personal/psx-auto-update
uv run python test_pdf_parser.py
```

Should parse 7 transactions from the sample PDF.

### Dry Run (without writing to sheets)

You can temporarily modify the main.py to comment out the append line if you want to test without writing to the actual sheet.

## Security Notes

- **Never commit credentials/** - Already in .gitignore
- Keep token files secure - they provide access to your email and sheets
- Use read-only Gmail scope - The app only reads emails, cannot send or delete
- Review OAuth consent screen - Only grant to your own account
- Revoke access anytime - Go to https://myaccount.google.com/permissions

## Next Steps

After successful setup:

1. Monitor logs for the first few days
2. Verify data accuracy in Google Sheets
3. Check `data/state.json` updates correctly
4. Test duplicate prevention by running twice
5. Verify cron job runs at scheduled time

## Getting Help

If you encounter issues:

1. Check `logs/psx_automation.log` for detailed error messages
2. Review the troubleshooting section above
3. Verify all setup steps were completed
4. Check file permissions on credentials and data directories
