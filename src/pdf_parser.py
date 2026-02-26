"""PDF parsing module for PSX trading confirmations"""
import re
import io
from datetime import datetime
from typing import List, Dict
import pdfplumber
from dateutil import parser as date_parser

from models import Transaction


class PDFParser:
    """Parser for PSX confirmation memo PDFs"""

    def parse_pdf(self, pdf_bytes: bytes) -> List[Transaction]:
        """Parse entire PDF and extract all transactions

        Args:
            pdf_bytes: PDF file content as bytes

        Returns:
            List of Transaction objects
        """
        transactions = []

        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                try:
                    page_text = page.extract_text()

                    # Extract trade date
                    trade_date = self.extract_trade_date(page_text)

                    # Extract transaction mode (Buy/Sell)
                    mode = self.extract_transaction_mode(page_text)

                    # Extract table data
                    table_rows = self.extract_table_data(page)

                    # Create Transaction objects
                    for row in table_rows:
                        transaction = Transaction(
                            symbol=row['symbol'],
                            date=trade_date,
                            mode=mode,
                            shares=row['shares'],
                            trade_price=row['trade_price']
                        )
                        transactions.append(transaction)

                except Exception as e:
                    raise ValueError(f"Error parsing page {page_num}: {e}")

        return transactions

    def extract_trade_date(self, page_text: str) -> datetime:
        """Extract trade date from page text

        Args:
            page_text: Extracted text from PDF page

        Returns:
            datetime object representing trade date
        """
        # Pattern: Find DD-MMM-YYYY anywhere in text near "Trade Date"
        # The layout has "Trade Date :" on one line and date on the next
        pattern = r"(\d{2}-[A-Z]{3}-\d{4})"
        match = re.search(pattern, page_text, re.IGNORECASE)

        if not match:
            raise ValueError("Trade date not found in PDF")

        date_str = match.group(1)
        return date_parser.parse(date_str, dayfirst=True)

    def extract_transaction_mode(self, page_text: str) -> str:
        """Determine if transaction is Buy or Sell

        Args:
            page_text: Extracted text from PDF page

        Returns:
            "BUY" or "SELL"
        """
        if "SOLD FOR YOU AS FOLLOWS" in page_text.upper():
            return "SELL"
        elif "PURCHASED FOR YOU AS FOLLOWS" in page_text.upper():
            return "BUY"
        else:
            raise ValueError("Transaction mode (Buy/Sell) not found in PDF")

    def extract_table_data(self, page) -> List[Dict]:
        """Extract transaction rows from PDF table

        Args:
            page: pdfplumber page object

        Returns:
            List of dictionaries with transaction data
        """
        page_text = page.extract_text()

        # Parse transaction lines directly from text
        # Format: "434 DGKC T+2 NCSS 02/02/2026 224.7500 ... 97,261.07"
        # We need: Shares, Symbol, and Net Amount Rs. (last column)
        # Net price per share = Net Amount / Shares

        transactions = []

        # Find all lines that match the transaction pattern
        # Look for lines starting with digits (shares) followed by stock symbol
        lines = page_text.split('\n')

        for line in lines:
            # Skip empty lines
            if not line.strip():
                continue

            # Transaction lines start with number (shares), then symbol
            # Pattern: NUMBER SYMBOL ...other data... NET_AMOUNT (last number)
            # Shares may be comma-formatted (e.g. 2,000)
            match = re.match(r'^(\d{1,3}(?:,\d{3})*)\s+([A-Z]+)\s+.*?(\d+(?:,\d{3})*\.\d{2})$', line.strip())

            if match:
                shares_str = match.group(1)
                symbol = match.group(2)
                net_amount_str = match.group(3).replace(',', '')  # Remove commas from amount

                # Skip lines with summary totals (they repeat the shares count)
                # Also skip if symbol is not a valid stock code
                if symbol in ['T', 'NCSS', 'TYPE', 'QUANTITY']:
                    continue

                try:
                    shares = int(shares_str.replace(',', ''))
                    net_amount = float(net_amount_str)

                    # Calculate net price per share (after taxes and fees)
                    net_price_per_share = net_amount / shares

                    # Validate: shares and amounts should be positive
                    if shares > 0 and net_amount > 0 and len(symbol) <= 6:
                        transactions.append({
                            'shares': shares,
                            'symbol': symbol,
                            'trade_price': net_price_per_share
                        })
                except (ValueError, AttributeError, ZeroDivisionError):
                    continue

        if not transactions:
            raise ValueError("No valid transaction data found in page")

        return transactions

    def _find_column_index(self, header: List[str], possible_names: List[str]) -> int:
        """Find column index by searching for possible column names

        Args:
            header: List of column headers
            possible_names: List of possible names for the column

        Returns:
            Index of the column
        """
        for name in possible_names:
            for idx, col in enumerate(header):
                if name in col:
                    return idx
        raise ValueError(f"Column not found. Possible names: {possible_names}")
