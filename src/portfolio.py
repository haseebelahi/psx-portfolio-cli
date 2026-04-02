"""Pure portfolio calculation logic — no I/O."""
from dataclasses import dataclass
from datetime import date


def xirr(cash_flows: list[tuple[date, float]]) -> float:
    """Return the annualised internal rate of return for irregular cash flows.

    cash_flows is a list of (date, amount) pairs where negative amounts are
    outflows (deposits) and positive amounts are inflows (terminal value).
    Returns the rate as a percentage, or 0.0 if it cannot be solved.
    """
    if len(cash_flows) < 2:
        return 0.0

    t0 = cash_flows[0][0]
    times   = [(cf[0] - t0).days / 365.25 for cf in cash_flows]
    amounts = [cf[1] for cf in cash_flows]

    def npv(rate: float) -> float:
        return sum(a / (1 + rate) ** t for a, t in zip(amounts, times))

    def dnpv(rate: float) -> float:
        return sum(-t * a / (1 + rate) ** (t + 1) for a, t in zip(amounts, times))

    rate = 0.1  # initial guess
    for _ in range(200):
        f  = npv(rate)
        df = dnpv(rate)
        if abs(df) < 1e-12:
            break
        step = f / df
        rate -= step
        if rate <= -1:
            rate = -0.9999
        if abs(step) < 1e-8:
            break

    # Sanity check: if NPV is not close to zero the solver diverged
    if abs(npv(rate)) > 1.0:
        return 0.0

    return rate * 100


@dataclass
class Position:
    symbol: str
    shares: int
    avg_buy_price: float
    current_price: float
    cost_basis: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float
    cagr: float
    xirr: float


@dataclass
class PortfolioSummary:
    total_deposits: float
    buy_cost: float
    sell_proceeds: float
    total_dividends: float
    cash_balance: float
    market_value: float
    current_invested: float
    nlv: float
    pnl: float
    absolute_return: float
    annualized_return: float
    xirr_return: float
    first_trade_date: date | None
    years_invested: float


def compute_positions(trades: list[dict], prices: dict[str, float]) -> list[Position]:
    holdings: dict[str, dict] = {}

    for t in sorted(trades, key=lambda x: x["date"]):
        sym = t["symbol"]
        if sym not in holdings:
            holdings[sym] = {"buy_shares": 0, "sell_shares": 0, "buy_cost": 0.0, "running_shares": 0, "flows": []}
        d = holdings[sym]
        amt = t["shares"] * t["trade_price"]
        if t["mode"] == "BUY":
            d["buy_shares"]     += t["shares"]
            d["buy_cost"]       += amt
            d["running_shares"] += t["shares"]
            d["flows"].append((date.fromisoformat(t["date"]), -amt))
        elif t["mode"] == "SELL":
            d["sell_shares"]    += t["shares"]
            d["running_shares"] -= t["shares"]
            d["flows"].append((date.fromisoformat(t["date"]), +amt))
            # Position fully closed — reset cost basis so re-entry starts fresh
            if d["running_shares"] <= 0:
                d["buy_shares"]     = 0
                d["buy_cost"]       = 0.0
                d["running_shares"] = 0

    today = date.today()
    positions: list[Position] = []
    for sym, data in holdings.items():
        current_shares = data["running_shares"]
        if current_shares <= 0:
            continue

        avg_buy    = data["buy_cost"] / data["buy_shares"] if data["buy_shares"] else 0.0
        cur_price  = prices.get(sym, avg_buy)
        market_val = current_shares * cur_price
        cost       = current_shares * avg_buy
        pnl        = market_val - cost
        pnl_pct    = (pnl / cost * 100) if cost else 0.0

        # CAGR: from first trade to today on open position only
        first_date  = min(cf[0] for cf in data["flows"])
        years       = (today - first_date).days / 365.25
        pos_cagr    = ((market_val / cost) ** (1 / years) - 1) * 100 if years > 0 and cost > 0 else 0.0

        # XIRR: all buy/sell flows + terminal market value today
        flows = data["flows"] + [(today, market_val)]
        flows.sort(key=lambda cf: cf[0])
        pos_xirr = xirr(flows)

        positions.append(
            Position(
                symbol=sym,
                shares=current_shares,
                avg_buy_price=avg_buy,
                current_price=cur_price,
                cost_basis=cost,
                market_value=market_val,
                unrealized_pnl=pnl,
                unrealized_pnl_pct=pnl_pct,
                cagr=pos_cagr,
                xirr=pos_xirr,
            )
        )

    return sorted(positions, key=lambda p: p.market_value, reverse=True)


def compute_summary(
    trades: list[dict],
    dividends: list[dict],
    deposits: list[dict],
    positions: list[Position],
) -> PortfolioSummary:
    total_deposits = sum(d["amount"] for d in deposits)
    buy_cost = sum(t["shares"] * t["trade_price"] for t in trades if t["mode"] == "BUY")
    sell_proceeds = sum(t["shares"] * t["trade_price"] for t in trades if t["mode"] == "SELL")
    total_dividends = sum(d["after_tax_amount"] for d in dividends)

    cash_balance = total_deposits + sell_proceeds - buy_cost
    market_value = sum(p.market_value for p in positions)
    current_invested = sum(p.cost_basis for p in positions)
    nlv = cash_balance + market_value
    pnl = nlv - total_deposits
    absolute_return = (pnl / total_deposits * 100) if total_deposits else 0.0

    first_trade_date = None
    years_invested = 0.0
    annualized_return = 0.0
    xirr_return = 0.0

    if trades:
        first_trade_date = min(date.fromisoformat(t["date"]) for t in trades)
        days = (date.today() - first_trade_date).days
        years_invested = days / 365.25
        if years_invested > 0 and total_deposits > 0:
            annualized_return = ((nlv / total_deposits) ** (1 / years_invested) - 1) * 100

    if deposits and nlv > 0:
        # Each deposit is an outflow (negative); today's NLV is the terminal inflow
        cash_flows = [(date.fromisoformat(d["date"]), -d["amount"]) for d in deposits]
        cash_flows.append((date.today(), nlv))
        cash_flows.sort(key=lambda cf: cf[0])
        xirr_return = xirr(cash_flows)

    return PortfolioSummary(
        total_deposits=total_deposits,
        buy_cost=buy_cost,
        sell_proceeds=sell_proceeds,
        total_dividends=total_dividends,
        cash_balance=cash_balance,
        market_value=market_value,
        current_invested=current_invested,
        nlv=nlv,
        pnl=pnl,
        absolute_return=absolute_return,
        annualized_return=annualized_return,
        xirr_return=xirr_return,
        first_trade_date=first_trade_date,
        years_invested=years_invested,
    )
