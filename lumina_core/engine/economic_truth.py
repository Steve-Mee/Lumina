from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class EconomicTruth:
    """Versioned observability ledger for PnL-related engine fields.

    Broker-confirmed **economic_pnl** for REAL reporting flows through
    `EconomicPnLService` / reconciler — not through this snapshot alone.
    Keys below mix account/broker fields with **internal runtime** sums; read names literally.
    """

    sequence: int = 0
    versions: list[dict[str, Any]] = field(default_factory=list)
    latest_by_source: dict[str, dict[str, Any]] = field(default_factory=dict)
    max_versions: int = 5000

    def record(self, source: str, value: float, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        self.sequence += 1
        event = {
            "version": int(self.sequence),
            "source": str(source),
            "value": float(value),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": dict(metadata or {}),
        }
        self.versions.append(event)
        self.latest_by_source[str(event["source"])] = event
        if len(self.versions) > int(self.max_versions):
            trim = len(self.versions) - int(self.max_versions)
            del self.versions[:trim]
        return event

    def version_all_pnl_sources(self, engine: Any) -> dict[str, float]:
        snapshot = {
            "open_pnl": float(getattr(engine, "open_pnl", 0.0) or 0.0),
            "realized_pnl_today": float(getattr(engine, "realized_pnl_today", 0.0) or 0.0),
            "sim_unrealized": float(getattr(engine, "sim_unrealized", 0.0) or 0.0),
            "last_realized_pnl_snapshot": float(getattr(engine, "last_realized_pnl_snapshot", 0.0) or 0.0),
            "equity_delta_observability": self._equity_delta(engine),
            "runtime_trade_log_pnl_sum_usd": self._trade_log_sum(engine),
            "runtime_pnl_history_close_sum_usd": self._pnl_history_sum(engine),
            "reconciliation_pending_expected_pnl_observability": self._reconciliation_pending_expected_pnl_observability(
                engine
            ),
        }
        metadata = {
            "trade_mode": str(getattr(getattr(engine, "config", None), "trade_mode", "unknown")),
            "pending_reconciliations": len(getattr(engine, "pending_trade_reconciliations", []) or []),
        }
        for source, value in snapshot.items():
            self.record(source=source, value=value, metadata=metadata)
        return snapshot

    def latest_value(self, source: str, default: float = 0.0) -> float:
        item = self.latest_by_source.get(str(source))
        if item is None:
            return float(default)
        return float(item.get("value", default) or default)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": int(self.sequence),
            "latest": {
                key: {
                    "version": int(value.get("version", 0)),
                    "value": float(value.get("value", 0.0) or 0.0),
                    "timestamp": str(value.get("timestamp", "")),
                    "metadata": dict(value.get("metadata", {})),
                }
                for key, value in self.latest_by_source.items()
            },
        }

    @staticmethod
    def _equity_delta(engine: Any) -> float:
        equity = list(getattr(engine, "equity_curve", []) or [])
        if len(equity) < 2:
            return 0.0
        return float(equity[-1] - equity[-2])

    @staticmethod
    def _trade_log_sum(engine: Any) -> float:
        total = 0.0
        for item in list(getattr(engine, "trade_log", []) or []):
            if isinstance(item, dict):
                total += float(item.get("pnl", 0.0) or 0.0)
        return float(total)

    @staticmethod
    def _pnl_history_sum(engine: Any) -> float:
        history = list(getattr(engine, "pnl_history", []) or [])
        return float(sum(float(x or 0.0) for x in history))

    @staticmethod
    def _reconciliation_pending_expected_pnl_observability(engine: Any) -> float:
        """Sum of ``expected_pnl`` on pending reconciliations — **not** economic truth (chart/snapshot hints)."""
        pending = list(getattr(engine, "pending_trade_reconciliations", []) or [])
        total = 0.0
        for item in pending:
            if isinstance(item, dict):
                total += float(item.get("expected_pnl", 0.0) or 0.0)
        return float(total)
