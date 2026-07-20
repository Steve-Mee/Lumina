"""Thin Phase 2 hooks for WallAdaptationHandler — keeps birth handlers non-god.

Slice E: closed-loop wiring lives here (not in stage_loop, not bloating the handler).
All entry points fail-closed: missing/inactive orchestrator → no-op / base cfg.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig


def bind_orchestrator_twin(orch: Any, registry: Any | None) -> None:
    """Late-bind Approval Twin from registry if orchestrator has none."""
    if orch is None:
        return
    if getattr(orch, "approval_twin", None) is not None:
        return
    if registry is None:
        return
    twin = getattr(registry, "approval_twin", None)
    if twin is not None:
        orch.approval_twin = twin


def cfg_with_wall_thresholds(
    cfg: BirthCurriculumConfig,
    payload: dict[str, Any],
) -> BirthCurriculumConfig:
    """Shadow-replace stall/stagnation thresholds on a cfg copy (single wall engine)."""
    return replace(
        cfg,
        certified_stage_stall_wall_sec=max(
            300,
            int(
                payload.get(
                    "effective_stall_wall_sec",
                    cfg.certified_stage_stall_wall_sec,
                )
            ),
        ),
        stage1_winrate_stagnation_rollouts=max(
            1,
            int(
                payload.get(
                    "effective_winrate_stagnation_rollouts",
                    cfg.stage1_winrate_stagnation_rollouts,
                )
            ),
        ),
        stage2_hold_stagnation_rollouts=max(
            1,
            int(
                payload.get(
                    "effective_hold_stagnation_rollouts",
                    cfg.stage2_hold_stagnation_rollouts,
                )
            ),
        ),
    )


def phase2_wall_closed_loop(
    orch: Any,
    *,
    cfg: BirthCurriculumConfig,
    registry: Any | None,
    correlation_id: str,
    stage_name: str,
    ctx: dict[str, Any],
) -> tuple[dict[str, Any] | None, BirthCurriculumConfig]:
    """Evaluate dynamic wall; return (meta, eval_cfg). Fail-closed → (None|meta, base cfg)."""
    if orch is None or not getattr(orch, "is_active", lambda: False)():
        return None, cfg
    try:
        bind_orchestrator_twin(orch, registry)
        decision = orch.evaluate_dynamic_wall(
            correlation_id=correlation_id,
            stage=stage_name,
            stage_trades=int(ctx.get("stage_trades", 0)),
            required=int(ctx.get("required", 0)),
            winrate_slope=float(ctx.get("winrate_slope", 0.0)),
            winrate_stagnation_count=int(ctx.get("winrate_stagnation_count", 0)),
            hold_stagnation_count=int(ctx.get("hold_stagnation_count", 0)),
            elapsed_stage_sec=float(ctx.get("elapsed_stage_sec", 0.0)),
            regime=str(ctx.get("regime", "") or "") or None,
            constitution_violations=int(ctx.get("constitution_violations", 0)),
            apply=True,
        )
        meta = decision.to_dict()
        if not decision.applied or not decision.apply_payload:
            return meta, cfg
        eval_cfg = cfg_with_wall_thresholds(cfg, decision.apply_payload)
        meta["thresholds_applied"] = True
        meta["effective_cfg"] = {
            "certified_stage_stall_wall_sec": eval_cfg.certified_stage_stall_wall_sec,
            "stage1_winrate_stagnation_rollouts": eval_cfg.stage1_winrate_stagnation_rollouts,
            "stage2_hold_stagnation_rollouts": eval_cfg.stage2_hold_stagnation_rollouts,
        }
        return meta, eval_cfg
    except Exception:
        return None, cfg


def phase2_recovery_closed_loop(
    orch: Any,
    *,
    wall_state: Any,
    registry: Any | None,
    cfg: BirthCurriculumConfig,
    correlation_id: str,
    stage_name: str,
    ctx: dict[str, Any],
    learning_health: str,
    stage_trades: int,
    required: int,
    constitution_blocked: bool,
) -> dict[str, Any]:
    """Gated param + instance adapt for recovery signals. Empty dict when inactive."""
    if orch is None or not getattr(orch, "is_active", lambda: False)():
        return {}
    bind_orchestrator_twin(orch, registry)
    viol = int(ctx.get("constitution_violations", 1 if constitution_blocked else 0))
    tier = int(ctx.get("adaptation_tier", getattr(wall_state, "adaptation_tier", 0)) or 0)
    retries = int(
        ctx.get("retries_this_stage", getattr(wall_state, "retries_this_stage", 0)) or 0
    )
    out: dict[str, Any] = {}
    try:
        param_dec = orch.evaluate_param_adjustment(
            correlation_id=correlation_id,
            stage=stage_name,
            learning_health=learning_health,
            current_winrate_window=int(getattr(wall_state, "effective_winrate_window", 12)),
            current_reward_window=int(getattr(wall_state, "effective_reward_window", 12)),
            adaptation_tier=tier,
            post_volume_gate=stage_trades >= max(1, required),
            constitution_violations=viol,
            wall_state=wall_state,
            apply=True,
        )
        out["param"] = param_dec.to_dict()
    except Exception as exc:
        out["param"] = {"error": str(exc)}
    try:
        inst_dec = orch.evaluate_instance_adapt(
            correlation_id=correlation_id,
            stage=stage_name,
            adaptation_tier=tier,
            retries_this_stage=retries,
            plateau_active=bool(ctx.get("plateau_active", False)),
            phoenix_eligible=bool(ctx.get("phoenix_eligible", True)),
            learning_health=learning_health,
            stall_reason=str(ctx.get("failure_key", "") or ""),
            constitution_violations=viol,
            apply=True,
        )
        out["instance"] = inst_dec.to_dict()
        if (
            inst_dec.applied
            and inst_dec.apply_payload.get("refresh_handler_cfg")
            and registry is not None
            and hasattr(registry, "sync_curriculum_cfg")
        ):
            try:
                registry.sync_curriculum_cfg(cfg)
                out["instance_cfg_refreshed"] = True
            except Exception:
                out["instance_cfg_refreshed"] = False
    except Exception as exc:
        out["instance"] = {"error": str(exc)}
    return out


def merge_instance_spawn_flags(
    *,
    plan_spawn_plateau: bool,
    plan_spawn_phoenix: bool,
    phase2_extra: dict[str, Any] | None,
) -> tuple[bool, bool]:
    """OR plan flags with gated Phase 2 instance payload (in-process only)."""
    spawn_plateau = bool(plan_spawn_plateau)
    spawn_phoenix = bool(plan_spawn_phoenix)
    p2 = phase2_extra or {}
    inst_raw = p2.get("instance")
    inst: dict[str, Any] = inst_raw if isinstance(inst_raw, dict) else {}
    apply_payload = inst.get("apply_payload")
    if inst.get("applied") and isinstance(apply_payload, dict):
        spawn_plateau = spawn_plateau or bool(apply_payload.get("spawn_plateau"))
        spawn_phoenix = spawn_phoenix or bool(apply_payload.get("spawn_phoenix_reset"))
    return spawn_plateau, spawn_phoenix


__all__ = [
    "bind_orchestrator_twin",
    "cfg_with_wall_thresholds",
    "merge_instance_spawn_flags",
    "phase2_recovery_closed_loop",
    "phase2_wall_closed_loop",
]
