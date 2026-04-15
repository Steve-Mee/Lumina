from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _read_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _bounded(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def main() -> int:
    audit_path = Path("logs/trade_fill_audit.jsonl")
    rows = _read_rows(audit_path)

    reconciled = [r for r in rows if str(r.get("event", "")) in {"reconciled", "fill_received"}]

    slippages = [_safe_float(r.get("slippage_points")) for r in reconciled if r.get("slippage_points") is not None]
    commissions = [_safe_float(r.get("commission")) for r in reconciled if r.get("commission") is not None]
    latencies = [_safe_float(r.get("fill_latency_ms")) for r in reconciled if r.get("fill_latency_ms") is not None]

    median_slippage = median(slippages) if slippages else 1.0
    median_commission = median(commissions) if commissions else 1.25
    median_latency = median(latencies) if latencies else 300.0

    spread_mult = _bounded(median_slippage / 1.0, 0.7, 2.0)
    commission_mult = _bounded(median_commission / 1.25, 0.7, 2.0)
    latency_mult = _bounded(median_latency / 300.0, 0.7, 2.5)

    calibration = {
        "generated_from": str(audit_path),
        "sample_count": len(reconciled),
        "symbol_commission_multiplier": {"MES": round(commission_mult, 4), "MNQ": round(commission_mult, 4)},
        "symbol_spread_multiplier": {"default": round(spread_mult, 4)},
        "fill_latency_multiplier": {"default": round(latency_mult, 4), "volatile": round(_bounded(latency_mult * 1.2, 0.8, 3.0), 4)},
        "medians": {
            "slippage_points": round(median_slippage, 4),
            "commission": round(median_commission, 4),
            "fill_latency_ms": round(median_latency, 2),
        },
    }

    out_dir = Path("state/validation")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "fill_calibration.json").write_text(json.dumps(calibration, indent=2), encoding="utf-8")
    (out_dir / "fill_calibration_report.json").write_text(
        json.dumps(
            {
                "status": "ok" if len(reconciled) >= 10 else "low_sample_warning",
                "sample_count": len(reconciled),
                "calibration": calibration,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps({"status": "ok", "output": str(out_dir / "fill_calibration.json"), "samples": len(reconciled)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
