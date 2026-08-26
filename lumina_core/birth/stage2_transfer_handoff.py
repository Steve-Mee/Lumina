"""Stage-2 → Stage-3 transfer handoff — cut weak range prior before mixed regimes.

Mirror Stage-1→2 umbilical cut without floor theater:
  - purge/curate buffer of toxic Stage-2 trajectories
  - reinit action (+ value) head; keep feature encoder
  - telemetry for operator SSOT

Live forensics 2026-08: Stage-2 passed on rolling 35% with lifetime 26% WR;
Stage-3 then over-traded to ~22% WR. Handoff detox is capital-preservation honesty.
"""

from __future__ import annotations

from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage2_transfer")


def execute_stage2_transfer_handoff(
    *,
    host: Any,
    cfg: Any,
    stage_trades: int = 0,
    stage_wins: int = 0,
    rolling_winrate: float | None = None,
) -> dict[str, Any]:
    """Hard Stage-2 → Stage-3 umbilical cut. Floors unchanged."""
    enabled = bool(getattr(cfg, "stage2_transfer_handoff_enabled", True))
    result: dict[str, Any] = {
        "ok": False,
        "enabled": enabled,
        "buffer_purge": {},
        "action_head_reinit": {},
        "stage2_wr": 0.0,
        "stage2_rolling_wr": None,
        "reason": "",
    }
    if not enabled:
        result["reason"] = "disabled"
        return result

    trades = max(0, int(stage_trades))
    wins = max(0, int(stage_wins))
    wr = float(wins) / float(max(1, trades)) if trades > 0 else 0.0
    result["stage2_wr"] = round(wr, 4)
    if rolling_winrate is not None:
        try:
            result["stage2_rolling_wr"] = round(float(rolling_winrate), 4)
        except (TypeError, ValueError):
            result["stage2_rolling_wr"] = None

    # Always purge when lifetime was weak vs rolling (handoff risk), or when configured.
    purge_on = bool(getattr(cfg, "stage2_transfer_purge_buffer", True))
    if purge_on:
        from lumina_core.birth.stage1_foundation import purge_stage1_buffer

        buf = getattr(host, "buffer", None)
        keep_pct = float(getattr(cfg, "stage2_transfer_keep_buffer_top_pct", 0.10) or 0.10)
        # Weak lifetime: keep less of the buffer (more detox).
        if wr + 1e-12 < 0.30:
            keep_pct = min(keep_pct, 0.05)
        result["buffer_purge"] = purge_stage1_buffer(
            buf,
            keep_top_pct=keep_pct,
            max_keep=int(getattr(cfg, "stage2_transfer_max_buffer_keep", 500) or 500),
        )
    else:
        result["buffer_purge"] = {"mode": "skipped", "kept": -1, "removed": 0}

    reinit_on = bool(getattr(cfg, "stage2_transfer_reinit_action_head", True))
    # Reinit when lifetime below floor-equiv (weak handoff) or always if configured.
    force_reinit = wr + 1e-12 < float(
        getattr(cfg, "stage2_transfer_reinit_below_wr", 0.32) or 0.32
    )
    if reinit_on or force_reinit:
        from lumina_core.birth.stage2_policy_bootstrap import reinit_policy_action_head

        model = getattr(host, "current_policy", None)
        if model is None:
            eng = getattr(host, "runtime", None) or getattr(host, "engine", None)
            model = getattr(eng, "rl_policy_model", None) if eng is not None else None
        if model is None and hasattr(host, "ppo_trainer"):
            resolve = getattr(host.ppo_trainer, "_resolve_active_model", None)
            if callable(resolve):
                try:
                    model = resolve()
                except Exception:
                    model = None
        result["action_head_reinit"] = reinit_policy_action_head(
            model, reinit_value_net=True
        )
        if model is not None:
            host.current_policy = model
            try:
                eng = getattr(host, "runtime", None) or getattr(host, "engine", None)
                if eng is not None and hasattr(eng, "set_rl_policy"):
                    eng.set_rl_policy(model)
            except Exception:
                pass
    else:
        result["action_head_reinit"] = {"ok": False, "reason": "disabled"}

    reinit_ok = bool((result.get("action_head_reinit") or {}).get("ok"))
    purge_mode = str((result.get("buffer_purge") or {}).get("mode") or "")
    purge_ok = purge_mode in {
        "full_clear",
        "list_rewrite",
        "clear_add",
        "filter_min_reward",
        "top_quartile",
        "skipped",
    } or purge_mode.startswith("top_pct_")
    result["ok"] = (reinit_ok if (reinit_on or force_reinit) else True) and (
        purge_ok if purge_on else True
    )
    result["reason"] = "handoff_complete" if result["ok"] else "handoff_partial"
    try:
        host._stage2_transfer_handoff = dict(result)
    except Exception:
        pass
    logger.info(
        "birth.stage2.transfer_handoff ok=%s wr=%.3f roll=%s purge=%s reinit=%s",
        result["ok"],
        wr,
        result.get("stage2_rolling_wr"),
        purge_mode,
        reinit_ok,
    )
    return result


__all__ = ["execute_stage2_transfer_handoff"]
