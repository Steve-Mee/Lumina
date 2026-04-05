"""Example: call TraderLeague webhook on each Lumina trade close."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime

import requests

TRADERLEAGUE_URL = "http://localhost:8000/api/v1/lumina/webhooks/trade-close"
WEBHOOK_SHARED_SECRET = "replace_me"


def _sign(payload_bytes: bytes) -> str:
    digest = hmac.new(WEBHOOK_SHARED_SECRET.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def send_trade_close(*, participant_handle: str, broker_name: str, broker_account_ref: str, account_mode: str,
                     broker_fill_id: str, symbol: str, entry_time: datetime, exit_time: datetime,
                     entry_price: float, exit_price: float, quantity: float, pnl: float,
                     max_drawdown_trade: float, reflection: str, chart_snapshot_url: str | None = None) -> None:
    payload = {
        "participant_handle": participant_handle,
        "broker_name": broker_name,
        "broker_account_ref": broker_account_ref,
        "account_mode": account_mode,
        "broker_fill_id": broker_fill_id,
        "symbol": symbol,
        "entry_time": entry_time.isoformat(),
        "exit_time": exit_time.isoformat(),
        "entry_price": entry_price,
        "exit_price": exit_price,
        "quantity": quantity,
        "pnl": pnl,
        "max_drawdown_trade": max_drawdown_trade,
        "reflection": reflection,
        "chart_snapshot_url": chart_snapshot_url,
        "strategy_meta": {"source": "LuminaEngine"},
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "content-type": "application/json",
        "x-lumina-signature": _sign(body),
    }
    response = requests.post(TRADERLEAGUE_URL, headers=headers, data=body, timeout=5)
    response.raise_for_status()
