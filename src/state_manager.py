"""State management for tracking last run timestamp"""
import os
import json
from datetime import datetime, timedelta


class StateManager:
    """Manages persistent state for the automation"""

    def __init__(self, state_file: str = "data/state.json"):
        """Initialize state manager

        Args:
            state_file: Path to state file
        """
        self.state_file = state_file
        self._ensure_state_file()

    def _ensure_state_file(self):
        """Create state file and directory if they don't exist"""
        os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

        if not os.path.exists(self.state_file):
            self._write_state({
                "last_run": None,
                "total_transactions_processed": 0
            })

    def _read_state(self) -> dict:
        """Read state from file

        Returns:
            Dictionary containing state data
        """
        with open(self.state_file, 'r') as f:
            return json.load(f)

    def _write_state(self, state: dict):
        """Write state to file

        Args:
            state: Dictionary containing state data
        """
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)

    def get_last_run_date(self, lookback_days: int = 7) -> datetime:
        """Get last run timestamp

        Args:
            lookback_days: Number of days to look back on first run

        Returns:
            datetime object representing last run time or lookback date
        """
        state = self._read_state()

        if state.get("last_run"):
            return datetime.fromisoformat(state["last_run"])
        else:
            # First run: default to lookback_days ago
            return datetime.now() - timedelta(days=lookback_days)

    def update_last_run_date(self, run_date: datetime, transactions_processed: int = 0):
        """Update last run timestamp and transaction count

        Args:
            run_date: datetime of successful run
            transactions_processed: Number of transactions processed in this run
        """
        state = self._read_state()

        state["last_run"] = run_date.isoformat()
        state["total_transactions_processed"] = state.get("total_transactions_processed", 0) + transactions_processed

        self._write_state(state)

    def get_total_transactions(self) -> int:
        """Get total number of transactions processed

        Returns:
            Total transaction count
        """
        state = self._read_state()
        return state.get("total_transactions_processed", 0)
