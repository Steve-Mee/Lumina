from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
METRICS_FILE = ROOT / "state" / "build_metrics_snapshot_latest.json"
OUT_FILE = ROOT / "state" / "slo_report.json"


def main() -> int:
    if not METRICS_FILE.exists():
        print(f"Metrics snapshot missing: {METRICS_FILE}")
        return 2

    data = json.loads(METRICS_FILE.read_text(encoding="utf-8"))
    breaches = data.get("breaches", []) if isinstance(data, dict) else []
    status = "pass" if not breaches else "fail"

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_metrics_file": str(METRICS_FILE),
        "status": status,
        "breaches": breaches,
        "summary": {
            "order_acceptance_rate": data.get("order_acceptance_rate"),
            "inference_fallback_rate": data.get("inference_fallback_rate"),
            "reconcile_latency_p95_ms": data.get("reconcile_latency_p95_ms"),
        },
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"SLO report written: {OUT_FILE}")
    print(f"SLO status: {status}")
    for item in breaches:
        print(f"- breach: {item}")

    fail_on_breach = os.getenv("LUMINA_SLO_FAIL_ON_BREACH", "true").strip().lower() == "true"
    if breaches and fail_on_breach:
        return 3

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
