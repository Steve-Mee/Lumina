"""REAL readiness evidence (SC-3/SC-5) — coverage, recon, FA, DNA-human.

Never hardcodes gate ``ok: True``. Empty samples and missing config fail-closed
for REAL-green. ``soft_pass`` stays ops yellow.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import yaml

from lumina_core.engine.trade_reconciler.real_recon_gate import (
    evaluate_real_broker_recon_gate,
)
from lumina_core.risk.capital_aperture_coverage import aperture_coverage_ready_for_real

DnaPromotionFn = Callable[..., tuple[bool, str]]

__all__ = [
    "aperture_readiness_blockers",
    "evaluate_dna_human_chain",
    "evaluate_final_arbitration_gate",
    "evaluate_workspace_recon",
    "load_workspace_mapping",
]


def load_workspace_mapping(root: Path) -> tuple[dict[str, Any] | None, str | None]:
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


def evaluate_workspace_recon(root: Path) -> dict[str, Any]:
    """Evaluate REAL recon from workspace config — never hardcode reconcile_fills=True."""
    cfg, err = load_workspace_mapping(root)
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
    broker_raw = cfg.get("broker")
    broker: dict[str, Any] = broker_raw if isinstance(broker_raw, dict) else {}
    nt_raw = broker.get("ninjatrader")
    nt: dict[str, Any] = nt_raw if isinstance(nt_raw, dict) else {}
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
            reconciliation_timeout_seconds=(timeout if timeout is not None else 15.0),
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


def aperture_readiness_blockers(aperture: dict[str, Any], *, ready: bool) -> list[str]:
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


def evaluate_final_arbitration_gate(
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


def evaluate_dna_human_chain(
    root: Path,
    *,
    promotion_allowed: DnaPromotionFn,
) -> dict[str, Any]:
    """Prove REAL DNA promotion cannot skip human — never hardcoded ok."""
    allowed, reason = promotion_allowed(
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
    cfg, err = load_workspace_mapping(root)
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
