"""chart command group — terminal charts for portfolio data."""
import click

from helpers import console, get_db


@click.group()
def chart():
    """Terminal charts for portfolio data."""


@chart.command("nlv")
def chart_nlv():
    """Historical portfolio value (NLV), invested amount, and total deposits."""
    import plotext as plt

    rows = get_db().get_portfolio_history()
    if not rows:
        console.print("[yellow]No portfolio history yet — run ./psx dashboard after market hours.[/yellow]")
        return

    dates      = [r["date"] for r in rows]
    nlvs       = [r["nlv"]          / 1_000_000 for r in rows]
    invested   = [r["invested"]     / 1_000_000 for r in rows]
    deposits   = [r["total_deposits"] / 1_000_000 for r in rows]

    plt.clf()
    plt.date_form("Y-m-d")
    plt.plot(dates, nlvs,     marker="braille", color="green",  label="NLV (Rs M)")
    plt.plot(dates, invested, marker="braille", color="cyan",   label="Invested (Rs M)")
    plt.plot(dates, deposits, marker="braille", color="yellow", label="Deposits (Rs M)")
    plt.title("Portfolio Value Over Time")
    plt.xlabel("Date")
    plt.ylabel("Rs (millions)")
    plt.plotsize(100, 30)
    plt.show()

    latest = rows[-1]
    pnl = latest["nlv"] - latest["total_deposits"]
    pnl_pct = pnl / latest["total_deposits"] * 100 if latest["total_deposits"] else 0
    color = "green" if pnl >= 0 else "red"
    console.print(
        f"\nLatest NLV: [bold green]Rs {latest['nlv']:,.0f}[/bold green]  "
        f"P&L: [{color}]Rs {pnl:,.0f} ({pnl_pct:+.1f}%)[/{color}]  "
        f"[dim]as of {latest['date']}[/dim]"
    )


@chart.command("deposits")
def chart_deposits():
    """Trend line of cumulative deposits overlaid with KSE100 index."""
    import plotext as plt

    db = get_db()
    deposits = db.get_all_deposits()
    if not deposits:
        console.print("[yellow]No deposits found.[/yellow]")
        return

    deposits.sort(key=lambda d: d["date"])

    dep_dates, cumulative = [], []
    running = 0.0
    for d in deposits:
        running += d["amount"]
        dep_dates.append(d["date"])
        cumulative.append(running / 1_000_000)

    # KSE100 history filtered to the same date range
    first_date, last_date = dep_dates[0], dep_dates[-1]
    kse_rows = [
        (dt, val) for dt, val in db.get_index_history("KSE100")
        if first_date <= dt <= last_date
    ]

    plt.clf()
    plt.date_form("Y-m-d")
    plt.plot(dep_dates, cumulative, marker="braille", color="green", label="Deposits (Rs M)")
    plt.ylabel("Rs (millions)")

    if kse_rows:
        kse_dates = [r[0] for r in kse_rows]
        kse_vals  = [r[1] / 1_000 for r in kse_rows]   # display in thousands
        plt.plot(kse_dates, kse_vals, marker="braille", color="cyan", yside=2, label="KSE100 (000s)")

    plt.title("Cumulative Deposits vs KSE100")
    plt.xlabel("Date")
    plt.plotsize(100, 30)
    plt.show()

    if not kse_rows:
        console.print("[dim]No KSE100 history found — run: ./psx import-kse[/dim]")
    console.print(
        f"\nTotal deposited: [bold green]Rs {running:,.0f}[/bold green]  "
        f"across [bold]{len(deposits)}[/bold] deposit(s)"
    )
