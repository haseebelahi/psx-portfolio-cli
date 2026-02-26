"""Data models for PSX portfolio tracker"""
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass
class Transaction:
    """Represents a single stock transaction"""
    symbol: str
    date: datetime
    mode: str  # "BUY" or "SELL"
    shares: int
    trade_price: float  # Net price per share (after taxes, fees, etc.)

    def to_sheets_row(self) -> List:
        """Convert transaction to Google Sheets row format"""
        return [
            self.symbol,
            self.date.strftime('%Y-%m-%d'),
            self.mode,
            self.shares,
            "",  # After Tax DPS (skip)
            self.trade_price
        ]


@dataclass
class Dividend:
    """Represents a dividend payment"""
    symbol: str
    date: str          # YYYY-MM-DD string
    after_tax_amount: float
    shares: int
    per_share: float


@dataclass
class Deposit:
    """Represents a cash deposit"""
    amount: float
    date: str          # YYYY-MM-DD string
    broker: str = ""
