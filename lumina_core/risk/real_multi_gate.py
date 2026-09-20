"""REAL multi-gate SSOT (H2) — human + maturation + constitution; Twin never sole-authorizes.

Fail-closed. Twin judgment is allowed only *inside* gates (assisted/full_auto for DNA
proposals in SIM paths). REAL capital mode and REAL DNA promotion always require
explicit human approval and maturation eligibility.

Non-bypassable gates (all must pass for REAL capital):
1. Maturation ladder milestones (certificate, evolution proof, sim stability,
   promotion gate, perfect birth autonomy)
2. Explicit human REAL approval milestone (``human_real_approval``)
3. Capital aperture lineage + Final Arbitration on each order (admission)
4. REAL DNA promotion: ApprovalChain + require_human_approval mandatory
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from lumina_core.engine.trade_reconciler.real_recon_gate import (
    evaluate_real_broker_recon_gate,
)
from lumina_core.evolution.twin_mode_types import apply_mode_authority, canonicalize_twin_mode
from lumina_core.logging_utils import get_logger
from lumina_core.maturity.maturation_progress import (
    load_maturation_progress,
    maturation_eligible_for_real,
)
from lumina_core.risk.capital_aperture_lineage import (
    aperture_coverage_ready_for_real,
    evaluate_aperture_coverage_gate,
)

logger = get_logger("lumina.risk.real_multi_gate")

# Gates that Twin / full_auto must never short-circuit
REAL_GATE_IDS: tuple[str, ...] = (
    "maturation_eligible",
    "human_real_approval",
    "capital_aperture_lineage",
    "final_arbitration",
    "real_dna_human_approval_chain",
)

__all__ = [
    "REAL_GATE_IDS",
    "assert_twin_cannot_authorize_real_mode",
    "evaluate_real_capital_readiness",
    "real_dna_promotion_allowed",
    "real_mode_switch_allowed",
    "run_real_multi_gate_dry_run",
    "twin_judgment_subordinate_to_real_gates",
]


def evaluate_real_capital_readiness(
    workspace_root: Path | str,
) -> dict[str, Any]:
    """Full readiness snapshot for REAL capital (operator + API).

    Aperture ``soft_pass`` is ops yellow and never counts as REAL-green.
    Empty ``decision_log`` samples are not ready. Coverage and recon are
    evaluated; aperture/FA/DNA-human are never hardcoded ``ok: True``.
    """
    root = Path(workspace_root)

    eligible, blockers = maturation_eligible_for_real(root)
    progress = load_maturation_progress(root)
    reached = set(progress.milestones_reached)
    human_ok = "human_real_approval" in reached
    live = "real_trading_live" in reached

    aperture = evaluate_aperture_coverage_gate(workspace_root=root)
    aperture_ready = aperture_coverage_ready_for_real(aperture)
    recon = _evaluate_workspace_recon(root)
    fa_gate = _evaluate_final_arbitration_gate(aperture=aperture, recon=recon)
    dna_gate = _evaluate_dna_human_chain(root)

    aperture_blockers = _aperture_readiness_blockers(aperture, ready=aperture_ready)
    gate_results = {
        "maturation_eligible": {
            "ok": eligible,
            "blockers": list(blockers),
        },
        "human_real_approval": {
            "ok": human_ok,
            "blockers": [] if human_ok else ["Operator REAL approval not recorded"],
        },
        "capital_aperture_lineage": {
            "ok": aperture_ready,
            "soft_pass": bool(aperture.get("soft_pass")),
            "certified": bool(aperture.get("certified")),
            "ops_status": aperture.get("ops_status"),
            "reason": aperture.get("reason"),
            "sample_size": aperture.get("sample_size"),
            "lineage_coverage_pct": aperture.get("lineage_coverage_pct"),
            "blockers": aperture_blockers,
            "note": (
                "Enforced per-order at admission; REAL-green only when coverage is "
                "certified (soft_pass is ops yellow, never green)."
            ),
        },
        "final_arbitration": fa_gate,
        "real_dna_human_approval_chain": dna_gate,
    }
    all_ok = (
        eligible
        and human_ok
        and aperture_ready
        and bool(fa_gate.get("ok"))
        and bool(dna_gate.get("ok"))
    )
    hard_blockers: list[str] = []
    if not eligible:
        hard_blockers.extend(blockers)
    if not human_ok:
        hard_blockers.append("Operator REAL approval required (POST /api/maturity/approve-real)")
    hard_blockers.extend(aperture_blockers)
    if not fa_gate.get("ok"):
        hard_blockers.extend(str(b) for b in list(fa_gate.get("blockers") or []))
    if not dna_gate.get("ok"):
        hard_blockers.extend(str(b) for b in list(dna_gate.get("blockers") or []))

    if not all_ok:
        logger.warning(
            "real_multi_gate.readiness_not_green ready=%s blockers=%s",
            all_ok,
            hard_blockers,
        )

    return {
        "ready_for_real_capital": all_ok,
        "maturation_eligible": eligible,
        "human_real_approval": human_ok,
        "real_trading_live": live,
        "blockers": hard_blockers,
        "gates": gate_results,
        "aperture_coverage": aperture,
        "broker_recon": recon,
        "twin_can_bypass": False,
        "policy": {
            "twin_role": "judgment_inside_gates_only",
            "human_required_for_real_mode": True,
            "human_required_for_real_dna_promotion": True,
            "auto_evolve_never_arms_real": True,
            "soft_pass_is_ops_yellow_not_real_green": True,
            "empty_samples_not_ready": True,
        },
    }


def real_mode_switch_allowed(workspace_root: Path | str) -> tuple[bool, list[str]]:
    """Whether operator may switch deck/runtime to REAL capital mode."""
    snap = evaluate_real_capital_readiness(workspace_root)
    return bool(snap["ready_for_real_capital"]), list(snap["blockers"])


def run_real_multi_gate_dry_run(
    workspace_root: Path | str | None = None,
) -> dict[str, Any]:
    """T3: Read-only REAL multi-gate dry-run — never switches mode or arms capital.

    Reports maturation + human approve-real readiness, twin non-bypass, DNA promotion
    invariant, and aperture coverage soft status. Exit tooling uses this for CI/ops.
    """
    root = Path(workspace_root) if workspace_root else Path.cwd()
    readiness = evaluate_real_capital_readiness(root)
    switch_ok = bool(readiness.get("ready_for_real_capital"))
    switch_blockers = list(readiness.get("blockers") or [])

    # Twin full_auto cannot sole-authorize REAL
    twin_floor = twin_judgment_subordinate_to_real_gates(
        twin_recommendation=True,
        twin_executable=True,
        twin_mode="full_auto",
        capital_mode="real",
    )
    twin_invariant_ok = (
        twin_floor.get("executable") is False
        and twin_floor.get("effective_recommendation") is False
        and twin_floor.get("real_capital_floor") is True
    )
    try:
        assert_twin_cannot_authorize_real_mode(
            twin_full_auto=True, twin_recommendation=True
        )
        twin_assert_ok = True
        twin_assert_error = None
    except AssertionError as exc:
        twin_assert_ok = False
        twin_assert_error = str(exc)

    # DNA promotion: REAL without human must fail
    dna_no_human_ok, dna_no_human_reason = real_dna_promotion_allowed(
        mode="real",
        require_human_approval=False,
        explicit_human_approval=True,
        base_promoted=True,
        has_approval_signatures=True,
    )
    dna_invariant = (dna_no_human_ok is False) and (
        "human" in str(dna_no_human_reason).lower()
    )

    aperture = readiness.get("aperture_coverage")
    if not isinstance(aperture, dict):
        aperture = {}
    recon = readiness.get("broker_recon")
    if not isinstance(recon, dict):
        recon = {"ok": False, "failures": ["recon_not_evaluated"]}

    checks = {
        "twin_cannot_authorize_real": twin_invariant_ok and twin_assert_ok,
        "real_dna_requires_human": dna_invariant,
        "readiness_loaded": isinstance(readiness, dict),
        "twin_can_bypass_flag_false": readiness.get("twin_can_bypass") is False,
        "recon_evaluated": "ok" in recon,
    }
    all_invariants = all(checks.values())
    # dry_run "ready_for_real" mirrors switch — informational only
    return {
        "schema": "real_multi_gate_dry_run_v1",
        "ok": all_invariants,  # invariants hold (not "ready for REAL")
        "ready_for_real_capital": bool(readiness.get("ready_for_real_capital")),
        "mode_switch_allowed": bool(switch_ok),
        "blockers": list(switch_blockers),
        "invariants": checks,
        "twin_floor": twin_floor,
        "twin_assert_error": twin_assert_error,
        "dna_promotion_without_human": {
            "allowed": dna_no_human_ok,
            "reason": dna_no_human_reason,
            "must_be_false": True,
            "invariant_ok": dna_invariant,
        },
        "readiness": readiness,
        "aperture_coverage": {
            "ok": aperture.get("ok"),
            "soft_pass": aperture.get("soft_pass"),
            "certified": aperture.get("certified"),
            "ops_status": aperture.get("ops_status"),
            "reason": aperture.get("reason"),
            "sample_size": aperture.get("sample_size"),
            "lineage_coverage_pct": aperture.get("lineage_coverage_pct"),
            "message": aperture.get("message"),
        },
        "broker_recon": recon,
        "policy": {
            "never_arms_real": True,
            "never_calls_approve_real": True,
            "twin_role": "judgment_inside_gates_only",
            "timeout_fill_no_economic_ledger": True,
            "soft_pass_is_ops_yellow_not_real_green": True,
            "next_step_if_not_ready": (
                "Complete maturation milestones + POST /api/maturity/approve-real "
                "+ certified aperture coverage + REAL recon config "
                "before any REAL mode switch; keep reconcile_fills=true for REAL."
            ),
        },
        "gate_ids": list(REAL_GATE_IDS),
    }


def real_dna_promotion_allowed(
    *,
    mode: str,
    require_human_approval: bool,
    explicit_human_approval: bool = False,
    base_promoted: bool,
    has_approval_signatures: bool = False,
) -> tuple[bool, str]:
    """Fail-closed REAL DNA promotion eligibility (generation path).

    Twin recommendation is intentionally *not* a parameter — it cannot authorize.
    Human proof = require_human_approval AND (signatures | explicit flag);
    ApprovalChain.verify remains the cryptographic check when proceeding.
    """
    m = str(mode or "").strip().lower()
    if m != "real":
        return True, "not_real_mode"
    if not require_human_approval:
        return False, "real_human_approval_mandatory"
    if not base_promoted:
        return False, "promotion_not_eligible_before_approval"
    if not (explicit_human_approval or has_approval_signatures):
        return False, "explicit_human_approval_or_signatures_required"
    return True, "ok_proceed_to_approval_chain"


def twin_judgment_subordinate_to_real_gates(
    *,
    twin_recommendation: bool,
    twin_executable: bool,
    twin_mode: str | None,
    capital_mode: str | None,
) -> dict[str, Any]:
    """Prove Twin cannot sole-authorize REAL capital operations.

    Returns effective authority fields for consumers (deck, generation, birth).
    """
    cap = str(capital_mode or "sim").strip().lower()
    # Track D: capital floor is inside apply_mode_authority (REAL never executable).
    auth = apply_mode_authority(
        raw_recommendation=bool(twin_recommendation),
        mode=twin_mode,
        capital_mode=cap,
    )
    real_capital = bool(auth.get("real_capital_floor"))
    return {
        **auth,
        "capital_mode": cap,
        "twin_mode": canonicalize_twin_mode(twin_mode),
        "real_capital_floor": real_capital,
        "reason": (
            "twin_cannot_authorize_real_capital" if real_capital else "mode_authority"
        ),
        "raw_recommendation": bool(twin_recommendation),
        "raw_executable": bool(twin_executable),
    }


def assert_twin_cannot_authorize_real_mode(
    *,
    twin_full_auto: bool,
    twin_recommendation: bool,
) -> None:
    """Invariant check for tests/ops — twin alone never yields real mode switch OK."""
    result = twin_judgment_subordinate_to_real_gates(
        twin_recommendation=twin_recommendation or twin_full_auto,
        twin_executable=True,
        twin_mode="full_auto" if twin_full_auto else "shadow",
        capital_mode="real",
    )
    if result.get("effective_recommendation") or result.get("executable"):
        raise AssertionError("H2 invariant broken: Twin authorized REAL capital")


def _load_workspace_mapping(root: Path) -> tuple[dict[str, Any] | None, str | None]:
    path = root / "config.yaml"
    if not path.is_file():
        return None, "workspace_config_yaml_missing"
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"workspace_config_yaml_unreadable:{exc}"
    if not isinstance(raw, dict):
        return None, "workspace_config_yaml_not_mapping"
    return raw, None


def _evaluate_workspace_recon(root: Path) -> dict[str, Any]:
    """Evaluate REAL recon from workspace config — never hardcode reconcile_fills=True."""
    cfg, err = _load_workspace_mapping(root)
    if cfg is None:
        return {
            "schema": "real_broker_recon_gate_v1",
            "ok": False,
            "failures": [err or "workspace_config_yaml_missing"],
            "message": "REAL recon config fail-closed: workspace config unavailable",
        }
    if "reconcile_fills" not in cfg:
        return {
            "schema": "real_broker_recon_gate_v1",
            "ok": False,
            "failures": ["reconcile_fills_not_declared"],
            "message": "REAL recon config fail-closed: reconcile_fills not declared",
        }
    broker = cfg.get("broker") if isinstance(cfg.get("broker"), dict) else {}
    nt = broker.get("ninjatrader") if isinstance(broker.get("ninjatrader"), dict) else {}
    live_provider = str(broker.get("live_provider") or "").strip()
    nt_enabled_raw = nt.get("enabled") if "enabled" in nt else None
    nt_enabled = bool(nt_enabled_raw) if nt_enabled_raw is not None else None
    live_configured = bool(live_provider) if live_provider else None
    method = cfg.get("reconciliation_method")
    timeout = cfg.get("reconciliation_timeout_seconds")
    try:
        return evaluate_real_broker_recon_gate(
            trade_mode="real",
            reconcile_fills=bool(cfg.get("reconcile_fills")),
            reconciliation_method=str(method) if method is not None else "websocket",
            reconciliation_timeout_seconds=(
                timeout if timeout is not None else 15.0
            ),
            live_broker_configured=live_configured,
            ninjatrader_enabled=nt_enabled,
        )
    except Exception as exc:
        return {
            "schema": "real_broker_recon_gate_v1",
            "ok": False,
            "failures": [f"recon_gate_error:{exc}"],
            "message": f"REAL recon config fail-closed: {exc}",
        }


def _aperture_readiness_blockers(aperture: dict[str, Any], *, ready: bool) -> list[str]:
    if ready:
        return []
    reason = str(aperture.get("reason") or "aperture_coverage_not_certified")
    sample = aperture.get("sample_size")
    if reason == "no_samples" or int(sample or 0) <= 0:
        return ["empty_decision_log_not_ready"]
    if reason == "thin_sample" or bool(aperture.get("soft_pass")):
        return [f"aperture_coverage_soft_pass:{reason}"]
    if bool(aperture.get("hard_fail")):
        return [f"aperture_coverage_below_target:{aperture.get('lineage_coverage_pct')}"]
    return [f"aperture_coverage_not_certified:{reason}"]


def _evaluate_final_arbitration_gate(
    *,
    aperture: dict[str, Any],
    recon: dict[str, Any],
) -> dict[str, Any]:
    """FA is not green from a static note — requires coverage evidence + recon."""
    snap = aperture.get("snapshot") if isinstance(aperture.get("snapshot"), dict) else {}
    fa_n = int(snap.get("final_arbitration_sample_size") or 0)
    min_n = int(aperture.get("min_sample_size") or 10)
    recon_ok = bool(recon.get("ok"))
    coverage_ready = aperture_coverage_ready_for_real(aperture)
    blockers: list[str] = []
    if fa_n <= 0:
        blockers.append("no_final_arbitration_samples")
    elif fa_n < min_n:
        blockers.append(f"thin_final_arbitration_samples:{fa_n}<{min_n}")
    if not coverage_ready:
        blockers.append("aperture_coverage_not_certified")
    if not recon_ok:
        recon_failures = recon.get("failures") or []
        if recon_failures:
            blockers.extend(f"broker_recon:{f}" for f in recon_failures)
        else:
            blockers.append("broker_recon_not_ok")
    return {
        "ok": len(blockers) == 0,
        "sample_size": fa_n,
        "min_sample_size": min_n,
        "coverage_certified": coverage_ready,
        "recon_ok": recon_ok,
        "blockers": blockers,
        "note": (
            "FA readiness requires certified lineage coverage, FA-stage samples, "
            "and REAL recon config. Empty samples are not green."
        ),
    }


def _evaluate_dna_human_chain(root: Path) -> dict[str, Any]:
    """Prove REAL DNA promotion cannot skip human — never hardcoded ok."""
    allowed, reason = real_dna_promotion_allowed(
        mode="real",
        require_human_approval=False,
        explicit_human_approval=True,
        base_promoted=True,
        has_approval_signatures=True,
    )
    invariant_ok = allowed is False and "human" in str(reason).lower()
    blockers: list[str] = []
    if not invariant_ok:
        blockers.append("real_dna_promotion_skips_human")
    cfg, err = _load_workspace_mapping(root)
    if cfg is None:
        blockers.append(err or "workspace_config_yaml_missing")
    else:
        real_cfg = cfg.get("real") if isinstance(cfg.get("real"), dict) else {}
        if real_cfg.get("approval_required") is not True:
            blockers.append("real.approval_required_not_true")
    return {
        "ok": len(blockers) == 0,
        "blockers": blockers,
        "invariant_blocks_without_human": invariant_ok,
        "invariant_reason": reason,
        "note": (
            "generation_runner + evolution API require human chain in REAL; "
            "workspace config must declare real.approval_required=true."
        ),
    }
