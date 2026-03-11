# CLAUDE.md — PSX Portfolio Tracker

## Project Purpose
Local CLI tool tracking a PSX portfolio. Syncs broker confirmation emails → PDF parsing → SQLite → analytics.
Run commands via `./psx` from the project root.

## Build & Run
- Package manager: `uv` (not pip)
- Run CLI: `./psx <command>` (shell wrapper around `uv run python src/cli.py`)
- Add dependencies: `uv add <package>`

## Key Non-Obvious Facts

1. **Net Price**: calculated as `Net Amount ÷ Shares` — already includes all brokerage fees, taxes, and charges. Do not recalculate from trade price alone.

2. **Modular structure**: Commands live in `src/commands/`, shared state in `src/helpers.py`. `src/cli.py` is a thin entry point only — do not add logic there.

3. **Price caching**: After market close (15:30 PKT, Mon–Fri), prices are cached in `price_cache` and reused until next open. LDCP is stored alongside current price for day P&L.

4. **Shariah data**: Parsed from a KMIALL PDF (pdfplumber), cached in `shariah_cache` for 90 days. Default PDF: `Merged_KMIALL_Notice_and_FinalList_June2025.pdf` in project root.

5. **XIRR**: Newton's method on irregular cash flows in `portfolio.py`. Used for per-position and per-sector analytics.

6. **Portfolio snapshots**: `dashboard` writes one row per day to `portfolio_history` after market close (`INSERT OR IGNORE`). The `fetch` command does NOT write to this table — only `dashboard` does.

7. **State file**: `data/state.json` tracks `last_run`. Updated after every `sync` to prevent re-processing emails.

8. **Failed PDFs**: Saved to `data/failed_pdfs/` — execution continues rather than stopping.

9. **`fetch` command**: Lightweight cron target (runs every 30 min during market hours). Updates `index_history` and `price_cache` only.

10. **Deposits chart**: Extended to today's date even when the last deposit is older, so the KSE100 overlay spans the full range.
