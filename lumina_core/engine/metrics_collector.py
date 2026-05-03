from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
import pandas as pd
import plotly.figure_factory as ff
import time


class MetricsCollectorProtocol(Protocol):
    blackboard_health_history: deque[dict[str, float | str]]

    def update_performance_log(self, trade_data: dict[str, Any]) -> None: ...

    def generate_strategy_heatmap(self) -> Any: ...

    def generate_performance_summary(self) -> dict[str, Any]: ...

    def collect_blackboard_health_state(self) -> dict[str, Any]: ...

    def record_blackboard_health_sample(self, health: dict[str, Any]) -> None: ...

    def classify_blackboard_health(
        self,
        *,
        blackboard_enabled: bool,
        meta_enabled: bool,
        publish_latency: float,
        reject_total: float,
        drop_total: float,
        sub_error_total: float,
        latest_conf: float,
        has_execution_event: bool,
    ) -> tuple[str, str, str]: ...

    @staticmethod
    def sum_metric(snapshot: dict[str, Any], metric_name: str, *, labels: dict[str, str] | None = None) -> float: ...


@dataclass(slots=True)
class MetricsCollector:
    engine: Any
    blackboard_health_history: deque[dict[str, float | str]] = field(init=False)

    def __post_init__(self) -> None:
        if self.engine is None:
            raise ValueError("DashboardService requires a LuminaEngine")
        history_points = max(5, int(getattr(self.engine.config, "blackboard_health_trend_points", 30) or 30))
        self.blackboard_health_history = deque(maxlen=history_points)

    def update_performance_log(self, trade_data: dict[str, Any]) -> None:
        self.engine.update_performance_log(trade_data)

    def generate_strategy_heatmap(self) -> Any:
        performance_log = self.engine.performance_log
        if len(performance_log) < 20:
            return None

        df_perf = pd.DataFrame(performance_log)
        pivot = (
            df_perf.groupby(["chosen_strategy", "regime"])["pnl"]
            .agg(["mean", "count", lambda x: (x > 0).mean()])
            .reset_index()
        )
        pivot.columns = ["strategy", "regime", "avg_pnl", "trades", "winrate"]

        strategies = pivot["strategy"].unique()
        regimes = pivot["regime"].unique()
        z = np.zeros((len(strategies), len(regimes)))
        for i, strat in enumerate(strategies):
            for j, reg in enumerate(regimes):
                row = pivot[(pivot["strategy"] == strat) & (pivot["regime"] == reg)]
                z[i, j] = row["winrate"].iloc[0] if not row.empty else 0.5

        fig = ff.create_annotated_heatmap(
            z,
            x=list(regimes),
            y=list(strategies),
            annotation_text=np.round(z, 2),
            colorscale="RdYlGn",
            showscale=True,
        )
        fig.update_layout(title="Strategy Heatmap – Winrate per Regime", template="plotly_dark")
        return fig

    def generate_performance_summary(self) -> dict[str, Any]:
        performance_log = self.engine.performance_log
        if not performance_log:
            return {"sharpe": 0, "winrate": 0, "trades": 0}

        pnls = [t.get("pnl", 0) for t in performance_log if t.get("pnl", 0) != 0]
        if not pnls:
            return {"sharpe": 0, "winrate": 0, "trades": 0}

        sharpe = (float(np.mean(pnls)) / (float(np.std(pnls)) + 1e-8)) * float(np.sqrt(252))
        winrate = float(np.mean(np.array(pnls) > 0))
        return {
            "sharpe": round(sharpe, 2),
            "winrate": round(winrate, 3),
            "trades": len(pnls),
            "avg_pnl": round(float(np.mean(pnls)), 1),
        }

    @staticmethod
    def _sum_metric(snapshot: dict[str, Any], metric_name: str, *, labels: dict[str, str] | None = None) -> float:
        total = 0.0
        expected = {str(k): str(v) for k, v in (labels or {}).items()}
        for payload in snapshot.values():
            if not isinstance(payload, dict):
                continue
            if str(payload.get("name", "")) != metric_name:
                continue
            observed = {str(k): str(v) for k, v in dict(payload.get("labels", {}) or {}).items()}
            if any(observed.get(key) != value for key, value in expected.items()):
                continue
            total += float(payload.get("value", 0.0) or 0.0)
        return total

    def _classify_blackboard_health(
        self,
        *,
        blackboard_enabled: bool,
        meta_enabled: bool,
        publish_latency: float,
        reject_total: float,
        drop_total: float,
        sub_error_total: float,
        latest_conf: float,
        has_execution_event: bool,
    ) -> tuple[str, str, str]:
        red_latency = float(getattr(self.engine.config, "blackboard_health_latency_red_ms", 1000.0) or 1000.0)
        amber_latency = float(getattr(self.engine.config, "blackboard_health_latency_amber_ms", 250.0) or 250.0)
        min_confidence = float(getattr(self.engine.config, "blackboard_health_min_confidence", 0.80) or 0.80)
        if not blackboard_enabled:
            return ("RED", "#ff6b6b", "blackboard disabled")
        if reject_total > 0:
            return ("RED", "#ff6b6b", "unauthorized or malformed events rejected")
        if sub_error_total > 0:
            return ("RED", "#ff6b6b", "subscriber errors detected")
        if publish_latency > red_latency:
            return ("RED", "#ff6b6b", f"publish latency above {red_latency:.0f} ms")
        if has_execution_event and latest_conf < min_confidence:
            return ("RED", "#ff6b6b", f"latest aggregate confidence below {min_confidence:.2f}")
        if drop_total > 0:
            return ("AMBER", "#ffc857", "non-critical telemetry drops detected")
        if publish_latency > amber_latency:
            return ("AMBER", "#ffc857", f"publish latency above {amber_latency:.0f} ms")
        if not meta_enabled:
            return ("AMBER", "#ffc857", "meta-orchestrator not enabled")
        if not has_execution_event:
            return ("AMBER", "#ffc857", "no execution aggregate observed yet")
        return ("GREEN", "#00ff88", "blackboard and orchestrator healthy")

    def _collect_blackboard_health_state(self) -> dict[str, Any]:
        obs = getattr(self.engine, "observability_service", None)
        snapshot = obs.snapshot() if (obs is not None and hasattr(obs, "snapshot")) else {}
        publish_latency = self._sum_metric(snapshot, "lumina_blackboard_publish_latency_ms")
        reject_total = self._sum_metric(snapshot, "lumina_blackboard_reject_total")
        drop_total = self._sum_metric(snapshot, "lumina_blackboard_drop_total")
        sub_error_total = self._sum_metric(snapshot, "lumina_blackboard_subscription_error_total")

        blackboard = getattr(self.engine, "blackboard", None)
        meta_agent = getattr(self.engine, "meta_agent_orchestrator", None)
        execution_event = (
            blackboard.latest("execution.aggregate")
            if (blackboard is not None and hasattr(blackboard, "latest"))
            else None
        )
        has_execution_event = execution_event is not None
        latest_conf = float(getattr(execution_event, "confidence", 0.0) or 0.0) if execution_event is not None else 0.0
        latest_seq = int(getattr(execution_event, "sequence", 0) or 0) if execution_event is not None else 0
        status, status_color, reason = self._classify_blackboard_health(
            blackboard_enabled=blackboard is not None,
            meta_enabled=meta_agent is not None,
            publish_latency=publish_latency,
            reject_total=reject_total,
            drop_total=drop_total,
            sub_error_total=sub_error_total,
            latest_conf=latest_conf,
            has_execution_event=has_execution_event,
        )
        return {
            "blackboard_enabled": blackboard is not None,
            "meta_enabled": meta_agent is not None,
            "publish_latency": publish_latency,
            "reject_total": reject_total,
            "drop_total": drop_total,
            "sub_error_total": sub_error_total,
            "latest_conf": latest_conf,
            "latest_seq": latest_seq,
            "has_execution_event": has_execution_event,
            "status": status,
            "status_color": status_color,
            "reason": reason,
        }

    def _record_blackboard_health_sample(self, health: dict[str, Any]) -> None:
        self.blackboard_health_history.append(
            {
                "ts": time.strftime("%H:%M:%S"),
                "publish_latency": float(health.get("publish_latency", 0.0) or 0.0),
                "reject_total": float(health.get("reject_total", 0.0) or 0.0),
                "drop_total": float(health.get("drop_total", 0.0) or 0.0),
                "sub_error_total": float(health.get("sub_error_total", 0.0) or 0.0),
                "status": str(health.get("status", "AMBER") or "AMBER"),
                "status_color": str(health.get("status_color", "#ffc857") or "#ffc857"),
            }
        )

    @staticmethod
    def sum_metric(snapshot: dict[str, Any], metric_name: str, *, labels: dict[str, str] | None = None) -> float:
        return MetricsCollector._sum_metric(snapshot, metric_name, labels=labels)

    def classify_blackboard_health(
        self,
        *,
        blackboard_enabled: bool,
        meta_enabled: bool,
        publish_latency: float,
        reject_total: float,
        drop_total: float,
        sub_error_total: float,
        latest_conf: float,
        has_execution_event: bool,
    ) -> tuple[str, str, str]:
        return self._classify_blackboard_health(
            blackboard_enabled=blackboard_enabled,
            meta_enabled=meta_enabled,
            publish_latency=publish_latency,
            reject_total=reject_total,
            drop_total=drop_total,
            sub_error_total=sub_error_total,
            latest_conf=latest_conf,
            has_execution_event=has_execution_event,
        )

    def collect_blackboard_health_state(self) -> dict[str, Any]:
        return self._collect_blackboard_health_state()

    def record_blackboard_health_sample(self, health: dict[str, Any]) -> None:
        self._record_blackboard_health_sample(health)
