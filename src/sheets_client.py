"""Google Sheets API client for managing transaction data"""
import os
from datetime import date
from typing import List, Set
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import gspread
from dateutil import parser as date_parser

from models import Transaction


# Google Sheets API scopes
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


class SheetsClient:
    """Client for interacting with Google Sheets API"""

    def __init__(self, credentials_path: str, token_path: str, sheet_id: str):
        """Initialize Sheets client with OAuth credentials

        Args:
            credentials_path: Path to OAuth credentials JSON file
            token_path: Path to save/load token file
            sheet_id: Google Sheets spreadsheet ID
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.sheet_id = sheet_id
        self.client = self._authenticate()
        self.spreadsheet = self.client.open_by_key(sheet_id)

    def _authenticate(self):
        """Authenticate with Google Sheets API using OAuth2

        Returns:
            gspread client object
        """
        creds = None

        # Load existing token if available
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        # Refresh or create new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            # Save credentials for next run
            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())

        return gspread.authorize(creds)

    def get_existing_dates(self, tab_name: str = "Entry") -> Set[date]:
        """Get all existing transaction dates from the sheet

        Args:
            tab_name: Name of the worksheet tab

        Returns:
            Set of date objects representing existing transaction dates
        """
        worksheet = self.spreadsheet.worksheet(tab_name)

        # Get all values from Date column (column C, index 3)
        # Skip header row
        date_values = worksheet.col_values(3)[1:]

        existing_dates = set()
        for date_str in date_values:
            if date_str and date_str.strip():
                try:
                    # Parse date using dateutil (handles multiple formats)
                    # e.g., "2026-01-29", "29 Jan 2026", "31 Dec 2025", etc.
                    parsed_date = date_parser.parse(date_str, dayfirst=True)
                    existing_dates.add(parsed_date.date())
                except (ValueError, TypeError):
                    # Skip invalid dates
                    continue

        return existing_dates

    def filter_duplicates(self, transactions: List[Transaction]) -> List[Transaction]:
        """Remove transactions with dates that already exist in the sheet

        Args:
            transactions: List of Transaction objects

        Returns:
            List of Transaction objects with unique dates
        """
        existing_dates = self.get_existing_dates()

        new_transactions = []
        for transaction in transactions:
            if transaction.date.date() not in existing_dates:
                new_transactions.append(transaction)

        return new_transactions

    def append_transactions(self, tab_name: str, transactions: List[Transaction]):
        """Append new transactions to the sheet table

        Args:
            tab_name: Name of the worksheet tab
            transactions: List of Transaction objects to append
        """
        if not transactions:
            return

        worksheet = self.spreadsheet.worksheet(tab_name)

        # Find the first empty row in column B (Symbol column)
        # Get all values from column B (this returns only non-empty cells)
        symbol_col = worksheet.col_values(2)  # Column B is index 2

        # The table starts at row 2 (row 1 is header)
        # First empty row is right after the last row with data
        # len(symbol_col) gives us the count of non-empty cells
        # So first_empty_row = len(symbol_col) + 1
        first_empty_row = len(symbol_col) + 1

        # Safety check: make sure this row is actually empty
        # Check if any cell in this row (columns B-G) has data
        try:
            # Get values from columns B to G for this row
            row_range = f'B{first_empty_row}:G{first_empty_row}'
            row_data = worksheet.get(row_range)[0] if worksheet.get(row_range) else []

            # If any cell has data, find the next truly empty row
            while row_data and any(cell.strip() if isinstance(cell, str) else cell for cell in row_data):
                first_empty_row += 1
                row_range = f'B{first_empty_row}:G{first_empty_row}'
                try:
                    row_data = worksheet.get(row_range)[0] if worksheet.get(row_range) else []
                except:
                    row_data = []
                    break
        except:
            # Row doesn't exist yet, which is fine
            pass

        # Convert transactions to rows
        rows = [transaction.to_sheets_row() for transaction in transactions]

        # Define the range to update (B:G columns, 6 columns total)
        start_cell = f'B{first_empty_row}'
        end_cell = f'G{first_empty_row + len(rows) - 1}'
        cell_range = f'{start_cell}:{end_cell}'

        # Update the cells in the table
        worksheet.update(cell_range, rows, value_input_option='USER_ENTERED')
