"""Multi-gate evaluator for Phase 2 Autonomy — fail-closed by default."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.phase2_autonomy.contracts import (
    Phase2GateReason,
    Phase2GateResult,
    Phase2InstanceAdaptProposal,
    Phase2ParamAdjustmentProposal,
    Phase2Pillar,
    Phase2WallAdjustmentProposal,
)
from lumina_core.birth.phase2_autonomy.features import Phase2AutonomyFeatures
from lumina_core.birth.phase2_autonomy.param_catalog import (
    FORBIDDEN_PARAM_KEYS,
    validate_param_changes,
)

# Align with organism_autonomy high-conf band.
TWIN_HIGH_CONF = 0.80

_SIM_MODES = frozenset({"sim", "birth", "paper", "practice", "shadow"})
_REAL_MODES = frozenset({"real", "live", "sim_real_guard", "prod", "production"})


def _normalize_mode(mode: str | None) -> str:
    return str(mode or "").strip().lower()


def _is_sim_like(mode: str | None) -> bool:
    m = _normalize_mode(mode)
    return m in _SIM_MODES or m.startswith("sim") or m.startswith("birth")


def _is_real_like(mode: str | None) -> bool:
    m = _normalize_mode(mode)
    return m in _REAL_MODES or m.startswith("real")


def evaluate_phase2_gate(
    *,
    features: Phase2AutonomyFeatures,
    pillar: Phase2Pillar | str,
    constitution_violations: int = 0,
    mode: str = "sim",
    approval_twin: Any | None = None,
    proposal: (
        Phase2WallAdjustmentProposal
        | Phase2ParamAdjustmentProposal
        | Phase2InstanceAdaptProposal
        | None
    ) = None,
    require_apply_path: bool = True,
    shadow_ok: bool | None = None,
) -> Phase2GateResult:
    """Evaluate whether a Phase 2 pillar action may proceed.

    Gate order (non-negotiable):
    1. master feature flag
    2. pillar flag
    3. perfect birth unlock (or explicit SIM scaffold)
    4. constitution violations (apply path)
    5. twin (when required for apply)
    6. risk surface / forbidden params / shadow for risk-touching
    """
    pillar_key = (
        pillar.value if isinstance(pillar, Phase2Pillar) else str(pillar or "").strip().lower()
    )
    pillar_enum = None
    for p in Phase2Pillar:
        if p.value == pillar_key:
            pillar_enum = p
            break
    if pillar_enum is None:
        return Phase2GateResult(
            allowed=False,
            reason=Phase2GateReason.INVALID_PROPOSAL.value,
            pillar=pillar_key,
            message=f"Unknown Phase 2 pillar: {pillar_key}",
        )

    if not features.enabled:
        return Phase2GateResult(
            allowed=False,
            reason=Phase2GateReason.FEATURE_DISABLED.value,
            pillar=pillar_key,
            message="phase2_autonomy_enabled is false (fail-closed)",
        )

    if not features.pillar_enabled(pillar_key):
        return Phase2GateResult(
            allowed=False,
            reason=Phase2GateReason.PILLAR_DISABLED.value,
            pillar=pillar_key,
            message=f"Phase 2 pillar disabled: {pillar_key}",
        )

    # Perfect Birth unlock: flag + evidence (Slice C); SIM scaffold may bypass
    unlocked = features.perfect_birth_unlocked()
    unlock_detail = "flag_present" if unlocked else "flag_missing"
    if features.require_perfect_birth_flag:
        if not (features.allow_sim_scaffold and _is_sim_like(mode)):
            ok, unlock_detail = features.perfect_birth_unlock_status(
                recheck=bool(
                    require_apply_path and getattr(features, "recheck_perfect_birth_kpis", False)
                ),
            )
            if not ok:
                reason = (
                    Phase2GateReason.PERFECT_BIRTH_EVIDENCE.value
                    if "evidence" in unlock_detail or "recheck" in unlock_detail
                    else Phase2GateReason.PERFECT_BIRTH_REQUIRED.value
                )
                return Phase2GateResult(
                    allowed=False,
                    reason=reason,
                    pillar=pillar_key,
                    message=(
                        f"Perfect Birth unlock failed ({unlock_detail}) at "
                        f"{features.perfect_birth_path()} "
                        "(declare via scripts/validation/declare_perfect_birth.py "
                        "or set phase2_allow_sim_scaffold for SIM scaffold)"
                    ),
                    details={"unlock_detail": unlock_detail},
                )
            unlocked = True

    if require_apply_path and _is_real_like(mode):
        return Phase2GateResult(
            allowed=False,
            reason=Phase2GateReason.RISK_SURFACE.value,
            pillar=pillar_key,
            message=f"Phase 2 apply forbidden in mode={_normalize_mode(mode)} (SIM/birth only)",
            details={"mode": _normalize_mode(mode)},
        )

    if require_apply_path and int(constitution_violations or 0) > 0:
        return Phase2GateResult(
            allowed=False,
            reason=Phase2GateReason.CONSTITUTION_BLOCKED.value,
            pillar=pillar_key,
            message=f"constitution_violations={constitution_violations} — twin cannot override",
            details={"constitution_violations": int(constitution_violations)},
        )

    twin_conf = 0.0
    twin_mode = ""
    if require_apply_path and features.require_twin_for_apply:
        if approval_twin is None:
            return Phase2GateResult(
                allowed=False,
                reason=Phase2GateReason.TWIN_REQUIRED.value,
                pillar=pillar_key,
                message="Approval Twin required for Phase 2 apply (fail-closed)",
            )
        twin_res = _evaluate_twin(approval_twin, pillar_key=pillar_key, mode=mode)
        twin_conf = float(twin_res.get("confidence", 0.0) or 0.0)
        twin_mode = str(twin_res.get("mode") or "")
        if twin_res.get("error"):
            return Phase2GateResult(
                allowed=False,
                reason=Phase2GateReason.TWIN_REQUIRED.value,
                pillar=pillar_key,
                message=str(twin_res["error"]),
                twin_confidence=twin_conf,
                twin_mode=twin_mode,
            )
        if not twin_res.get("raw_recommendation", False) and twin_conf >= TWIN_HIGH_CONF:
            return Phase2GateResult(
                allowed=False,
                reason=Phase2GateReason.TWIN_VETO.value,
                pillar=pillar_key,
                message=f"Twin high-conf veto (conf={twin_conf:.2%})",
                twin_confidence=twin_conf,
                twin_mode=twin_mode,
            )
        if twin_conf < TWIN_HIGH_CONF:
            return Phase2GateResult(
                allowed=False,
                reason=Phase2GateReason.TWIN_LOW_CONFIDENCE.value,
                pillar=pillar_key,
                message=f"Twin confidence {twin_conf:.2%} < {TWIN_HIGH_CONF:.0%}",
                twin_confidence=twin_conf,
                twin_mode=twin_mode,
            )
        if not twin_res.get("executable", False) or not twin_res.get(
            "effective_recommendation", False
        ):
            return Phase2GateResult(
                allowed=False,
                reason=Phase2GateReason.TWIN_NOT_EXECUTABLE.value,
                pillar=pillar_key,
                message=(
                    f"Twin not executable for apply (mode={twin_mode}, "
                    f"effective={twin_res.get('effective_recommendation')})"
                ),
                twin_confidence=twin_conf,
                twin_mode=twin_mode,
            )

    if proposal is not None:
        prop_check = _validate_proposal(proposal)
        if prop_check is not None:
            return Phase2GateResult(
                allowed=False,
                reason=prop_check[0],
                pillar=pillar_key,
                message=prop_check[1],
                twin_confidence=twin_conf,
                twin_mode=twin_mode,
            )
        risk_touching = bool(getattr(proposal, "risk_touching", False))
        if risk_touching:
            if shadow_ok is not True:
                return Phase2GateResult(
                    allowed=False,
                    reason=Phase2GateReason.SHADOW_REQUIRED.value,
                    pillar=pillar_key,
                    message="Risk-touching Phase 2 proposal requires shadow_ok=True",
                    twin_confidence=twin_conf,
                    twin_mode=twin_mode,
                )

    return Phase2GateResult(
        allowed=True,
        reason=Phase2GateReason.ALLOWED.value,
        pillar=pillar_key,
        message="Phase 2 gate passed",
        twin_confidence=twin_conf,
        twin_mode=twin_mode,
        details={
            "perfect_birth_unlocked": unlocked,
            "mode": _normalize_mode(mode),
        },
    )


def _evaluate_twin(approval_twin: Any, *, pillar_key: str, mode: str) -> dict[str, Any]:
    try:
        if hasattr(approval_twin, "sync_mode_from_controller"):
            try:
                approval_twin.sync_mode_from_controller()
            except Exception:
                pass

        from lumina_core.evolution.dna_registry import PolicyDNA

        proxy = PolicyDNA.create(
            prompt_id="phase2_autonomy_twin_gate",
            version="phase2",
            content={"pillar": pillar_key, "mode": mode},
            fitness_score=0.5,
            generation=0,
            mutation_rate=0.03,
            lineage_hash="phase2-autonomy",
        )
        twin_res = approval_twin.evaluate_dna_promotion(proxy)
        if not isinstance(twin_res, dict):
            return {"error": "twin returned non-dict result"}
        t_conf = float(twin_res.get("confidence", 0.0) or 0.0)
        t_raw = bool(twin_res.get("recommendation", False))
        t_executable = bool(twin_res.get("executable", False))
        t_rec = bool(twin_res.get("effective_recommendation", False))
        if "effective_recommendation" not in twin_res:
            # Legacy twin without mode authority — fail-closed
            t_rec = False
            t_executable = False
        twin_mode = str(
            twin_res.get("mode") or getattr(approval_twin, "mode", "shadow") or "shadow"
        )
        return {
            "confidence": t_conf,
            "raw_recommendation": t_raw,
            "effective_recommendation": t_rec,
            "executable": t_executable,
            "mode": twin_mode,
            "risk_flags": list(twin_res.get("risk_flags", []) or []),
        }
    except Exception as exc:
        return {"error": f"twin evaluation failed: {exc}"}


def _validate_proposal(
    proposal: (
        Phase2WallAdjustmentProposal
        | Phase2ParamAdjustmentProposal
        | Phase2InstanceAdaptProposal
    ),
) -> tuple[str, str] | None:
    if isinstance(proposal, Phase2ParamAdjustmentProposal):
        for key in proposal.changes:
            if str(key) in FORBIDDEN_PARAM_KEYS:
                return (
                    Phase2GateReason.FORBIDDEN_PARAM.value,
                    f"Forbidden risk/capital param key: {key}",
                )
        violations = validate_param_changes(proposal.changes)
        if violations:
            return (
                Phase2GateReason.OUT_OF_BOUNDS.value,
                f"Param bound violations: {', '.join(violations)}",
            )
    if isinstance(proposal, Phase2InstanceAdaptProposal):
        action = str(proposal.action or "").strip().lower()
        forbidden_surfaces = ("broker", "real", "order", "capital", "live_session")
        if any(s in action for s in forbidden_surfaces):
            return (
                Phase2GateReason.RISK_SURFACE.value,
                f"Instance adapt action touches forbidden surface: {action}",
            )
        if proposal.risk_touching:
            return (
                Phase2GateReason.RISK_SURFACE.value,
                "Instance adapt marked risk_touching — refused in Phase 2 foundation",
            )
    if isinstance(proposal, Phase2WallAdjustmentProposal):
        mult = float(proposal.stall_wall_sec_multiplier)
        if mult < 0.75 or mult > 1.5:
            return (
                Phase2GateReason.OUT_OF_BOUNDS.value,
                f"stall_wall_sec_multiplier {mult} outside [0.75, 1.5]",
            )
        delta = int(proposal.stagnation_rollouts_delta)
        if delta < -1 or delta > 2:
            return (
                Phase2GateReason.OUT_OF_BOUNDS.value,
                f"stagnation_rollouts_delta {delta} outside [-1, 2]",
            )
    return None


__all__ = [
    "TWIN_HIGH_CONF",
    "evaluate_phase2_gate",
]
