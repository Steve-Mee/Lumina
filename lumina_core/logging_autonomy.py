"""Autonomy snapshot helpers for logging/metrics."""
from __future__ import annotations

import json
from typing import Any


def compute_autonomy_snapshot(window_hours: int = 24) -> dict[str, Any]:
    """Compute rolling AutonomySnapshot dict from monitoring_twin_decisions.jsonl.

    Respects LUMINA_WORKSPACE_ROOT for test isolation. Filters to recent window.
    Returns keys matching AutonomySnapshot + autonomy_level_pct.
    """
    # Lazy imports avoid circular dependency with logging_monitoring/logging_core.
    from lumina_core.logging_monitoring import (  # noqa: PLC0415
        _monitoring_state_path,
        classify_twin_decision_outcome,
    )

    path = _monitoring_state_path("monitoring_twin_decisions.jsonl")
    decisions_total = 0
    auto_approved_total = 0
    veto_total = 0
    deferred_total = 0

    if not path.exists():
        return {
            "decisions_total": 0,
            "auto_approved_total": 0,
            "veto_total": 0,
            "deferred_total": 0,
            "autonomy_level_pct": 0.0,
        }

    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        cutoff = None
        if window_hours and window_hours > 0:
            from datetime import datetime, timedelta, timezone as _tz
            cutoff = datetime.now(_tz.utc) - timedelta(hours=int(window_hours))

        for raw in lines:
            raw = raw.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except Exception:
                continue

            ts_raw = str(row.get("timestamp", "") or "").strip()
            if cutoff and ts_raw:
                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=_tz.utc)
                    if ts < cutoff:
                        continue
                except Exception:
                    pass  # include if unparsable

            outcome = str(row.get("outcome", "") or "").strip().lower()
            if not outcome:
                # Fallback classify using available fields
                rec = bool(row.get("recommendation", False))
                sc = float(row.get("score", row.get("confidence", 0.0)) or 0.0)
                rf = row.get("risk_flags") or []
                outcome = classify_twin_decision_outcome(recommendation=rec, score=sc, risk_flags=list(rf) if isinstance(rf, list) else [])

            decisions_total += 1
            if outcome == "auto_approved":
                auto_approved_total += 1
            elif outcome == "veto":
                veto_total += 1
            else:
                deferred_total += 1
    except Exception:
        pass

    denom = max(1, decisions_total)
    autonomy_level_pct = round((auto_approved_total / denom) * 100.0, 2)
    return {
        "decisions_total": int(decisions_total),
        "auto_approved_total": int(auto_approved_total),
        "veto_total": int(veto_total),
        "deferred_total": int(deferred_total),
        "autonomy_level_pct": float(autonomy_level_pct),
    }


