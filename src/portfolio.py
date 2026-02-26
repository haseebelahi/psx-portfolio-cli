"""Pure portfolio calculation logic — no I/O."""
from dataclasses import dataclass
from datetime import date


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
    first_trade_date: date | None
    years_invested: float


def compute_positions(trades: list[dict], prices: dict[str, float]) -> list[Position]:
    holdings: dict[str, dict] = {}

    for t in trades:
        sym = t["symbol"]
        if sym not in holdings:
            holdings[sym] = {"buy_shares": 0, "sell_shares": 0, "buy_cost": 0.0}
        if t["mode"] == "BUY":
            holdings[sym]["buy_shares"] += t["shares"]
            holdings[sym]["buy_cost"] += t["shares"] * t["trade_price"]
        elif t["mode"] == "SELL":
            holdings[sym]["sell_shares"] += t["shares"]

    positions: list[Position] = []
    for sym, data in holdings.items():
        current_shares = data["buy_shares"] - data["sell_shares"]
        if current_shares <= 0:
            continue

        avg_buy = data["buy_cost"] / data["buy_shares"] if data["buy_shares"] else 0.0
        cur_price = prices.get(sym, avg_buy)
        market_val = current_shares * cur_price
        cost = current_shares * avg_buy
        pnl = market_val - cost
        pnl_pct = (pnl / cost * 100) if cost else 0.0

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

    cash_balance = total_deposits + sell_proceeds + total_dividends - buy_cost
    market_value = sum(p.market_value for p in positions)
    current_invested = sum(p.cost_basis for p in positions)
    nlv = cash_balance + market_value
    pnl = nlv - total_deposits
    absolute_return = (pnl / total_deposits * 100) if total_deposits else 0.0

    first_trade_date = None
    years_invested = 0.0
    annualized_return = 0.0

    if trades:
        first_trade_date = min(date.fromisoformat(t["date"]) for t in trades)
        days = (date.today() - first_trade_date).days
        years_invested = days / 365.25
        if years_invested > 0 and total_deposits > 0:
            annualized_return = ((nlv / total_deposits) ** (1 / years_invested) - 1) * 100

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
        first_trade_date=first_trade_date,
        years_invested=years_invested,
    )
