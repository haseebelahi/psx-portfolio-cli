"""dividends command."""
import click
from rich import box
from rich.table import Table

from helpers import _DEFAULT_SHARIAH_PDF, _group_avg_buy, _resolve_shariah_pdf, console, get_db


@click.command()
@click.option("--symbol",  "-s", default=None, help="Filter by symbol")
@click.option("--summary", is_flag=True,        help="Show one row per symbol with totals")
@click.option(
    "--shariah", "shariah_pdf",
    default=None, metavar="PDF",
    help=f"Path to KMIALL screening PDF (default: {_DEFAULT_SHARIAH_PDF})",
)
def dividends(symbol, summary, shariah_pdf):
    """Show dividend history and totals.

    Add --shariah to include purification % and amount per symbol.
    """
    db = get_db()
    all_divs = db.get_all_dividends()

    if symbol:
        all_divs = [d for d in all_divs if d["symbol"].upper() == symbol.upper()]

    if not all_divs:
        console.print("No dividends found.")
        return

    income_map = _resolve_shariah_pdf(shariah_pdf)
    if income_map:
        console.print(f"[dim]Loaded {len(income_map)} tickers from Shariah PDF[/dim]\n")
    show_shariah = bool(income_map)

    # ── Summary view ──────────────────────────────────────────────────────────
    if summary:
        avg_buy = _group_avg_buy(db.get_all_trades())

        sym_data: dict = {}
        for d in all_divs:
            sym = d["symbol"]
            if sym not in sym_data:
                sym_data[sym] = {
                    "total": 0.0, "total_per_share": 0.0,
                    "count": 0, "first": d["date"], "last": d["date"],
                }
            sym_data[sym]["total"]          += d["after_tax_amount"]
            sym_data[sym]["total_per_share"] += d["per_share"]
            sym_data[sym]["count"]           += 1
            if d["date"] < sym_data[sym]["first"]:
                sym_data[sym]["first"] = d["date"]
            if d["date"] > sym_data[sym]["last"]:
                sym_data[sym]["last"] = d["date"]

        table = Table(title="Dividend Summary by Symbol", box=box.ROUNDED)
        table.add_column("Symbol",        style="bold cyan")
        table.add_column("Payments",      justify="right")
        table.add_column("First",         justify="right")
        table.add_column("Last",          justify="right")
        table.add_column("Total Received", justify="right")
        table.add_column("Yield on Cost", justify="right")
        if show_shariah:
            table.add_column("Non-Compliant %", justify="right")
            table.add_column("Purification",    justify="right")

        grand_total = 0.0
        grand_purification = 0.0
        for sym, data in sorted(sym_data.items(), key=lambda x: x[1]["total"], reverse=True):
            total = data["total"]
            grand_total += total

            # Yield on cost: sum of per-share dividends received / avg buy price
            abp = avg_buy.get(sym)
            if abp and abp > 0:
                yoc = data["total_per_share"] / abp * 100
                yield_str = f"[cyan]{yoc:.2f}%[/cyan]"
            else:
                yield_str = "[dim]—[/dim]"

            row = [
                sym,
                str(data["count"]),
                data["first"],
                data["last"],
                f"[green]Rs {total:>12,.0f}[/green]",
                yield_str,
            ]
            if show_shariah:
                entry = income_map.get(sym, {})
                pct = entry.get("income_pct")
                if pct is not None:
                    purif = total * pct / 100
                    grand_purification += purif
                    pct_color = "red" if pct >= 5 else "yellow"
                    row += [
                        f"[{pct_color}]{pct:.2f}%[/{pct_color}]",
                        f"[red]Rs {purif:>10,.0f}[/red]",
                    ]
                else:
                    row += ["[dim]N/A[/dim]", "[dim]—[/dim]"]
            table.add_row(*row)

        console.print(table)
        console.print(f"\nTotal dividends received : [bold green]Rs {grand_total:,.0f}[/bold green]")
        if show_shariah and grand_purification:
            console.print(f"Total purification due   : [bold red]Rs {grand_purification:,.0f}[/bold red]")
        return

    # ── Detail view ───────────────────────────────────────────────────────────
    table = Table(title="Dividend History", box=box.ROUNDED)
    table.add_column("Date")
    table.add_column("Symbol",          style="bold cyan")
    table.add_column("Shares",          justify="right")
    table.add_column("Per Share",       justify="right")
    table.add_column("After-Tax Total", justify="right")
    if show_shariah:
        table.add_column("Non-Compliant %", justify="right")
        table.add_column("Purification",    justify="right")

    total = 0.0
    total_purification = 0.0
    for d in all_divs:
        amt = d["after_tax_amount"]
        total += amt
        row = [
            d["date"],
            d["symbol"],
            f"{d['shares']:,}",
            f"Rs {d['per_share']:.4f}",
            f"Rs {amt:>12,.0f}",
        ]
        if show_shariah:
            entry = income_map.get(d["symbol"], {})
            pct = entry.get("income_pct")
            if pct is not None:
                purif = amt * pct / 100
                total_purification += purif
                pct_color = "red" if pct >= 5 else "yellow"
                row += [
                    f"[{pct_color}]{pct:.2f}%[/{pct_color}]",
                    f"[red]Rs {purif:>10,.0f}[/red]",
                ]
            else:
                row += ["[dim]N/A[/dim]", "[dim]—[/dim]"]
        table.add_row(*row)

    console.print(table)
    console.print(f"\nTotal dividends received : [bold green]Rs {total:,.0f}[/bold green]")
    if show_shariah and total_purification:
        console.print(f"Total purification due   : [bold red]Rs {total_purification:,.0f}[/bold red]")
