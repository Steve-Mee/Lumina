"""H4: Twin training discipline — One Twin DNA · Dual Authority (ADR-0038).

Single ApprovalTwin conscience trained to REAL standards.
Authority by capital_mode (not a second agent):

- explore_pass (birth/sim): Twin preference does NOT block the learn loop
- values_active (sim_real_guard): Twin applies Steve values (dress rehearsal)
- values_inside_gates (real): Twin input only; human multi-gate owns capital

Does not arm REAL capital. Coordinates with ``real_multi_gate``.
"""
from __future__ import annotations

from typing import Any, Literal

from lumina_core.evolution.twin_mode_types import (
    canonicalize_twin_mode,
    authority_for_mode,
)
from lumina_core.logging_utils import get_logger
from lumina_core.risk.real_multi_gate import twin_judgment_subordinate_to_real_gates

logger = get_logger("lumina.evolution.twin_discipline")

# Align with organism_autonomy high-conf band
HIGH_CONF_THRESHOLD = 0.80

# Pure REAL capital modes — Twin never sole-authorizes capital or DNA promotion
HARD_REAL_CAPITAL = frozenset({"real", "live", "prod", "production"})
# Pre-REAL dress rehearsal: SIM account + REAL-like risk guards
DRESS_REHEARSAL_CAPITAL = frozenset({"sim_real_guard"})
# Backward-compat alias: anything that must not sole-execute REAL money
REAL_LIKE = HARD_REAL_CAPITAL | DRESS_REHEARSAL_CAPITAL

TwinValuesRole = Literal["explore_pass", "values_active", "values_inside_gates"]


def is_real_like_capital(mode: str | None) -> bool:
    """True when capital path must not sole-execute REAL money (includes dress rehearsal)."""
    return str(mode or "").strip().lower() in REAL_LIKE


def is_hard_real_capital(mode: str | None) -> bool:
    """True only for live REAL capital modes (not sim_real_guard)."""
    return str(mode or "").strip().lower() in HARD_REAL_CAPITAL


def twin_values_role(capital_mode: str | None) -> TwinValuesRole:
    """SSOT: which authority regime the single Twin conscience uses.

    - explore_pass: free SIM/birth — organism learns; Twin shadow may log
    - values_active: sim_real_guard — apply trained REAL values to DNA judgment
    - values_inside_gates: REAL — judgment input only; multi-gate owns capital
    """
    m = str(capital_mode or "sim").strip().lower() or "sim"
    if m in HARD_REAL_CAPITAL:
        return "values_inside_gates"
    if m in DRESS_REHEARSAL_CAPITAL:
        return "values_active"
    return "explore_pass"


def twin_blocks_preference(capital_mode: str | None) -> bool:
    """Whether Twin APPROVE/VETO preference may block the exploration/DNA path."""
    return twin_values_role(capital_mode) != "explore_pass"


def birth_sim_high_conf_primary_ready(
    *,
    twin_mode: str | None,
    agreement_pct: float,
    samples: int,
    steve_label_samples: int,
    false_positive_pct: float = 0.0,
    min_samples: int = 30,
    min_agreement_pct: float = 80.0,
    min_steve_labels: int = 15,
    max_false_positive_pct: float = 15.0,
    capital_mode: str | None = "sim",
) -> dict[str, Any]:
    """Whether Twin may act as high-conf primary *values* judgment (values_active path).

    explore_pass: not "values primary" — loop free; use twin_primary_judgment_for_decision.
    values_inside_gates / hard REAL: never primary.
    values_active (sim_real_guard): requires assisted+ training bars.
    """
    mode = canonicalize_twin_mode(twin_mode)
    role = twin_values_role(capital_mode)
    failures: list[str] = []
    if role == "values_inside_gates" or is_hard_real_capital(capital_mode):
        failures.append("real_capital_not_primary_judgment")
    if role == "explore_pass":
        # Free SIM: Twin is not the values rem; readiness for "values primary" is N/A
        failures.append("explore_pass_values_not_gating")
    if mode == "shadow":
        failures.append("mode_is_shadow_propose_only")
    if int(samples) < int(min_samples):
        failures.append(f"samples={samples}<{min_samples}")
    if float(agreement_pct) < float(min_agreement_pct):
        failures.append(f"agreement_pct={agreement_pct}<{min_agreement_pct}")
    if int(steve_label_samples) < int(min_steve_labels):
        failures.append(f"steve_label_samples={steve_label_samples}<{min_steve_labels}")
    if float(false_positive_pct) > float(max_false_positive_pct):
        failures.append(f"false_positive_pct={false_positive_pct}>{max_false_positive_pct}")

    ready = len(failures) == 0
    return {
        "ready": ready,
        "twin_mode": mode,
        "twin_values_role": role,
        "authority": authority_for_mode(mode),
        "high_conf_threshold": HIGH_CONF_THRESHOLD,
        "capital_mode": str(capital_mode or "sim"),
        "failures": failures,
        "metrics": {
            "samples": int(samples),
            "agreement_pct": float(agreement_pct),
            "steve_label_samples": int(steve_label_samples),
            "false_positive_pct": float(false_positive_pct),
        },
        "note": (
            "One Twin DNA: explore_pass frees birth/SIM; values_active on sim_real_guard; "
            "REAL remains multi-gate (H2)."
        ),
    }


def twin_primary_judgment_for_decision(
    *,
    twin_mode: str | None,
    twin_confidence: float,
    twin_raw_recommendation: bool,
    twin_executable: bool,
    twin_effective_recommendation: bool,
    capital_mode: str | None = "sim",
    constitution_violations: int = 0,
    high_conf_threshold: float = HIGH_CONF_THRESHOLD,
    base_trained: bool | None = None,
) -> dict[str, Any]:
    """SSOT: may this decision treat Twin as primary for the *preference* path?

    - explore_pass (birth/sim): primary=True if constitution clean — Twin does not gate
      preference (organism learns). Twin may still shadow-score.
    - values_active (sim_real_guard): high-conf full_auto + base_trained + approve.
    - values_inside_gates (real): never primary sole; human multi-gate.

    Does not authorize REAL capital, PromotionGate bypass, or constitution override.
    """
    mode = canonicalize_twin_mode(twin_mode)
    role = twin_values_role(capital_mode)
    failures: list[str] = []
    if int(constitution_violations or 0) > 0:
        failures.append("constitution_violations")

    if role == "values_inside_gates":
        failures.append("real_capital_requires_human_multi_gate")
    elif role == "explore_pass":
        # Free learn loop: Twin preference never blocks (constitution already checked).
        # base_trained is still enforced at Birth *start* (API gate), not per tick.
        primary = len(failures) == 0
        return {
            "primary": primary,
            "twin_mode": mode,
            "capital_mode": str(capital_mode or "sim"),
            "twin_values_role": role,
            "failures": failures,
            "role": "explore_pass_no_twin_preference_gate" if primary else "blocked",
            "shadow_raw_recommendation": bool(twin_raw_recommendation),
            "never_bypasses": (
                "constitution",
                "sandbox",
                "promotion_gate",
                "real_human_approve",
            ),
        }
    else:
        # values_active — apply trained REAL conscience
        ready = base_trained
        if ready is None:
            try:
                from lumina_core.evolution.twin_base_training import is_twin_birth_ready

                ready = is_twin_birth_ready()
            except Exception:
                ready = False
        if not bool(ready):
            failures.append("base_training_incomplete")
        if float(twin_confidence) < float(high_conf_threshold):
            failures.append(f"confidence_below_{high_conf_threshold}")
        if mode == "shadow":
            failures.append("mode_shadow_propose_only")
        if mode != "full_auto":
            failures.append("mode_not_full_auto_for_primary_approve")
        if not bool(twin_executable):
            failures.append("not_executable")
        if not bool(twin_effective_recommendation):
            failures.append("effective_recommendation_false")
        if not bool(twin_raw_recommendation):
            failures.append("raw_recommendation_veto")

    primary = len(failures) == 0
    return {
        "primary": primary,
        "twin_mode": mode,
        "capital_mode": str(capital_mode or "sim"),
        "twin_values_role": role,
        "failures": failures,
        "role": (
            "primary_values_active_judgment"
            if primary and role == "values_active"
            else "primary_birth_sim_judgment"
            if primary
            else "subordinate_or_human_required"
        ),
        "never_bypasses": (
            "constitution",
            "sandbox",
            "shadow",
            "promotion_gate",
            "real_human_approve",
        ),
    }


def full_auto_allowed_for_capital_mode(capital_mode: str | None) -> tuple[bool, str]:
    """full_auto Twin *mode* is allowed for explore_pass and values_active, not hard REAL."""
    if is_hard_real_capital(capital_mode):
        return False, "full_auto_forbidden_in_real_capital"
    # sim_real_guard: full_auto OK for DNA judgment (values_active); still no real $
    return True, "ok"


def discipline_snapshot(
    *,
    twin_mode: str | None,
    capital_mode: str | None = "sim",
    metrics: dict[str, Any] | None = None,
    readiness: dict[str, Any] | None = None,
    auto_promote_when_ready: bool = False,
    auto_promote_full_auto: bool = False,
) -> dict[str, Any]:
    """Operator-facing H4 discipline panel."""
    m = metrics or {}
    samples = int(m.get("samples", 0) or 0)
    agreement = float(m.get("agreement_pct", 0.0) or 0.0)
    steve = int(m.get("steve_label_samples", 0) or 0)
    fp = float(m.get("false_positive_pct", 100.0) or 100.0)

    primary = birth_sim_high_conf_primary_ready(
        twin_mode=twin_mode,
        agreement_pct=agreement,
        samples=samples,
        steve_label_samples=steve,
        false_positive_pct=fp,
        capital_mode=capital_mode,
    )
    fa_ok, fa_reason = full_auto_allowed_for_capital_mode(capital_mode)
    twin_floor = twin_judgment_subordinate_to_real_gates(
        twin_recommendation=True,
        twin_executable=True,
        twin_mode=twin_mode or "full_auto",
        capital_mode=capital_mode,
    )

    return {
        "schema": "twin_discipline_v1",
        "twin_mode": canonicalize_twin_mode(twin_mode),
        "capital_mode": str(capital_mode or "sim"),
        "birth_sim_high_conf_primary": primary,
        "full_auto_allowed_for_capital": fa_ok,
        "full_auto_block_reason": None if fa_ok else fa_reason,
        "real_capital_twin_floor": twin_floor,
        "auto_promote_when_ready": bool(auto_promote_when_ready),
        "auto_promote_full_auto": bool(auto_promote_full_auto),
        "readiness": readiness or {},
        "twin_values_role": twin_values_role(capital_mode),
        "policy": {
            "promote_one_step_only": True,
            "full_auto_requires_steve_labels": True,
            "full_auto_forbidden_in_real_capital": True,
            "one_twin_dna_dual_authority": True,
            "explore_pass_birth_sim": True,
            "values_active_sim_real_guard": True,
            "values_inside_gates_real": True,
            "base_training_is_real_conscience": True,
            "auto_promote_default_off": True,
            "auto_promote_full_auto_default_off": True,
            "human_labels_drive_calibration": True,
        },
        "next_step": (
            "Label twin review queue + train REAL-standard conscience; "
            "promote shadow→assisted when gate green; full_auto never in hard REAL."
            if not primary["ready"] and twin_values_role(capital_mode) != "explore_pass"
            else (
                "explore_pass: Birth/SIM free learn loop; Twin shadow logs, no preference gate."
                if twin_values_role(capital_mode) == "explore_pass"
                else (
                    "values_active: Twin applies REAL conscience under sim_real_guard."
                    if fa_ok and twin_values_role(capital_mode) == "values_active"
                    else "REAL capital: Twin cannot sole-execute; use human multi-gate (H2)."
                )
            )
        ),
    }


def build_twin_promote_ops_report(
    *,
    mode_status: dict[str, Any] | None = None,
    controller: Any | None = None,
    capital_mode: str | None = None,
) -> dict[str, Any]:
    """T6: Operator report for shadow→assisted→full_auto promote path (fail-closed).

    Does not promote. Use TwinModeController.try_promote / CLI for gated upgrades.
    """
    status: dict[str, Any] = {}
    if controller is not None and hasattr(controller, "status"):
        status = dict(controller.status() or {})
    elif isinstance(mode_status, dict):
        status = dict(mode_status)
    else:
        status = {}

    mode = canonicalize_twin_mode(status.get("mode") or "shadow")
    cap = str(
        capital_mode
        or status.get("capital_mode_hint")
        or (status.get("mode_ssot") or {}).get("capital_mode")
        or "sim"
    )
    readiness = status.get("readiness") if isinstance(status.get("readiness"), dict) else {}
    assisted = readiness.get("assisted") if isinstance(readiness.get("assisted"), dict) else {}
    full_auto = readiness.get("full_auto") if isinstance(readiness.get("full_auto"), dict) else {}
    fa_ok, fa_reason = full_auto_allowed_for_capital_mode(cap)
    mode_ssot = status.get("mode_ssot") if isinstance(status.get("mode_ssot"), dict) else {}

    metrics = status.get("metrics") if isinstance(status.get("metrics"), dict) else {}
    primary = birth_sim_high_conf_primary_ready(
        twin_mode=mode,
        agreement_pct=float(metrics.get("agreement_pct", 0.0) or 0.0),
        samples=int(metrics.get("samples", 0) or 0),
        steve_label_samples=int(metrics.get("steve_label_samples", 0) or 0),
        false_positive_pct=float(metrics.get("false_positive_pct", 100.0) or 100.0),
        capital_mode=cap,
    )

    ladder = [
        {
            "id": "seed_shadow",
            "title": "Live mode is shadow (or higher via gate only)",
            "ok": mode in {"shadow", "assisted", "full_auto"},
            "actual": mode,
            "action": "python -m lumina_launcher twin mode",
        },
        {
            "id": "labels",
            "title": "Steve labels for assisted promote",
            "ok": int(metrics.get("steve_label_samples", 0) or 0) >= 15
            or bool(assisted.get("promoted")),
            "actual": int(metrics.get("steve_label_samples", 0) or 0),
            "target": 15,
            "action": "python -m lumina_launcher twin review",
        },
        {
            "id": "ready_assisted",
            "title": "Gate ready for assisted",
            "ok": bool(assisted.get("promoted")),
            "actual": assisted,
            "action": "python -m lumina_launcher twin promote assisted",
        },
        {
            "id": "mode_assisted_or_higher",
            "title": "Live mode assisted or full_auto",
            "ok": mode in {"assisted", "full_auto"},
            "actual": mode,
            "action": "Promote only when ready_assisted",
        },
        {
            "id": "ready_full_auto",
            "title": "Gate ready for full_auto (SIM capital only)",
            "ok": bool(full_auto.get("promoted")) and fa_ok,
            "actual": {"gate": full_auto, "capital_ok": fa_ok, "capital_reason": fa_reason},
            "action": (
                "python -m lumina_launcher twin promote full_auto"
                if fa_ok
                else f"Blocked: {fa_reason}"
            ),
        },
        {
            "id": "full_auto_not_in_real",
            "title": "full_auto forbidden under REAL capital hint",
            "ok": fa_ok or mode != "full_auto",
            "actual": {"capital_mode": cap, "mode": mode},
            "action": "Keep capital_mode_hint=sim/birth for full_auto judgment",
        },
    ]

    open_items = [x for x in ladder if not x["ok"]]
    actions: list[str] = []
    for x in open_items:
        a = str(x.get("action") or "")
        if a and a not in actions:
            actions.append(a)
    if mode == "shadow" and bool(assisted.get("promoted")):
        actions.insert(0, "python -m lumina_launcher twin promote assisted")
    if mode == "assisted" and bool(full_auto.get("promoted")) and fa_ok:
        actions.insert(0, "python -m lumina_launcher twin promote full_auto")

    return {
        "schema": "twin_promote_ops_v1",
        "ok": mode in {"assisted", "full_auto"} and primary.get("ready") is not False,
        "live_mode": mode,
        "capital_mode": cap,
        "authority": authority_for_mode(mode),
        "mode_ssot": mode_ssot
        or {
            "live_mode": mode,
            "config_is_seed_only": True,
            "full_auto_requires_promotion_gate": True,
        },
        "readiness": {
            "assisted": {
                "ready": bool(assisted.get("promoted")),
                "fail_reasons": list(assisted.get("fail_reasons") or []),
                "reason": assisted.get("reason"),
            },
            "full_auto": {
                "ready": bool(full_auto.get("promoted")),
                "fail_reasons": list(full_auto.get("fail_reasons") or []),
                "reason": full_auto.get("reason"),
                "capital_allows": fa_ok,
                "capital_block_reason": None if fa_ok else fa_reason,
            },
        },
        "birth_sim_high_conf_primary": primary,
        "ladder": ladder,
        "open_items": [x["id"] for x in open_items],
        "ordered_actions": actions,
        "auto_promote_when_ready": bool(status.get("auto_promote_when_ready")),
        "auto_promote_full_auto_when_ready": bool(
            status.get("auto_promote_full_auto_when_ready")
        ),
        "policy": {
            "yaml_cannot_seed_full_auto": True,
            "promote_only_via_gate": True,
            "full_auto_forbidden_in_real_capital": True,
            "auto_promote_full_auto_default_off": True,
            "one_step_at_a_time": True,
        },
        "commands": {
            "mode": "python -m lumina_launcher twin mode",
            "review": "python -m lumina_launcher twin review",
            "train": "python -m lumina_launcher twin train",
            "promote_assisted": "python -m lumina_launcher twin promote assisted",
            "promote_full_auto": "python -m lumina_launcher twin promote full_auto",
            "ops_report": "python scripts/validation/twin_promote_ops.py",
        },
        "next_step": (
            actions[0]
            if actions
            else "Twin promote path ready — use full_auto only in birth/SIM high-conf judgment"
        ),
    }


__all__ = [
    "DRESS_REHEARSAL_CAPITAL",
    "HARD_REAL_CAPITAL",
    "HIGH_CONF_THRESHOLD",
    "REAL_LIKE",
    "TwinValuesRole",
    "birth_sim_high_conf_primary_ready",
    "build_twin_promote_ops_report",
    "discipline_snapshot",
    "full_auto_allowed_for_capital_mode",
    "is_hard_real_capital",
    "is_real_like_capital",
    "twin_blocks_preference",
    "twin_primary_judgment_for_decision",
    "twin_values_role",
]
