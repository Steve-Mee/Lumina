"""CrossTrade REST account field aliases and warn-once state."""

from __future__ import annotations

# One WARNING per account per process when REST returns no parsable balance/equity (avoid log spam).
CROSS_TRADE_BALANCE_WARN_ACCOUNTS: set[str] = set()

ACCOUNT_BALANCE_KEYS = (
    "balance",
    "cashBalance",
    "cash_balance",
    "availableBalance",
    "available_balance",
    "availableFunds",
    "netCash",
    "net_cash",
    "cashValue",
    "totalCashValue",
)
ACCOUNT_EQUITY_KEYS = (
    "equity",
    "totalEquity",
    "total_equity",
    "netLiquidation",
    "net_liquidation",
    "accountEquity",
    "account_equity",
    "netLiquidationValue",
    "total_account_value",
)
ACCOUNT_PNL_KEYS = (
    "realizedPnlToday",
    "realized_pnl_today",
    "realizedPnl",
    "dayPnl",
    "realizedDayPnl",
)
ACCOUNT_AVAILABLE_MARGIN_KEYS = (
    "availableMargin",
    "available_margin",
    "availableFunds",
    "available_funds",
    "availableBalance",
    "available_balance",
    "buyingPower",
    "buying_power",
    "excessLiquidity",
    "excess_liquidity",
    "maintenanceExcess",
)
