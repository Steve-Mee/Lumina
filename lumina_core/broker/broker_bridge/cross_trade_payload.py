"""CrossTrade REST payload / account parsing helpers."""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.broker.broker_bridge.cross_trade_account import (
    ACCOUNT_AVAILABLE_MARGIN_KEYS,
    ACCOUNT_BALANCE_KEYS,
    ACCOUNT_EQUITY_KEYS,
    ACCOUNT_PNL_KEYS,
    CROSS_TRADE_BALANCE_WARN_ACCOUNTS,
)
from lumina_core.broker.broker_bridge.schemas import AccountInfo


def pick_float(payload: dict[str, Any], keys: tuple[str, ...]) -> float:
    for key in keys:
        if key not in payload:
            continue
        val = payload.get(key)
        if val is None:
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return 0.0


def account_payload_layers(root: dict[str, Any]) -> list[dict[str, Any]]:
    """Crosstrade often wraps balances inside ``item`` / ``data`` / list entries."""
    layers: list[dict[str, Any]] = []
    seen: set[int] = set()

    def add(d: dict[str, Any]) -> None:
        i = id(d)
        if i in seen:
            return
        seen.add(i)
        layers.append(d)

    add(root)
    for key in ("item", "data", "account", "result", "payload", "summary", "details"):
        node = root.get(key)
        if isinstance(node, dict):
            add(node)
        elif isinstance(node, list):
            for el in node[:8]:
                if isinstance(el, dict):
                    add(el)
    return layers


def parse_account_info_payload(
    data: dict[str, Any],
    *,
    account: str,
    logger: logging.Logger | None = None,
) -> AccountInfo:
    """Map nested Crosstrade account JSON into ``AccountInfo``."""
    layers = account_payload_layers(data)
    balance = 0.0
    equity = 0.0
    pnl = 0.0
    available_margin: float | None = None
    for layer in layers:
        if balance == 0.0:
            balance = pick_float(layer, ACCOUNT_BALANCE_KEYS)
        if equity == 0.0:
            equity = pick_float(layer, ACCOUNT_EQUITY_KEYS)
        if pnl == 0.0:
            pnl = pick_float(layer, ACCOUNT_PNL_KEYS)
        if available_margin is None:
            parsed_margin = pick_float(layer, ACCOUNT_AVAILABLE_MARGIN_KEYS)
            if parsed_margin > 0.0:
                available_margin = parsed_margin
    if equity == 0.0 and balance > 0.0:
        equity = balance

    if balance == 0.0 and equity == 0.0 and logger is not None:
        aid = str(account)
        if aid not in CROSS_TRADE_BALANCE_WARN_ACCOUNTS:
            CROSS_TRADE_BALANCE_WARN_ACCOUNTS.add(aid)
            item_preview = ""
            raw_item = data.get("item")
            if isinstance(raw_item, dict):
                item_preview = str(sorted(raw_item.keys()))[:200]
            elif raw_item is not None:
                item_preview = str(raw_item)[:220]
            logger.warning(
                "CrossTrade account REST has no parsable balance/equity for account=%s "
                "(parsed nested layers: item/data/account/…). top_keys=%s item_keys_or_preview=%s "
                "Set CROSSTRADE_ACCOUNT to the ID Crosstrade shows for your NinjaTrader demo. "
                "If this endpoint only returns metadata, balances may live on another route in your tenant.",
                aid,
                sorted(data.keys())[:28],
                item_preview or "<none>",
            )

    return AccountInfo(
        balance=balance,
        equity=equity,
        available_margin=available_margin,
        realized_pnl_today=pnl,
        raw=data,
    )
