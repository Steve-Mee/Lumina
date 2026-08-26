"""Perfect Birth conjunction gate — SSOT unlock for Phase 2 Autonomy.

M5: types/evaluate in ``perfect_birth_types``; KPI gather in ``perfect_birth_gather``.
Fail-closed. Hollow flag is not enough when evidence sidecar is required.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.perfect_birth_gather import gather_perfect_birth_kpis
from lumina_core.birth.perfect_birth_types import (
    DEFAULT_EVIDENCE_REL,
    DEFAULT_FLAG_REL,
    MILESTONE_ID,
    PerfectBirthConjunctionResult,
    PerfectBirthKpis,
    PerfectBirthThresholds,
    _read_json,
    evaluate_perfect_birth_conjunction,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.perfect_birth_gate")

def _missing_sources(source_notes: dict[str, str]) -> list[str]:
    """Sources marked missing/unavailable — fail-closed honesty for operators."""
    missing: list[str] = []
    for key, note in (source_notes or {}).items():
        n = str(note or "").strip().lower()
        if not n or n in {"missing", "unavailable"} or "missing" in n or "unavailable" in n:
            missing.append(str(key))
    return missing


def perfect_birth_status(
    workspace_root: Path | str | None = None,
    *,
    thresholds: PerfectBirthThresholds | None = None,
    auto_declare_enabled: bool | None = None,
) -> dict[str, Any]:
    """Operator-facing Perfect Birth status: KPIs, gaps, unlock, Phase 2 suggestion."""
    root = Path(workspace_root) if workspace_root else Path.cwd()
    thr = thresholds or PerfectBirthThresholds()
    kpis = gather_perfect_birth_kpis(root)
    conj = evaluate_perfect_birth_conjunction(kpis, thresholds=thr)
    flag_path = root / DEFAULT_FLAG_REL
    evidence = load_perfect_birth_evidence(flag_path)
    unlock_ok, unlock_detail = perfect_birth_unlock_valid(
        flag_path=flag_path,
        require_evidence=True,
    )
    phase2_profile = phase2_shadow_campaign_profile()
    missing = _missing_sources(dict(kpis.source_notes))
    auto_on = bool(auto_declare_enabled) if auto_declare_enabled is not None else False
    if auto_declare_enabled is None:
        try:
            from lumina_core.birth.config import load_birth_v2_config

            auto_on = bool(
                getattr(load_birth_v2_config(root).curriculum, "perfect_birth_auto_declare", False)
            )
        except Exception:
            auto_on = False

    if unlock_ok:
        next_step = (
            "Phase 2 shadow unlock valid (evidence+flag). Apply Phase 2 shadow profile in config "
            "(SIM/birth only); apply mode remains operator + twin gated; REAL apply hard-blocked."
        )
    elif conj.passed:
        next_step = (
            "Perfect Birth conjunction passed — declare with "
            "`python scripts/validation/declare_perfect_birth.py` (or enable "
            "`perfect_birth_auto_declare` after birth complete), then enable Phase 2 shadow profile."
        )
    else:
        next_step = "Close KPI gaps listed in failures; re-run gather/status."

    return {
        "would_pass": bool(conj.passed),
        "failures": list(conj.failures),
        "missing_sources": missing,
        "metrics": conj.metrics,
        "thresholds": conj.thresholds,
        "sources": dict(kpis.source_notes),
        "flag_exists": flag_path.is_file(),
        "flag_path": str(flag_path),
        "evidence_exists": bool(evidence),
        "evidence_passed": bool(evidence.get("passed")) if evidence else False,
        "unlock_valid": unlock_ok,
        "unlock_detail": unlock_detail,
        "auto_declare_enabled": auto_on,
        "phase2_shadow_profile": phase2_profile,
        "capital_mode_safe": True,  # Perfect Birth never opens REAL capital paths
        "next_step": next_step,
    }


from lumina_core.birth.perfect_birth_campaign import (  # noqa: E402,F401
    build_perfect_birth_campaign_report,
)


def maybe_auto_declare_perfect_birth(
    workspace_root: Path | str | None = None,
    *,
    curriculum_cfg: Any | None = None,
    force_enabled: bool | None = None,
    kpis: PerfectBirthKpis | None = None,
) -> dict[str, Any]:
    """If conjunction + Fabric foundation bundle pass, write flag+evidence.

    Fail-closed: never force. Never mutates Phase 2 flags / REAL.
    ``force_enabled=True`` is an explicit lab/test override (still conjunction-gated).
    Production auto-declare also requires the ADR-0040 Fabric sidecar.
    """
    root = Path(workspace_root) if workspace_root else Path.cwd()
    enabled = force_enabled
    skip_fabric = force_enabled is True
    thr = PerfectBirthThresholds()
    if curriculum_cfg is not None:
        thr = PerfectBirthThresholds.from_curriculum_cfg(curriculum_cfg)
        if enabled is None:
            enabled = bool(getattr(curriculum_cfg, "perfect_birth_auto_declare", False))
    if enabled is None:
        try:
            from lumina_core.birth.config import load_birth_v2_config

            cur = load_birth_v2_config(root).curriculum
            thr = PerfectBirthThresholds.from_curriculum_cfg(cur)
            enabled = bool(getattr(cur, "perfect_birth_auto_declare", False))
        except Exception:
            enabled = False

    fabric: dict[str, Any] = {"ok": False, "reason": "not_checked"}
    if not skip_fabric:
        from lumina_core.birth.fabric_foundation_bundle import evaluate_fabric_foundation_bundle

        fabric = evaluate_fabric_foundation_bundle(root)
        # Production only: Fabric evidence can enable auto-declare. Explicit False stays off.
        if fabric.get("ok") and force_enabled is None:
            enabled = True

    if not enabled:
        return {
            "declared": False,
            "reason": "auto_declare_disabled",
            "passed": False,
            "fabric_bundle": fabric,
        }

    if not skip_fabric and not fabric.get("ok"):
        return {
            "declared": False,
            "reason": "fabric_foundation_bundle_incomplete",
            "passed": False,
            "fabric_bundle": fabric,
        }

    flag_path = root / DEFAULT_FLAG_REL
    unlock_ok, unlock_detail = perfect_birth_unlock_valid(
        flag_path=flag_path,
        require_evidence=True,
    )
    if unlock_ok:
        return {
            "declared": False,
            "reason": "already_unlocked",
            "passed": True,
            "unlock_detail": unlock_detail,
        }

    # Never force from auto path — hollow / forced flags cannot unlock Phase 2.
    payload = declare_perfect_birth(
        root,
        thresholds=thr,
        kpis=kpis,
        force=False,
        record_maturity=True,
    )
    payload["auto_declare"] = True
    if payload.get("declared") and not payload.get("passed"):
        # Defensive: auto path must never leave a Phase-2-usable hollow unlock.
        payload["declared"] = False
        payload["reason"] = "auto_declare_refused_without_conjunction"
    return payload


def phase2_shadow_campaign_profile() -> dict[str, Any]:
    """Documented SIM/birth Phase 2 profile after Perfect Birth evidence (never REAL apply)."""
    return {
        "phase2_autonomy_enabled": True,
        "phase2_dynamic_wall_enabled": True,
        "phase2_self_adaptive_params_enabled": True,
        "phase2_instance_adapt_enabled": True,
        "phase2_execution_mode": "shadow",
        "phase2_require_perfect_birth_flag": True,
        "phase2_require_perfect_birth_evidence": True,
        "phase2_require_twin_for_apply": True,
        "note": "SIM/birth only — apply mode requires separate operator flip + twin; REAL apply hard-blocked",
    }


def evidence_path_for_flag(flag_path: Path | str) -> Path:
    p = Path(flag_path)
    if p.suffix == ".flag":
        return p.with_suffix(".json")
    return p.parent / "perfect_birth_complete.json"


def load_perfect_birth_evidence(flag_path: Path | str | None = None) -> dict[str, Any] | None:
    path = evidence_path_for_flag(flag_path or DEFAULT_FLAG_REL)
    data = _read_json(path)
    return data if data else None


def perfect_birth_unlock_valid(
    *,
    flag_path: Path | str = DEFAULT_FLAG_REL,
    require_evidence: bool = True,
    recheck_kpis: PerfectBirthKpis | None = None,
    thresholds: PerfectBirthThresholds | None = None,
) -> tuple[bool, str]:
    """Whether Phase 2 may treat Perfect Birth as unlocked.

    - Flag must exist.
    - If require_evidence: sidecar JSON must exist with passed=true.
    - If recheck_kpis provided: live conjunction must still pass (stale evidence fail-closed).
    """
    flag = Path(flag_path)
    try:
        if not flag.is_file():
            return False, f"missing_flag:{flag}"
    except OSError as exc:
        return False, f"flag_unreadable:{exc}"

    if require_evidence:
        evidence = load_perfect_birth_evidence(flag)
        if not evidence:
            return False, "missing_evidence_sidecar"
        # Force-declare is audited operator override for visibility only — never Phase 2 unlock.
        if bool(evidence.get("forced")):
            return False, "forced_evidence_not_valid_for_unlock"
        if not bool(evidence.get("passed")):
            return False, "evidence_not_passed"
        # Hollow / tampered: declared without conjunction pass cannot unlock.
        if evidence.get("declared") is False:
            return False, "evidence_not_declared"
        reason = str(evidence.get("reason") or "").strip().lower()
        if reason in {"forced_override", "conjunction_failed"}:
            return False, f"evidence_reason_not_valid:{reason}"

    if recheck_kpis is not None:
        result = evaluate_perfect_birth_conjunction(recheck_kpis, thresholds=thresholds)
        if not result.passed:
            return False, "recheck_failed:" + ",".join(result.failures[:3])

    return True, "ok"


def declare_perfect_birth(
    workspace_root: Path | str | None = None,
    *,
    thresholds: PerfectBirthThresholds | None = None,
    kpis: PerfectBirthKpis | None = None,
    force: bool = False,
    flag_rel: str = DEFAULT_FLAG_REL,
    record_maturity: bool = True,
) -> dict[str, Any]:
    """Evaluate conjunction; write flag + evidence only if passed (or force with audit).

    Returns declaration result dict. Never enables Phase 2 flags.
    """
    root = Path(workspace_root) if workspace_root else Path.cwd()
    thr = thresholds or PerfectBirthThresholds()
    measured = kpis or gather_perfect_birth_kpis(root)
    result = evaluate_perfect_birth_conjunction(measured, thresholds=thr)

    flag_path = Path(flag_rel)
    if not flag_path.is_absolute():
        flag_path = root / flag_rel
    evidence_path = evidence_path_for_flag(flag_path)

    declared = False
    reason = "conjunction_failed"
    if result.passed:
        declared = True
        reason = "conjunction_passed"
    elif force:
        declared = True
        reason = "forced_override"

    payload = {
        "declared_at": datetime.now(timezone.utc).isoformat(),
        "passed": bool(result.passed),
        "declared": declared,
        "reason": reason,
        "forced": bool(force and not result.passed),
        "failures": list(result.failures),
        "metrics": result.metrics,
        "thresholds": result.thresholds,
        "flag_path": str(flag_path),
        "evidence_path": str(evidence_path),
        "source": "declare_perfect_birth",
    }

    if declared:
        flag_path.parent.mkdir(parents=True, exist_ok=True)
        flag_path.write_text(
            datetime.now(timezone.utc).isoformat() + "\n",
            encoding="utf-8",
        )
        evidence_path.write_text(
            json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        if record_maturity and result.passed:
            try:
                from lumina_core.maturity.milestone_hooks import try_record_milestone

                try_record_milestone(
                    root,
                    MILESTONE_ID,
                    metadata={
                        "source": "declare_perfect_birth",
                        "twin_steve_agreement_pct": measured.twin_steve_agreement_pct,
                        "autonomous_recovery_rate_pct": measured.autonomous_recovery_rate_pct,
                    },
                )
            except Exception as exc:
                logger.debug("perfect_birth.maturity_hook_failed: %s", exc)
        if result.passed:
            _enable_sim_auto_evolve(root)
        logger.info(
            "perfect_birth.declared passed=%s forced=%s path=%s",
            result.passed,
            force and not result.passed,
            flag_path,
        )
    else:
        # Write evidence of failed attempt for operator visibility (no flag)
        try:
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            fail_path = evidence_path.with_name("perfect_birth_last_attempt.json")
            fail_path.write_text(
                json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            payload["last_attempt_path"] = str(fail_path)
        except Exception:
            pass
        logger.warning(
            "perfect_birth.declare_blocked failures=%s",
            result.failures,
        )

    return payload


def _enable_sim_auto_evolve(workspace_root: Path) -> None:
    """After Perfect Birth evidence: auto-advance SIM phases. REAL stays hub-confirm."""
    try:
        from lumina_core.maturity.continuum import load_continuum, set_advance_mode

        mode = str(load_continuum(workspace_root).get("advance_mode") or "manual")
        if mode in {"telegram", "auto_evolve"}:
            return
        set_advance_mode(workspace_root, "auto_evolve")
    except Exception as exc:
        logger.debug("perfect_birth.auto_evolve_skip: %s", exc)


__all__ = [
    "DEFAULT_EVIDENCE_REL",
    "DEFAULT_FLAG_REL",
    "MILESTONE_ID",
    "PerfectBirthConjunctionResult",
    "PerfectBirthKpis",
    "PerfectBirthThresholds",
    "build_perfect_birth_campaign_report",
    "declare_perfect_birth",
    "evaluate_perfect_birth_conjunction",
    "evidence_path_for_flag",
    "gather_perfect_birth_kpis",
    "load_perfect_birth_evidence",
    "maybe_auto_declare_perfect_birth",
    "perfect_birth_status",
    "perfect_birth_unlock_valid",
    "phase2_shadow_campaign_profile",
]
