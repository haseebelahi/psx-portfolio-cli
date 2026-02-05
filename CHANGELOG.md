# Changelog

## [0.1.0] - 2026-02-05

### Added
- **Dry Run Mode**: Test the automation without writing to Google Sheets
  - Use `--dry-run` or `-d` flag
  - Shows exactly what would be written
  - Does not modify sheets or state file
  - Perfect for testing and verification

### Fixed
- **Sheet Column Mapping**: Corrected to use columns B-G (not A-F)
  - Column A contains "Trade Entries >>>" label (not modified)
  - Data is written to columns B (Symbol) through G (Trade Price)

- **Sheet Insertion**: Now correctly inserts data into existing table structure
  - Checks column B (Symbol) to find first empty row
  - Verifies entire row (B-G) is empty before inserting
  - Never overwrites existing data
  - No longer creates new rows below the table
  - Works with formatted tables with headers and styling

- **Date Reading**: Updated to use column C (Date column)
  - Reads from correct column for duplicate detection
  - Uses flexible date parser to handle multiple formats
  - Works with "31 Dec 2025", "2026-01-29", and other formats

### Changed
- **Date Sorting**: Transactions are now sorted by date in ascending order (oldest first) before insertion
- **Mode Format**: Mode column now outputs "BUY" and "SELL" in all caps (was "Buy" and "Sell")
- **IMPORTANT**: Updated PDF parser to extract **Net Amount Rs.** instead of Rate/Share
- Trade price is now calculated as: **Net Amount ÷ Shares**
- This provides the actual net price per share after all taxes, brokerage, and fees

### Example
For a transaction:
- **Shares**: 434
- **Rate/Share (gross)**: 224.7500
- **Net Amount Rs.**: 97,261.07
- **Net Price per Share**: 97,261.07 ÷ 434 = **224.1038**

The system now records **224.1038** (net price) instead of 224.7500 (gross rate).

### Why This Matters
The net price reflects:
- ✅ Brokerage charges
- ✅ FED (Federal Excise Duty)
- ✅ CVT (Capital Value Tax)
- ✅ WHT (Withholding Tax)
- ✅ All other fees and charges

This is the **actual cost/revenue per share** for the transaction.

### Technical Details
- Updated `src/pdf_parser.py`: Modified `extract_table_data()` method
- Updated regex pattern to capture last column (Net Amount Rs.)
- Added calculation: `net_price_per_share = net_amount / shares`
- Updated documentation across README, QUICK_REFERENCE, and PROJECT_SUMMARY

### Testing
All 7 transactions from sample PDF parsed successfully with correct net prices:
- DGKC: 224.1038 (was 224.7500)
- FFC: 598.3353 (was 596.6200)
- ILP: 80.2300, 81.1727 (was 80.0000, 80.9400)
- LCI: 277.2949 (was 276.5000)
- SYS: 155.4356, 157.2508 (was 154.9900, 156.8000)

### Impact
- More accurate tracking of actual investment costs
- Better portfolio valuation
- Correct profit/loss calculations
- Reflects real-world transaction costs
