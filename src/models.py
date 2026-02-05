"""Data models for PSX transactions"""
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
        """Convert transaction to Google Sheets row format

        Returns:
            List with format: [Symbol, Date, Mode, Shares, Empty, Trade Price]
        """
        return [
            self.symbol,
            self.date.strftime('%Y-%m-%d'),
            self.mode,
            self.shares,
            "",  # After Tax DPS (skip)
            self.trade_price
        ]
