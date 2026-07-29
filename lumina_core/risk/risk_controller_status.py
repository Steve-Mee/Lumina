"""Regime/status telemetry helpers for HardRiskController.

Extracted from risk_controller for Wave B LOC hygiene. Behavior unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
import traceback
from typing import Any

import numpy as np

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured

_HANDLED_RISK_EXCEPTIONS = (
    AttributeError,
    ImportError,
    IndexError,
    KeyError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RiskControllerStatusMixin:
    """Portfolio return series + regime history status helpers."""

    state: Any
    _active_limits: Any

    def _portfolio_return_series(self) -> list[float]:
        window = max(20, int(self._active_limits.var_es_window))
        returns: list[float] = []
        for trade in list(self.state.trade_history)[-window:]:
            pnl = float(trade.get("pnl", 0.0) or 0.0)
            risk_taken = float(trade.get("risk_taken", 0.0) or 0.0)
            denom = max(abs(risk_taken), 1.0)
            returns.append(pnl / denom)
        return returns

    def record_regime_snapshot(self, snapshot: dict[str, Any] | None) -> None:
        if not isinstance(snapshot, dict):
            return
        label = str(snapshot.get("label", self.state.active_regime) or self.state.active_regime).upper()
        features = snapshot.get("features", {}) if isinstance(snapshot.get("features", {}), dict) else {}
        self.state.regime_history.append(
            {
                "ts": _utcnow().isoformat(),
                "label": label,
                "risk_state": str(snapshot.get("risk_state", "NORMAL") or "NORMAL").upper(),
                "realized_vol_ratio": float(features.get("realized_vol_ratio", 1.0) or 1.0),
            }
        )

    def record_regime_detector_history(self, *, detector: Any, market_df: Any, instrument: str) -> int:
        if detector is None or market_df is None:
            return 0
        if not all(hasattr(market_df, attr) for attr in ("tail", "reset_index", "iloc", "columns")):
            return 0
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        try:
            columns = set(str(col) for col in list(market_df.columns))
        except _HANDLED_RISK_EXCEPTIONS as _exc:
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RISK_REGIME_HISTORY_004",
                    message=str(_exc),
                    context={"traceback": traceback.format_exc()},
                )
            )
            return 0
        if not required.issubset(columns):
            return 0

        try:
            anchor = str(market_df.iloc[-1].get("timestamp", "") or "")
        except _HANDLED_RISK_EXCEPTIONS as _exc:
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RISK_REGIME_HISTORY_005",
                    message=str(_exc),
                    context={"traceback": traceback.format_exc()},
                )
            )
            return 0
        if anchor and anchor == self.state.regime_detector_last_anchor:
            return 0

        lookback = max(20, int(getattr(detector, "lookback_bars", 120) or 120))
        stride = max(1, min(10, lookback // 12))
        max_windows = 300
        tail_size = max(lookback + 2, lookback + (max_windows * stride))
        try:
            rows = market_df.tail(tail_size).reset_index(drop=True)
        except _HANDLED_RISK_EXCEPTIONS as _exc:
            log_structured(
                LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_LEARNING,
                    code="RISK_REGIME_HISTORY_006",
                    message=str(_exc),
                    context={"traceback": traceback.format_exc()},
                )
            )
            return 0
        if len(rows) <= lookback:
            return 0

        last_ts = ""
        if self.state.regime_detector_history:
            try:
                last_ts = str(self.state.regime_detector_history[-1].get("ts", "") or "")
            except _HANDLED_RISK_EXCEPTIONS as _exc:
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="RISK_REGIME_HISTORY_007",
                        message=str(_exc),
                        context={"traceback": traceback.format_exc()},
                    )
                )
                last_ts = ""

        appended = 0
        for end_idx in range(lookback, len(rows), stride):
            window = rows.iloc[: end_idx + 1]
            try:
                snapshot = detector.detect(window, instrument=str(instrument))
            except _HANDLED_RISK_EXCEPTIONS as _exc:
                log_structured(
                    LuminaError(
                        severity=ErrorSeverity.RECOVERABLE_LEARNING,
                        code="RISK_REGIME_DETECT_008",
                        message=str(_exc),
                        context={"traceback": traceback.format_exc()},
                    )
                )
                continue
            label = str(getattr(snapshot, "label", self.state.active_regime) or self.state.active_regime).upper()
            risk_state = str(getattr(snapshot, "risk_state", "NORMAL") or "NORMAL").upper()
            features = getattr(snapshot, "features", {}) or {}
            features = features if isinstance(features, dict) else {}
            ts = str(getattr(snapshot, "timestamp", "") or window.iloc[-1].get("timestamp", ""))
            if last_ts and ts and ts <= last_ts:
                continue

            close_now = float(window.iloc[-1].get("close", 0.0) or 0.0)
            close_prev = float(window.iloc[-2].get("close", close_now) or close_now)
            ret = 0.0 if abs(close_prev) < 1e-9 else (close_now - close_prev) / abs(close_prev)
            self.state.regime_detector_history.append(
                {
                    "ts": ts,
                    "label": label,
                    "risk_state": risk_state,
                    "realized_vol_ratio": float(features.get("realized_vol_ratio", 1.0) or 1.0),
                    "return_pct": float(np.clip(ret, -0.95, 0.95)),
                }
            )
            last_ts = ts
            appended += 1

        if anchor:
            self.state.regime_detector_last_anchor = anchor
        return appended



__all__ = ["RiskControllerStatusMixin"]
