"""Plateau resume risk calculation (extracted from birth_status_enricher.py per god-surface guard plan).

Keeps birth_status_enricher thin; dedicated bounded module for resume risk logic.
"""

from __future__ import annotations

from typing import Any, Dict

from lumina_core.birth.checkpoint import load_checkpoint_state
from lumina_core.birth.config import load_birth_v2_config
from lumina_core.birth.curriculum import CurriculumStage, stage_pass_trades
from lumina_core.birth.plateau_escalator import plateau_min_stage_trades


def resume_plateau_risk_fields(svc: Any) -> Dict[str, Any]:
    """Warn UI when resuming a polluted checkpoint would re-trigger plateau without quarantine."""
    if svc.is_running() or not svc.checkpoint_resumable():
        return {"resume_plateau_risk": False}
    ckpt = load_checkpoint_state(svc.workspace_root)
    metrics = ckpt.get("stage_metrics") if isinstance(ckpt, dict) else None
    if not isinstance(metrics, dict):
        return {"resume_plateau_risk": False}
    stage_raw = str(metrics.get("curriculum_stage_scope") or ckpt.get("curriculum_stage") or "")
    try:
        stage = CurriculumStage(stage_raw.strip().lower())
    except ValueError:
        return {"resume_plateau_risk": False}
    cfg = load_birth_v2_config(svc.workspace_root).curriculum
    stage_trades = int(metrics.get("stage_trades", 0) or 0)
    required = stage_pass_trades(stage, cfg)
    min_plateau = plateau_min_stage_trades(stage, cfg)
    quarantine_active = bool(metrics.get("plateau_quarantine_active", False))
    evolution_exhausted = int(metrics.get("plateau_evolution_step", 0) or 0) >= int(
        cfg.plateau_max_evolution_steps
    )
    velocity_stalls = int(metrics.get("velocity_stall_attempts", 0) or 0)
    risk = (
        not quarantine_active
        and stage_trades >= min_plateau
        and (
            evolution_exhausted
            or velocity_stalls >= int(cfg.velocity_stall_attempt_threshold)
            or stage_trades >= required
        )
    )
    return {
        "resume_plateau_risk": bool(risk),
        "resume_plateau_risk_trades": stage_trades,
        "resume_plateau_risk_required": required,
    }


__all__ = ["resume_plateau_risk_fields"]
