"""
TraderLeagueWebhook — D2 sub-slice 14: league trade webhook extraction from runtime_workers.

Observability-only POST to Trader League; best-effort, non-capital path.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any

import requests

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured

logger = logging.getLogger(__name__)

DEFAULT_WEBHOOK_URL = "http://localhost:8000/webhook/trade"


class TraderLeagueWebhook:
    """Bounded owner for Trader League trade push (D2 sub-slice 14)."""

    def __init__(self, *, app: Any, webhook_url: str | None = None) -> None:
        self.app = app
        self.webhook_url = webhook_url or DEFAULT_WEBHOOK_URL
        self._logger = getattr(app, "logger", logger)

    def push(
        self,
        *,
        mode: str,
        symbol: str,
        signal: str | None,
        entry_price: float,
        exit_price: float,
        qty: int,
        pnl_dollars: float,
        reflection: dict | None = None,
        chart_base64: str | None = None,
        broker_fill_id: str | None = None,
        commission: float | None = None,
        slippage_points: float | None = None,
        fill_latency_ms: float | None = None,
        reconciliation_status: str | None = None,
    ) -> None:
        reflection_payload = dict(reflection or {})
        if any(
            value is not None
            for value in (broker_fill_id, commission, slippage_points, fill_latency_ms, reconciliation_status)
        ):
            reflection_payload.setdefault("reconciliation", {})
            reflection_payload["reconciliation"].update(
                {
                    "broker_fill_id": broker_fill_id,
                    "commission": commission,
                    "slippage_points": slippage_points,
                    "fill_latency_ms": fill_latency_ms,
                    "status": reconciliation_status,
                }
            )
        payload = {
            "participant": str(getattr(getattr(self.app, "config", None), "participant_id", None) or "LUMINA_Steve"),
            "mode": mode,
            "symbol": symbol,
            "signal": signal,
            "entry": entry_price,
            "exit": exit_price,
            "qty": qty,
            "pnl": pnl_dollars,
            "broker_fill_id": broker_fill_id,
            "commission": commission,
            "slippage_points": slippage_points,
            "fill_latency_ms": fill_latency_ms,
            "reconciliation_status": reconciliation_status,
            "reflection": reflection_payload,
            "chart_base64": chart_base64,
        }
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            response.raise_for_status()
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="INFO_PRINT_LEGACY",
                    message="📡 Trade gepusht naar Trader League",
                    context={"mode": mode},
                )
            )
        except Exception as exc:
            err = LuminaError(
                severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                code="RUNTIME_WEBHOOK_001",
                message=str(exc),
                context={"traceback": traceback.format_exc(), "mode": mode},
            )
            log_structured(err)
            self._logger.warning(f"League webhook failed: {exc}")
