"""Phase 2 execution mode triad — observe / shadow / apply (Slice D).

Fail-closed default: observe (propose + audit only; never mutate).
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class Phase2ExecutionMode(str, Enum):
    OBSERVE = "observe"
    SHADOW = "shadow"
    APPLY = "apply"


def normalize_execution_mode(raw: str | Phase2ExecutionMode | None) -> Phase2ExecutionMode:
    if isinstance(raw, Phase2ExecutionMode):
        return raw
    key = str(raw or "observe").strip().lower()
    if key in {"observe", "obs", "log"}:
        return Phase2ExecutionMode.OBSERVE
    if key in {"shadow", "counterfactual", "dry"}:
        return Phase2ExecutionMode.SHADOW
    if key in {"apply", "live", "execute", "full"}:
        return Phase2ExecutionMode.APPLY
    return Phase2ExecutionMode.OBSERVE


def should_mutate(mode: Phase2ExecutionMode | str | None) -> bool:
    """True only for apply mode (gate must still allow)."""
    return normalize_execution_mode(mode) == Phase2ExecutionMode.APPLY


def should_record_counterfactual(mode: Phase2ExecutionMode | str | None) -> bool:
    return normalize_execution_mode(mode) == Phase2ExecutionMode.SHADOW


def evaluate_pillar_promotion(
    *,
    shadow_samples: int,
    shadow_would_apply: int,
    apply_samples: int = 0,
    apply_success: int = 0,
    min_shadow_samples: int = 8,
    min_shadow_would_apply_rate_pct: float = 30.0,
    require_non_inferior_apply: bool = False,
) -> dict[str, Any]:
    """Evidence helper for promoting a pillar observe→shadow→apply.

    Conservative defaults: enough shadow samples and a minimum would-apply rate
    (proves the gate is not stuck always-reject). Optional apply non-inferiority
    when compare window exists.
    """
    failures: list[str] = []
    if shadow_samples < min_shadow_samples:
        failures.append(
            f"shadow_samples={shadow_samples} < {min_shadow_samples}"
        )
    would_rate = (
        round((shadow_would_apply / max(1, shadow_samples)) * 100.0, 2)
        if shadow_samples
        else 0.0
    )
    if shadow_samples >= min_shadow_samples and would_rate < min_shadow_would_apply_rate_pct:
        failures.append(
            f"shadow_would_apply_rate_pct={would_rate} < {min_shadow_would_apply_rate_pct}"
        )
    apply_rate = (
        round((apply_success / max(1, apply_samples)) * 100.0, 2) if apply_samples else None
    )
    if require_non_inferior_apply and apply_samples >= min_shadow_samples:
        if apply_rate is not None and apply_rate + 1e-9 < would_rate:
            failures.append(
                f"apply_rate_pct={apply_rate} inferior to shadow_would_apply_rate_pct={would_rate}"
            )

    return {
        "promote_to_apply": len(failures) == 0,
        "failures": failures,
        "shadow_samples": int(shadow_samples),
        "shadow_would_apply": int(shadow_would_apply),
        "shadow_would_apply_rate_pct": would_rate,
        "apply_samples": int(apply_samples),
        "apply_success": int(apply_success),
        "apply_rate_pct": apply_rate,
    }


def compute_shadow_evidence_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize phase2 audit rows for promotion evidence."""
    shadow_rows = [r for r in rows if str(r.get("execution_mode", "")).lower() == "shadow"]
    apply_rows = [
        r
        for r in rows
        if str(r.get("execution_mode", "")).lower() == "apply" and bool(r.get("apply_requested"))
    ]
    shadow_would = sum(1 for r in shadow_rows if bool(r.get("shadow_would_apply")))
    apply_ok = sum(1 for r in apply_rows if bool(r.get("applied")))
    return evaluate_pillar_promotion(
        shadow_samples=len(shadow_rows),
        shadow_would_apply=shadow_would,
        apply_samples=len(apply_rows),
        apply_success=apply_ok,
    )


__all__ = [
    "Phase2ExecutionMode",
    "compute_shadow_evidence_from_rows",
    "evaluate_pillar_promotion",
    "normalize_execution_mode",
    "should_mutate",
    "should_record_counterfactual",
]
