"""Brain-side Execution Fabric metrics (Prometheus-compatible via MetricsCollector)."""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any


class FabricClientMetrics:
    """Thread-safe client-side counters for Fabric place/cancel/RTT."""

    def __init__(self, *, window: int = 500) -> None:
        self._lock = threading.Lock()
        self.place_total = 0
        self.place_ok = 0
        self.place_error = 0
        self.cancel_total = 0
        self.flatten_total = 0
        self.connect_ok = 0
        self.connect_fail = 0
        self.disconnects = 0
        self.safety_alerts = 0
        self._rtt_ms: deque[float] = deque(maxlen=window)

    def record_place(self, *, ok: bool, rtt_ms: float | None = None) -> None:
        with self._lock:
            self.place_total += 1
            if ok:
                self.place_ok += 1
            else:
                self.place_error += 1
            if rtt_ms is not None and rtt_ms >= 0:
                self._rtt_ms.append(float(rtt_ms))

    def record_cancel(self) -> None:
        with self._lock:
            self.cancel_total += 1

    def record_flatten(self) -> None:
        with self._lock:
            self.flatten_total += 1

    def record_connect(self, *, ok: bool) -> None:
        with self._lock:
            if ok:
                self.connect_ok += 1
            else:
                self.connect_fail += 1

    def record_disconnect(self) -> None:
        with self._lock:
            self.disconnects += 1

    def record_safety_alert(self) -> None:
        with self._lock:
            self.safety_alerts += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            rtts = list(self._rtt_ms)
            return {
                "fabric_client_place_total": self.place_total,
                "fabric_client_place_ok": self.place_ok,
                "fabric_client_place_error": self.place_error,
                "fabric_client_cancel_total": self.cancel_total,
                "fabric_client_flatten_total": self.flatten_total,
                "fabric_client_connect_ok": self.connect_ok,
                "fabric_client_connect_fail": self.connect_fail,
                "fabric_client_disconnects": self.disconnects,
                "fabric_client_safety_alerts": self.safety_alerts,
                "fabric_client_rtt_ms_p50": _percentile(rtts, 0.50),
                "fabric_client_rtt_ms_p95": _percentile(rtts, 0.95),
                "fabric_client_rtt_ms_p99": _percentile(rtts, 0.99),
                "fabric_client_rtt_samples": len(rtts),
            }

    def publish_to_collector(self, collector: Any) -> None:
        """Best-effort push into lumina MetricsCollector if provided."""
        if collector is None:
            return
        snap = self.snapshot()
        try:
            for key, value in snap.items():
                if key.endswith("_total") or key.endswith("_ok") or key.endswith("_error") or key.endswith("_fail") or key.endswith("_disconnects") or key.endswith("_alerts") or key.endswith("_samples"):
                    if hasattr(collector, "set"):
                        collector.set(key, float(value), help_=f"Fabric client metric {key}")
                elif "rtt_ms" in key and hasattr(collector, "set"):
                    collector.set(key, float(value), help_=f"Fabric client RTT {key}")
        except Exception:
            pass


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(max(0, min(len(ordered) - 1, round(p * (len(ordered) - 1)))))
    return float(ordered[idx])


class _Timer:
    __slots__ = ("_start",)

    def __init__(self) -> None:
        self._start = time.perf_counter()

    def ms(self) -> float:
        return (time.perf_counter() - self._start) * 1000.0
