"""Aperture coverage honesty helpers (SC-5).

``soft_pass`` is ops yellow. REAL-green is ``certified`` /
``aperture_coverage_ready_for_real`` only. Empty samples are never green.
"""
from __future__ import annotations

from typing import Any

_FA_EVIDENCE_STAGES = frozenset({"final_arbitration", "capital_aperture_admission"})

__all__ = [
    "aperture_coverage_ready_for_real",
    "finish_aperture_coverage_gate",
    "row_is_final_arbitration_evidence",
]


def row_is_final_arbitration_evidence(row: dict[str, Any]) -> bool:
    stage = str(row.get("stage") or "").strip().lower()
    topic = str(row.get("topic") or "").strip().lower()
    if stage in _FA_EVIDENCE_STAGES:
        return True
    return "final_arbitration" in stage or "final_arbitration" in topic


def aperture_coverage_ready_for_real(gate: dict[str, Any] | None) -> bool:
    """REAL readiness: certified coverage only. Empty/thin soft_pass is never green."""
    if not isinstance(gate, dict):
        return False
    if bool(gate.get("soft_pass")) or bool(gate.get("hard_fail")):
        return False
    if int(gate.get("sample_size") or 0) <= 0:
        return False
    if "certified" in gate:
        return bool(gate.get("certified"))
    return bool(gate.get("ok"))


def finish_aperture_coverage_gate(
    snap: dict[str, Any],
    *,
    target: float,
    min_sample_size: int,
) -> dict[str, Any]:
    """Apply empty/thin/hard coverage rules. Does not invent samples."""
    sample = int(snap.get("sample_size") or 0)
    pct_raw = snap.get("lineage_coverage_pct")
    pct = float(pct_raw) if pct_raw is not None else None
    min_n = int(min_sample_size)
    if sample <= 0:
        return _status(
            ok=True,
            soft_pass=True,
            hard_fail=False,
            reason="no_samples",
            message=(
                "No decision_log/audit rows found — ops yellow (soft pass). "
                "Not REAL-green. Run SIM/REAL sessions through Final Arbitration "
                "to accumulate samples."
            ),
            sample_size=0,
            pct=None,
            target=target,
            min_sample_size=min_n,
            snap=snap,
        )
    if sample < min_n:
        return _status(
            ok=True,
            soft_pass=True,
            hard_fail=False,
            reason="thin_sample",
            message=(
                f"sample_size={sample} < min_sample_size={min_n} — "
                "ops yellow (soft pass). Coverage observed="
                f"{pct}% (not H1-certified until N≥{min_n})."
            ),
            sample_size=sample,
            pct=pct,
            target=target,
            min_sample_size=min_n,
            snap=snap,
        )
    meets = pct is not None and pct >= target
    extra = {
        "coverage_meets_h1_goal": bool(snap.get("coverage_meets_h1_goal")),
        "coverage_meets_phase2_goal": bool(snap.get("coverage_meets_phase2_goal")),
    }
    return _status(
        ok=bool(meets),
        soft_pass=False,
        hard_fail=not bool(meets),
        reason="coverage_ok" if meets else "coverage_below_target",
        message=(
            f"coverage={pct}% target={target}% sample_size={sample} — "
            + ("H1 goal met." if meets else "below target; improve admission lineage emit.")
        ),
        sample_size=sample,
        pct=pct,
        target=target,
        min_sample_size=min_n,
        snap=snap,
        extra=extra,
    )


def _status(
    *,
    ok: bool,
    soft_pass: bool,
    hard_fail: bool,
    reason: str,
    message: str,
    sample_size: int,
    pct: float | None,
    target: float,
    min_sample_size: int,
    snap: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    certified = bool(ok) and not soft_pass and not hard_fail
    if hard_fail:
        ops_status = "red"
        certified = False
    elif certified:
        ops_status = "green"
    else:
        ops_status = "yellow"
    payload: dict[str, Any] = {
        "schema": "aperture_coverage_gate_v1",
        "ok": ok,
        "soft_pass": soft_pass,
        "hard_fail": hard_fail,
        "certified": certified,
        "ops_status": ops_status,
        "reason": reason,
        "message": message,
        "sample_size": sample_size,
        "lineage_coverage_pct": pct,
        "target_coverage_pct": target,
        "min_sample_size": min_sample_size,
        "snapshot": snap,
    }
    if extra:
        payload.update(extra)
    return payload
