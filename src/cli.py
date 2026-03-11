"""PSX Portfolio Tracker CLI."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import click

from commands.sync      import sync
from commands.fetch     import fetch
from commands.dashboard import dashboard
from commands.positions import positions
from commands.trades    import trades, history
from commands.dividends import dividends
from commands.chart     import chart
from commands.add       import add
from commands.import_   import import_from_sheets, import_kse_csv


@click.group()
def cli():
    """PSX Portfolio Tracker — manage trades, positions, and analytics."""


cli.add_command(sync)
cli.add_command(fetch)
cli.add_command(dashboard)
cli.add_command(positions)
cli.add_command(trades)
cli.add_command(history)
cli.add_command(dividends)
cli.add_command(chart)
cli.add_command(add)
cli.add_command(import_from_sheets, name="import")
cli.add_command(import_kse_csv)

if __name__ == "__main__":
    cli()
