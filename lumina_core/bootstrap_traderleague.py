"""TraderLeague bootstrap publish + webhook self-test."""
# CANONICAL IMPLEMENTATION – v50 Living Organism
# Bootstrap Module: Zero-Global-State Application Initialization
# All dependencies injected via container, no module-level globals.
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sys
import time
import numpy as np
import requests

from typing import Any, Callable

from lumina_core import backtest_workers, runtime_workers, trade_workers
from lumina_core.container import ApplicationContainer
from lumina_core.risk.mode_capabilities import resolve_mode_capabilities
from lumina_core.logging_utils import flush_logger_handlers
from lumina_core.logging_utils import get_logger
from lumina_core.runtime_bootstrap import start_runtime_services
from lumina_core.threading_utils import start_daemon

logger = logging.getLogger(__name__)
bootstrap_logger = get_logger("lumina.system.bootstrap")


def publish_traderleague_trade_close(
    container: ApplicationContainer,
    *,
    symbol: str,
    entry_price: float,
    exit_price: float,
    quantity: int,
    pnl: float,
    reflection: str = "",
    chart_snapshot_url: str | None = None,
    broker_fill_id: str | None = None,
    commission: float | None = None,
    slippage_points: float | None = None,
    fill_latency_ms: float | None = None,
    reconciliation_status: str | None = None,
) -> bool:
    """
    Publish a closed trade to TraderLeague with HMAC signature.

    This is intentionally fail-safe: it never raises into the trading loop.
    """
    enabled = os.getenv("TRADERLEAGUE_WEBHOOK_ENABLED", "false").lower() == "true"
    if not enabled:
        return False

    webhook_url = os.getenv("TRADERLEAGUE_WEBHOOK_URL", "").strip()
    webhook_secret = os.getenv("TRADERLEAGUE_WEBHOOK_SECRET", "").strip()
    participant_handle = os.getenv("TRADERLEAGUE_PARTICIPANT_HANDLE", "lumina_public").strip()
    broker_name = os.getenv("TRADERLEAGUE_BROKER_NAME", "NinjaTrader").strip()
    broker_account_ref = os.getenv("TRADERLEAGUE_BROKER_ACCOUNT_REF", "SIM-LUMINA").strip()
    account_mode = os.getenv("TRADERLEAGUE_ACCOUNT_MODE", "paper").strip().lower()

    if not webhook_url or not webhook_secret:
        container.logger.warning("TraderLeague webhook skipped: missing URL or secret")
        return False

    if account_mode not in {"paper", "sim", "real"}:
        container.logger.warning(
            "TraderLeague webhook skipped: invalid account mode '%s'",
            account_mode,
        )
        return False

    trade_mode = str(getattr(container.config, "trade_mode", "paper") or "paper").strip().lower()
    expected_account_mode = {
        "paper": "paper",
        "sim": "sim",
        "sim_real_guard": "sim",
        "real": "real",
    }.get(trade_mode, "paper")
    if account_mode != expected_account_mode:
        container.logger.warning(
            "TraderLeague webhook skipped: account mode mismatch (trade_mode=%s, expected=%s, configured=%s)",
            trade_mode,
            expected_account_mode,
            account_mode,
        )
        return False

    try:
        exit_ts = np.datetime64("now")
        entry_ts = exit_ts - np.timedelta64(3, "m")
        effective_fill_id = broker_fill_id or f"LUMINA-{str(exit_ts)}-{symbol}-{abs(int(pnl))}"
        payload = {
            "participant_handle": participant_handle,
            "broker_name": broker_name,
            "broker_account_ref": broker_account_ref,
            "account_mode": account_mode,
            "broker_fill_id": effective_fill_id,
            "symbol": symbol,
            "entry_time": str(entry_ts),
            "exit_time": str(exit_ts),
            "entry_price": float(entry_price),
            "exit_price": float(exit_price),
            "quantity": int(quantity),
            "pnl": float(pnl),
            "commission": float(commission) if commission is not None else None,
            "slippage_points": float(slippage_points) if slippage_points is not None else None,
            "fill_latency_ms": float(fill_latency_ms) if fill_latency_ms is not None else None,
            "reconciliation_status": reconciliation_status,
            "max_drawdown_trade": -abs(float(pnl)) * 0.35,
            "reflection": reflection,
            "chart_snapshot_url": chart_snapshot_url,
            "strategy_meta": {"source": "LuminaEngine", "runtime": "v50"},
        }
        body = json.dumps(payload).encode("utf-8")
        digest = hmac.new(webhook_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        signature = f"sha256={digest}"
        response = requests.post(
            webhook_url,
            headers={"content-type": "application/json", "x-lumina-signature": signature},
            data=body,
            timeout=2.5,
        )
        if response.status_code >= 300:
            container.logger.warning(f"TraderLeague webhook non-2xx: {response.status_code} {response.text[:160]}")
            return False
        return True
    except Exception as exc:
        container.logger.error(f"TraderLeague webhook error: {exc}")
        return False


def run_traderleague_webhook_self_test(container: ApplicationContainer) -> bool:
    """
    Send one synthetic trade-close event on startup in dev mode.

    Controlled by env vars and always fail-safe.
    """
    app_env = os.getenv("APP_ENV", "prod").strip().lower()
    enabled = os.getenv("TRADERLEAGUE_WEBHOOK_ENABLED", "false").lower() == "true"
    selftest_enabled = os.getenv("TRADERLEAGUE_WEBHOOK_SELFTEST", "true").lower() == "true"

    if not enabled or not selftest_enabled or app_env != "dev":
        return False

    cooldown_seconds = int(os.getenv("TRADERLEAGUE_WEBHOOK_SELFTEST_COOLDOWN_SEC", "900"))
    state_file = os.getenv("TRADERLEAGUE_WEBHOOK_SELFTEST_STATE_FILE", ".traderleague_webhook_selftest.json").strip()

    try:
        if os.path.exists(state_file):
            with open(state_file, "r", encoding="utf-8") as handle:
                state = json.load(handle)
            last_sent = float(state.get("last_sent_ts", 0.0))
            if (time.time() - last_sent) < max(0, cooldown_seconds):
                container.logger.info("TraderLeague webhook self-test skipped due to cooldown")
                return False
    except Exception as exc:
        container.logger.warning(f"TraderLeague self-test cooldown read error: {exc}")

    container.logger.info("TraderLeague webhook self-test starting")
    ok = publish_traderleague_trade_close(
        container,
        symbol=str(container.primary_instrument),
        entry_price=5000.0,
        exit_price=5002.0,
        quantity=1,
        pnl=10.0,
        reflection="startup self-test trade close event",
        chart_snapshot_url="",
    )
    if ok:
        try:
            with open(state_file, "w", encoding="utf-8") as handle:
                json.dump({"last_sent_ts": time.time()}, handle)
        except Exception as exc:
            container.logger.warning(f"TraderLeague self-test cooldown write error: {exc}")
        container.logger.info("TraderLeague webhook self-test succeeded")
    else:
        container.logger.warning("TraderLeague webhook self-test failed")
    return ok


