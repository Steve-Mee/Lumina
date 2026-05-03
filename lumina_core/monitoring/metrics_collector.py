# CANONICAL IMPLEMENTATION – v50 Living Organism
"""Thread-safe in-memory metrics store for Lumina v50.

- Counter : monotonically increasing value (resets on process restart)
- Gauge   : current point-in-time value (can go up or down)
- Histogram: sliding window with mean, p50, p95, p99 percentiles

Prometheus text exposition format is generated in-process;
no prometheus_client library required.

NullMetricsCollector is the zero-overhead variant used when
monitoring.enabled = false in config.yaml.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass
class _MetricEntry:
    name: str
    type_: MetricType
    help_: str
    value: float = 0.0
    labels: dict[str, str] = field(default_factory=dict)
    updated_at: float = field(default_factory=time.time)
    # Histogram: keep a sliding window for percentile computation
    _window: deque[float] = field(
        default_factory=lambda: deque(maxlen=500),
        repr=False,
        compare=False,
    )


def _label_key(name: str, labels: dict[str, str]) -> str:
    """Build a unique string key for (metric_name, label_set)."""
    if not labels:
        return name
    pairs = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    return f"{name}{{{pairs}}}"


class MetricsCollector:
    """Thread-safe in-memory collector with Prometheus export and optional SQLite sink."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._store: dict[str, _MetricEntry] = {}
        self._lock = threading.Lock()
        self._db_path = db_path
        if db_path is not None:
            self._init_db(db_path)

    # ── write API ──────────────────────────────────────────────────────────────

    def inc(
        self,
        name: str,
        *,
        labels: dict[str, str] | None = None,
        help_: str = "",
        amount: float = 1.0,
    ) -> None:
        """Increment a counter by *amount* (default 1)."""
        key = _label_key(name, labels or {})
        with self._lock:
            if key not in self._store:
                self._store[key] = _MetricEntry(
                    name=name,
                    type_=MetricType.COUNTER,
                    help_=help_,
                    labels=labels or {},
                )
            entry = self._store[key]
            entry.value += amount
            entry.updated_at = time.time()

    def set(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
        help_: str = "",
    ) -> None:
        """Set a gauge to *value*."""
        key = _label_key(name, labels or {})
        with self._lock:
            if key not in self._store:
                self._store[key] = _MetricEntry(
                    name=name,
                    type_=MetricType.GAUGE,
                    help_=help_,
                    labels=labels or {},
                )
            entry = self._store[key]
            entry.value = value
            entry.updated_at = time.time()

    def observe(
        self,
        name: str,
        value: float,
        *,
        labels: dict[str, str] | None = None,
        help_: str = "",
    ) -> None:
        """Append *value* to a histogram window and update running mean."""
        key = _label_key(name, labels or {})
        with self._lock:
            if key not in self._store:
                self._store[key] = _MetricEntry(
                    name=name,
                    type_=MetricType.HISTOGRAM,
                    help_=help_,
                    labels=labels or {},
                )
            entry = self._store[key]
            entry._window.append(value)
            entry.value = sum(entry._window) / len(entry._window)
            entry.updated_at = time.time()

    # ── read API ───────────────────────────────────────────────────────────────

    def get(self, name: str, labels: dict[str, str] | None = None) -> float:
        key = _label_key(name, labels or {})
        with self._lock:
            entry = self._store.get(key)
            return entry.value if entry else 0.0

    def get_percentile(
        self,
        name: str,
        p: float,
        labels: dict[str, str] | None = None,
    ) -> float:
        """Return the *p*-th percentile of a histogram (e.g. p=0.95 → p95)."""
        key = _label_key(name, labels or {})
        with self._lock:
            entry = self._store.get(key)
            if entry is None or not entry._window:
                return 0.0
            sorted_data = sorted(entry._window)
            idx = max(0, int(len(sorted_data) * p) - 1)
            return sorted_data[idx]

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-serialisable snapshot of every metric."""
        with self._lock:
            out: dict[str, Any] = {}
            for key, entry in self._store.items():
                record: dict[str, Any] = {
                    "name": entry.name,
                    "type": entry.type_.value,
                    "value": round(entry.value, 6),
                    "labels": entry.labels,
                    "updated_at": entry.updated_at,
                }
                if entry.type_ == MetricType.HISTOGRAM and entry._window:
                    sd = sorted(entry._window)
                    n = len(sd)
                    record["p50"] = round(sd[max(0, int(n * 0.50) - 1)], 3)
                    record["p95"] = round(sd[max(0, int(n * 0.95) - 1)], 3)
                    record["p99"] = round(sd[max(0, int(n * 0.99) - 1)], 3)
                    record["count"] = n
                out[key] = record
        return out

    # ── Prometheus text format ─────────────────────────────────────────────────

    def prometheus_text(self) -> str:
        """Return all metrics in Prometheus text exposition format (v0.0.4)."""
        lines: list[str] = []
        emitted_help: set[str] = set()
        ts_ms = int(time.time() * 1000)

        with self._lock:
            # Group by base metric name so HELP/TYPE appear once per family.
            by_name: dict[str, list[_MetricEntry]] = {}
            for entry in self._store.values():
                by_name.setdefault(entry.name, []).append(entry)

            for metric_name, entries in sorted(by_name.items()):
                first = entries[0]
                if metric_name not in emitted_help:
                    if first.help_:
                        lines.append(f"# HELP {metric_name} {first.help_}")
                    lines.append(f"# TYPE {metric_name} {first.type_.value}")
                    emitted_help.add(metric_name)

                for entry in entries:
                    label_str = ""
                    if entry.labels:
                        pairs = ",".join(f'{k}="{v}"' for k, v in sorted(entry.labels.items()))
                        label_str = f"{{{pairs}}}"

                    lines.append(f"{metric_name}{label_str} {entry.value} {ts_ms}")

                    if entry.type_ == MetricType.HISTOGRAM and entry._window:
                        sd = sorted(entry._window)
                        n = len(sd)
                        extra_labels = ",".join(f'{k}="{v}"' for k, v in sorted(entry.labels.items()))
                        extra = f",{extra_labels}" if entry.labels else ""
                        for pct, idx in [
                            ("0.5", max(0, int(n * 0.50) - 1)),
                            ("0.95", max(0, int(n * 0.95) - 1)),
                            ("0.99", max(0, int(n * 0.99) - 1)),
                        ]:
                            lines.append(f'{metric_name}_bucket{{le="{pct}"{extra}}} {sd[idx]} {ts_ms}')
                        lines.append(f"{metric_name}_count{label_str} {n} {ts_ms}")
                        lines.append(f"{metric_name}_sum{label_str} {sum(entry._window):.4f} {ts_ms}")

        lines.append("")
        return "\n".join(lines)

    # ── SQLite persistence ─────────────────────────────────────────────────────

    def _init_db(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(db_path))
        con.execute(
            """CREATE TABLE IF NOT EXISTS metrics (
               ts      REAL NOT NULL,
               name    TEXT NOT NULL,
               labels  TEXT NOT NULL,
               type    TEXT NOT NULL,
               value   REAL NOT NULL
            )"""
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_metrics_name_ts ON metrics(name, ts)")
        con.commit()
        con.close()

    def flush_to_sqlite(self) -> None:
        """Append current metric values to SQLite (non-blocking; errors are swallowed)."""
        if self._db_path is None:
            return
        ts = time.time()
        rows: list[tuple[float, str, str, str, float]] = []
        with self._lock:
            for entry in self._store.values():
                rows.append((ts, entry.name, json.dumps(entry.labels), entry.type_.value, entry.value))
        if not rows:
            return
        try:
            con = sqlite3.connect(str(self._db_path))
            con.executemany(
                "INSERT INTO metrics(ts, name, labels, type, value) VALUES (?,?,?,?,?)",
                rows,
            )
            con.commit()
            con.close()
        except Exception:
            logger.exception("MetricsCollector failed to persist metrics batch to SQLite")

    def query_history(
        self,
        metric_name: str,
        since_ts: float | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Retrieve historical rows from SQLite for a given metric name."""
        if self._db_path is None or not self._db_path.exists():
            return []
        try:
            con = sqlite3.connect(str(self._db_path))
            rows = con.execute(
                "SELECT ts, name, labels, type, value FROM metrics WHERE name=? AND ts>=? ORDER BY ts DESC LIMIT ?",
                (metric_name, since_ts or 0.0, limit),
            ).fetchall()
            con.close()
            return [
                {
                    "ts": r[0],
                    "name": r[1],
                    "labels": json.loads(r[2]),
                    "type": r[3],
                    "value": r[4],
                }
                for r in rows
            ]
        except Exception:
            logging.exception("Unhandled broad exception fallback in lumina_core/monitoring/metrics_collector.py:299")
            return []


# ── Zero-overhead null implementation ─────────────────────────────────────────


class NullMetricsCollector:
    """Drop-in replacement used when monitoring.enabled = false.

    Every method is a no-op with negligible runtime cost.
    """

    def inc(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def set(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def observe(self, *_args: Any, **_kwargs: Any) -> None:
        pass

    def get(self, *_args: Any, **_kwargs: Any) -> float:
        return 0.0

    def get_percentile(self, *_args: Any, **_kwargs: Any) -> float:
        return 0.0

    def snapshot(self) -> dict[str, Any]:
        return {}

    def prometheus_text(self) -> str:
        return "# monitoring disabled\n"

    def flush_to_sqlite(self) -> None:
        pass

    def query_history(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
        return []
