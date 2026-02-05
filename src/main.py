"""Main orchestration script for PSX email automation"""
import os
import sys
import argparse
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
import yaml

from gmail_client import GmailClient
from pdf_parser import PDFParser
from sheets_client import SheetsClient
from state_manager import StateManager


def load_config(config_path: str = "config/config.yaml") -> dict:
    """Load configuration from YAML file

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary
    """
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def setup_logging(config: dict) -> logging.Logger:
    """Setup logging with file and console handlers

    Args:
        config: Configuration dictionary

    Returns:
        Configured logger
    """
    log_config = config['logging']

    # Create logs directory
    os.makedirs(os.path.dirname(log_config['log_file']), exist_ok=True)

    # Create logger
    logger = logging.getLogger('psx_automation')
    logger.setLevel(getattr(logging, log_config['log_level']))

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_config['log_file'],
        maxBytes=log_config['max_bytes'],
        backupCount=log_config['backup_count']
    )
    file_handler.setLevel(getattr(logging, log_config['log_level']))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def save_failed_pdf(pdf_bytes: bytes, filename: str, logger: logging.Logger):
    """Save failed PDF for manual review

    Args:
        pdf_bytes: PDF content
        filename: Original filename
        logger: Logger instance
    """
    failed_dir = "data/failed_pdfs"
    os.makedirs(failed_dir, exist_ok=True)

    output_path = os.path.join(failed_dir, filename)
    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)

    logger.info(f"Saved failed PDF to {output_path}")


def main(dry_run: bool = False):
    """Main execution function

    Args:
        dry_run: If True, run without writing to Google Sheets
    """
    try:
        # Load configuration
        config = load_config()
        logger = setup_logging(config)

        logger.info("=" * 60)
        if dry_run:
            logger.info("PSX Email Automation Started (DRY RUN MODE)")
            logger.info("No data will be written to Google Sheets")
        else:
            logger.info("PSX Email Automation Started")
        logger.info("=" * 60)

        # Initialize clients
        logger.info("Initializing clients...")

        gmail = GmailClient(
            config['gmail']['credentials_path'],
            config['gmail']['token_path']
        )
        logger.info("Gmail client initialized")

        parser = PDFParser()

        sheets = SheetsClient(
            config['sheets']['credentials_path'],
            config['sheets']['token_path'],
            config['sheets']['spreadsheet_id']
        )
        logger.info("Sheets client initialized")

        state_mgr = StateManager(config['state']['state_file'])

        # Get last run date
        last_run = state_mgr.get_last_run_date(config['state']['lookback_days'])
        logger.info(f"Checking emails since: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")

        # Fetch emails from broker
        emails = gmail.get_emails_since(
            sender=config['gmail']['sender_email'],
            subject=config['gmail']['subject_filter'],
            since_date=last_run
        )
        logger.info(f"Found {len(emails)} email(s)")

        if not emails:
            logger.info("No new emails to process")
            if not dry_run:
                state_mgr.update_last_run_date(datetime.now())
                logger.info("State updated, run complete")
            else:
                logger.info("DRY RUN: State not updated")
            return

        # Process each email's PDF attachments
        all_transactions = []
        for email_num, email in enumerate(emails, 1):
            logger.info(f"Processing email {email_num}/{len(emails)} (ID: {email['id']})")

            attachments = gmail.list_attachments(email['id'])
            logger.info(f"Found {len(attachments)} attachment(s)")

            for att in attachments:
                if att['filename'].lower().endswith('.pdf'):
                    logger.info(f"Processing PDF: {att['filename']}")

                    try:
                        pdf_bytes = gmail.get_attachment(email['id'], att['id'])
                        transactions = parser.parse_pdf(pdf_bytes)
                        all_transactions.extend(transactions)
                        logger.info(f"Extracted {len(transactions)} transaction(s)")

                        # Log transaction details
                        for t in transactions:
                            logger.info(f"  - {t.mode}: {t.symbol} x{t.shares} @ {t.trade_price}")

                    except Exception as e:
                        logger.error(f"Failed to parse {att['filename']}: {e}")
                        save_failed_pdf(pdf_bytes, att['filename'], logger)
                else:
                    logger.info(f"Skipping non-PDF attachment: {att['filename']}")

        logger.info(f"Total transactions extracted: {len(all_transactions)}")

        if not all_transactions:
            logger.info("No transactions found in emails")
            if not dry_run:
                state_mgr.update_last_run_date(datetime.now())
                logger.info("State updated, run complete")
            else:
                logger.info("DRY RUN: State not updated")
            return

        # Filter duplicates
        new_transactions = sheets.filter_duplicates(all_transactions)
        duplicates_count = len(all_transactions) - len(new_transactions)

        if duplicates_count > 0:
            logger.info(f"Filtered out {duplicates_count} duplicate transaction(s)")

        # Sort by date in ascending order (oldest first)
        new_transactions.sort(key=lambda t: t.date)
        logger.info("Sorted transactions by date (ascending order)")

        logger.info(f"New transactions to add: {len(new_transactions)}")

        # Append to Google Sheets (or show in dry run mode)
        if new_transactions:
            if dry_run:
                logger.info("=" * 60)
                logger.info("DRY RUN: The following would be written to Google Sheets:")
                logger.info("=" * 60)
                for i, t in enumerate(new_transactions, 1):
                    row = t.to_sheets_row()
                    logger.info(f"{i}. {row[0]} | {row[1]} | {row[2]} | {row[3]} shares | ${row[5]:.4f}")
                logger.info("=" * 60)
                logger.info(f"DRY RUN: Would add {len(new_transactions)} transaction(s) to sheet")
                logger.info("DRY RUN: No data was actually written")
                logger.info("DRY RUN: No state was updated")
            else:
                sheets.append_transactions(config['sheets']['tab_name'], new_transactions)
                logger.info(f"Successfully added {len(new_transactions)} transaction(s) to sheet")
        else:
            logger.info("No new transactions to add (all duplicates)")

        # Update state (skip in dry run mode)
        if not dry_run:
            state_mgr.update_last_run_date(datetime.now(), len(new_transactions))
            total_processed = state_mgr.get_total_transactions()
            logger.info(f"State updated. Total transactions processed: {total_processed}")
        else:
            logger.info("DRY RUN: State not updated")

        logger.info("=" * 60)
        if dry_run:
            logger.info("PSX Email Automation Completed Successfully (DRY RUN)")
        else:
            logger.info("PSX Email Automation Completed Successfully")
        logger.info("=" * 60)

    except FileNotFoundError as e:
        logger.error(f"Configuration or credentials file not found: {e}")
        logger.error("Please ensure all required files are in place")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='PSX Email-to-Sheets Automation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/main.py              # Normal run (writes to sheet)
  python src/main.py --dry-run    # Dry run (no writes, preview only)
  python src/main.py -d           # Dry run (short form)
        """
    )
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Run in dry-run mode (no data written to Google Sheets)'
    )

    args = parser.parse_args()
    main(dry_run=args.dry_run)
