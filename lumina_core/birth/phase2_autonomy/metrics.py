"""Phase 2 Autonomy truth layer — audit JSONL + rolling metrics.

Canonical stream: ``state/monitoring_phase2_autonomy.jsonl``

Operator question: "Did Phase 2 help?" → ``compute_phase2_metrics_snapshot()``
or ``python -m lumina_launcher birth phase2-status``.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import resolve_monitoring_state_dir

PHASE2_MONITORING_FILENAME = "monitoring_phase2_autonomy.jsonl"


def phase2_monitoring_path() -> Path:
    return resolve_monitoring_state_dir() / PHASE2_MONITORING_FILENAME


def proposal_hash(proposal: dict[str, Any] | None) -> str:
    """Stable short hash of proposal payload for audit linkage."""
    raw = json.dumps(proposal or {}, ensure_ascii=True, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def record_phase2_decision_monitoring(
    *,
    pillar: str,
    allowed: bool,
    reason: str,
    applied: bool,
    correlation_id: str = "",
    stage: str = "",
    twin_conf: float = 0.0,
    twin_mode: str = "",
    mode: str = "",
    proposal: dict[str, Any] | None = None,
    constitution_violations: int = 0,
    message: str = "",
    apply_requested: bool = False,
    recovery_tag: str = "",
    execution_mode: str = "",
    shadow_would_apply: bool = False,
) -> dict[str, Any]:
    """Append one Phase 2 gate/apply decision. Best-effort; never raises to callers."""
    payload: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pillar": str(pillar or ""),
        "allowed": bool(allowed),
        "reason": str(reason or ""),
        "applied": bool(applied),
        "apply_requested": bool(apply_requested),
        "correlation_id": str(correlation_id or "")[:128],
        "stage": str(stage or ""),
        "twin_conf": round(float(twin_conf or 0.0), 4),
        "twin_mode": str(twin_mode or ""),
        "mode": str(mode or ""),
        "proposal_hash": proposal_hash(proposal),
        "constitution_violations": int(constitution_violations or 0),
        "message": str(message or "")[:500],
        "execution_mode": str(execution_mode or ""),
        "shadow_would_apply": bool(shadow_would_apply),
    }
    if recovery_tag:
        payload["recovery_tag"] = str(recovery_tag)[:64]
    try:
        path = phase2_monitoring_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(payload, ensure_ascii=True, sort_keys=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
    return payload


def _parse_ts(ts_raw: str) -> datetime | None:
    if not ts_raw:
        return None
    try:
        ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except Exception:
        return None


def _iter_phase2_rows(
    *,
    window_hours: int | None = 24,
    path: Path | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    p = path or phase2_monitoring_path()
    if not p.is_file():
        return []
    try:
        lines = p.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return []
    if limit is not None and limit > 0:
        lines = lines[-limit:]

    cutoff = None
    if window_hours and window_hours > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=int(window_hours))

    rows: list[dict[str, Any]] = []
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        if cutoff is not None:
            ts = _parse_ts(str(row.get("timestamp", "") or ""))
            if ts is not None and ts < cutoff:
                continue
        rows.append(row)
    return rows


def compute_phase2_metrics_snapshot(
    *,
    window_hours: int = 24,
    path: Path | None = None,
) -> dict[str, Any]:
    """Rolling Phase 2 metrics for ops / CLI.

    Keys:
      phase2_proposals_total, phase2_apply_rate_pct, phase2_allowed_rate_pct,
      phase2_gate_reject_by_reason, phase2_by_pillar, phase2_applied_total,
      phase2_recovery_tagged, last_decision, window_hours
    """
    rows = _iter_phase2_rows(window_hours=window_hours, path=path)
    total = len(rows)
    applied_n = sum(1 for r in rows if bool(r.get("applied")))
    allowed_n = sum(1 for r in rows if bool(r.get("allowed")))
    apply_req_n = sum(1 for r in rows if bool(r.get("apply_requested")))
    reject_reasons: Counter[str] = Counter()
    by_pillar: dict[str, dict[str, int]] = {}
    recovery_tagged = 0

    for r in rows:
        pillar = str(r.get("pillar", "") or "unknown")
        bucket = by_pillar.setdefault(
            pillar, {"proposals": 0, "allowed": 0, "applied": 0, "rejected": 0}
        )
        bucket["proposals"] += 1
        if bool(r.get("allowed")):
            bucket["allowed"] += 1
        else:
            bucket["rejected"] += 1
            reason = str(r.get("reason", "") or "unknown")
            reject_reasons[reason] += 1
        if bool(r.get("applied")):
            bucket["applied"] += 1
        if r.get("recovery_tag"):
            recovery_tagged += 1

    # Apply rate among apply-requested rows when available; else among all
    if apply_req_n > 0:
        apply_rate = round((applied_n / max(1, apply_req_n)) * 100.0, 2)
    else:
        apply_rate = round((applied_n / max(1, total)) * 100.0, 2) if total else 0.0

    last = rows[-1] if rows else None
    return {
        "window_hours": int(window_hours),
        "phase2_proposals_total": int(total),
        "phase2_applied_total": int(applied_n),
        "phase2_allowed_total": int(allowed_n),
        "phase2_apply_requested_total": int(apply_req_n),
        "phase2_apply_rate_pct": float(apply_rate),
        "phase2_allowed_rate_pct": round((allowed_n / max(1, total)) * 100.0, 2) if total else 0.0,
        "phase2_gate_reject_by_reason": dict(reject_reasons.most_common(20)),
        "phase2_by_pillar": by_pillar,
        "phase2_recovery_tagged": int(recovery_tagged),
        "last_decision": last,
        "monitoring_path": str(phase2_monitoring_path()),
        "empty": total == 0,
    }


def load_phase2_recent_decisions(
    *,
    limit: int = 10,
    window_hours: int | None = None,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    """Most recent decisions (newest last)."""
    if window_hours is None:
        rows = _iter_phase2_rows(window_hours=None, path=path, limit=max(1, limit))
    else:
        rows = _iter_phase2_rows(window_hours=window_hours, path=path)
        rows = rows[-max(1, limit) :]
    return rows


def phase2_status_payload(
    *,
    window_hours: int = 24,
    recent_limit: int = 5,
    features: Any | None = None,
    workspace_root: Any | None = None,
) -> dict[str, Any]:
    """Full operator payload for CLI / ops (includes H3 SIM campaign)."""
    snap = compute_phase2_metrics_snapshot(window_hours=window_hours)
    recent = load_phase2_recent_decisions(limit=recent_limit, window_hours=window_hours)
    features_block: dict[str, Any] = {}
    if features is not None:
        features_block = {
            "enabled": bool(getattr(features, "enabled", False)),
            "dynamic_wall_enabled": bool(getattr(features, "dynamic_wall_enabled", False)),
            "self_adaptive_params_enabled": bool(
                getattr(features, "self_adaptive_params_enabled", False)
            ),
            "instance_adapt_enabled": bool(getattr(features, "instance_adapt_enabled", False)),
            "require_perfect_birth_flag": bool(
                getattr(features, "require_perfect_birth_flag", True)
            ),
            "require_perfect_birth_evidence": bool(
                getattr(features, "require_perfect_birth_evidence", True)
            ),
            "allow_sim_scaffold": bool(getattr(features, "allow_sim_scaffold", False)),
            "require_twin_for_apply": bool(getattr(features, "require_twin_for_apply", True)),
            "execution_mode": str(getattr(features, "execution_mode", "observe") or "observe"),
            "perfect_birth_unlocked": bool(
                features.perfect_birth_unlocked()
                if hasattr(features, "perfect_birth_unlocked")
                else False
            ),
        }
    campaign_block: dict[str, Any] = {}
    perfect_birth_block: dict[str, Any] = {}
    if workspace_root is not None:
        try:
            from lumina_core.birth.phase2_autonomy.sim_campaign import sim_campaign_status

            campaign_block = sim_campaign_status(workspace_root)
        except Exception:
            campaign_block = {"error": "campaign_status_unavailable"}
        try:
            from lumina_core.birth.perfect_birth_gate import perfect_birth_status

            pb = perfect_birth_status(workspace_root)
            perfect_birth_block = {
                "would_pass": pb.get("would_pass"),
                "unlock_valid": pb.get("unlock_valid"),
                "failures": pb.get("failures") or [],
                "missing_sources": pb.get("missing_sources") or [],
                "next_step": pb.get("next_step"),
                "phase2_shadow_profile": pb.get("phase2_shadow_profile"),
            }
        except Exception:
            perfect_birth_block = {"error": "perfect_birth_status_unavailable"}
    return {
        "features": features_block,
        "metrics": snap,
        "recent_decisions": recent,
        "sim_campaign": campaign_block,
        "perfect_birth": perfect_birth_block,
        "operator_hint": (
            "C1/H3: GET /api/birth/perfect-birth-status for KPI gaps; "
            "after unlock, POST /api/birth/phase2-enable-shadow; "
            "shadow_would_apply accumulates; then phase2-promote-sim-apply. "
            "REAL apply remains forbidden."
        ),
    }


__all__ = [
    "PHASE2_MONITORING_FILENAME",
    "compute_phase2_metrics_snapshot",
    "load_phase2_recent_decisions",
    "phase2_monitoring_path",
    "phase2_status_payload",
    "proposal_hash",
    "record_phase2_decision_monitoring",
]
