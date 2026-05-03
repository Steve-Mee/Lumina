from __future__ import annotations

import json
import logging
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

logger = logging.getLogger(__name__)


ROOT = Path(__file__).resolve().parents[2]
LOG_CSV = ROOT / "logs" / "lumina_full_log.csv"
FILL_AUDIT = ROOT / "logs" / "trade_fill_audit.jsonl"
OUT_DIR = ROOT / "state"
CURRENT_OUT = OUT_DIR / "build_metrics_snapshot.json"
LATEST_OUT = OUT_DIR / "build_metrics_snapshot_latest.json"

DEFAULT_THRESHOLDS = {
    "order_acceptance_rate_min": 0.50,
    "inference_fallback_rate_max": 0.60,
    "reconcile_latency_p95_ms_max": 5000.0,
}


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        logging.exception("Unhandled broad exception fallback in scripts/validation/build_metrics_snapshot.py:35")
        return ""


def _parse_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in _read_text(path).splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def _extract_order_metrics(log_text: str) -> tuple[float, dict[str, int], int, int]:
    success = len(re.findall(r"\b(?:REAL|SIM)_ORDER_SUCCESS\b", log_text))
    blocked = len(re.findall(r"\bplace_order blocked by\b", log_text))
    failed = len(re.findall(r"\bOrder failed\b", log_text))
    attempts = success + blocked + failed
    acceptance_rate = (success / attempts) if attempts > 0 else 1.0

    reason_counts: Counter[str] = Counter()
    for match in re.finditer(r"place_order blocked by [^:]+: (?P<reason>.+)", log_text):
        reason = match.group("reason").strip()
        reason_counts[reason] += 1

    return acceptance_rate, dict(reason_counts), attempts, success


def _extract_inference_metrics(log_text: str) -> tuple[float, int, int]:
    requests = len(re.findall(r"\bINFERENCE,", log_text))
    fallback = len(
        re.findall(
            r"All inference providers failed|FAST_PATH_ONLY enabled|LOCAL_INFERENCE_GATE,provider=vllm,action=skip",
            log_text,
        )
    )
    rate = (fallback / requests) if requests > 0 else 0.0
    return rate, requests, fallback


def _extract_reconcile_latency(rows: list[dict[str, Any]]) -> tuple[float, float, int]:
    values: list[float] = []
    for row in rows:
        value = row.get("fill_latency_ms")
        if value is None:
            details = row.get("details")
            if isinstance(details, dict):
                value = details.get("fill_latency_ms")
        try:
            if value is not None:
                values.append(float(value))
        except (TypeError, ValueError):
            continue

    if not values:
        return 0.0, 0.0, 0

    values_sorted = sorted(values)
    p50 = median(values_sorted)
    idx = int(round(0.95 * (len(values_sorted) - 1)))
    p95 = values_sorted[max(0, min(idx, len(values_sorted) - 1))]
    return float(p50), float(p95), len(values_sorted)


def _load_previous() -> dict[str, Any] | None:
    if not LATEST_OUT.exists():
        return None
    try:
        data = json.loads(LATEST_OUT.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        logging.exception("Unhandled broad exception fallback in scripts/validation/build_metrics_snapshot.py:113")
        return None


def _thresholds() -> dict[str, float]:
    threshold_path = os.getenv("LUMINA_METRICS_THRESHOLDS", "").strip()
    if threshold_path:
        try:
            data = json.loads(Path(threshold_path).read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged = dict(DEFAULT_THRESHOLDS)
                for k, v in data.items():
                    merged[str(k)] = float(v)
                return merged
        except Exception:
            logger.exception("build_metrics_snapshot failed to load custom thresholds; using defaults")
    return dict(DEFAULT_THRESHOLDS)


def _breaches(snapshot: dict[str, Any], limits: dict[str, float]) -> list[str]:
    breaches: list[str] = []
    if float(snapshot["order_acceptance_rate"]) < float(limits["order_acceptance_rate_min"]):
        breaches.append(
            f"order_acceptance_rate {snapshot['order_acceptance_rate']:.3f} < {limits['order_acceptance_rate_min']:.3f}"
        )
    if float(snapshot["inference_fallback_rate"]) > float(limits["inference_fallback_rate_max"]):
        breaches.append(
            f"inference_fallback_rate {snapshot['inference_fallback_rate']:.3f} > {limits['inference_fallback_rate_max']:.3f}"
        )
    if float(snapshot["reconcile_latency_p95_ms"]) > float(limits["reconcile_latency_p95_ms_max"]):
        breaches.append(
            f"reconcile_latency_p95_ms {snapshot['reconcile_latency_p95_ms']:.1f} > {limits['reconcile_latency_p95_ms_max']:.1f}"
        )
    return breaches


def main() -> int:
    log_text = _read_text(LOG_CSV)
    fill_rows = _parse_jsonl(FILL_AUDIT)

    order_acceptance_rate, block_reason_distribution, order_attempts, order_successes = _extract_order_metrics(log_text)
    inference_fallback_rate, inference_requests, inference_fallbacks = _extract_inference_metrics(log_text)
    rec_p50, rec_p95, rec_samples = _extract_reconcile_latency(fill_rows)

    snapshot = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "order_acceptance_rate": round(float(order_acceptance_rate), 6),
        "order_attempts": int(order_attempts),
        "order_successes": int(order_successes),
        "block_reason_distribution": block_reason_distribution,
        "inference_fallback_rate": round(float(inference_fallback_rate), 6),
        "inference_requests": int(inference_requests),
        "inference_fallbacks": int(inference_fallbacks),
        "reconcile_latency_p50_ms": round(float(rec_p50), 3),
        "reconcile_latency_p95_ms": round(float(rec_p95), 3),
        "reconcile_latency_samples": int(rec_samples),
        "sources": {
            "log_csv": str(LOG_CSV),
            "fill_audit": str(FILL_AUDIT),
        },
    }

    previous = _load_previous()
    snapshot["previous_timestamp_utc"] = previous.get("timestamp_utc") if isinstance(previous, dict) else None
    if isinstance(previous, dict):
        snapshot["delta"] = {
            "order_acceptance_rate": round(
                float(snapshot["order_acceptance_rate"]) - float(previous.get("order_acceptance_rate", 0.0)), 6
            ),
            "inference_fallback_rate": round(
                float(snapshot["inference_fallback_rate"]) - float(previous.get("inference_fallback_rate", 0.0)), 6
            ),
            "reconcile_latency_p95_ms": round(
                float(snapshot["reconcile_latency_p95_ms"]) - float(previous.get("reconcile_latency_p95_ms", 0.0)), 3
            ),
        }
    else:
        snapshot["delta"] = None

    limits = _thresholds()
    snapshot["thresholds"] = limits
    snapshot["breaches"] = _breaches(snapshot, limits)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_OUT.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    LATEST_OUT.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    print(f"Metrics snapshot written: {CURRENT_OUT}")
    print(f"Order acceptance rate: {snapshot['order_acceptance_rate']:.3f} (attempts={order_attempts})")
    print(f"Inference fallback rate: {snapshot['inference_fallback_rate']:.3f} (requests={inference_requests})")
    print(
        "Reconcile latency p95 (ms): "
        f"{snapshot['reconcile_latency_p95_ms']:.1f} (samples={snapshot['reconcile_latency_samples']})"
    )

    fail_on_breach = os.getenv("LUMINA_METRICS_FAIL_ON_BREACH", "false").strip().lower() == "true"
    if snapshot["breaches"]:
        print("Threshold breaches:")
        for item in snapshot["breaches"]:
            print(f"- {item}")
        if fail_on_breach:
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
