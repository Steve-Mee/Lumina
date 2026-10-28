"""Stage-1 foundation SSOT — breathe without poisoning the nursery.

Doctrine (ADR-0046, immutable):
  - Stage-1 **pass** is process-R: median_loss_r ≤ 1.5 after the volume gate,
    plus constitution 0, entropy alive, settlement, net RR. WR is HUD-only.
  - Stage-1 **learning** may still pressure WR toward a foundation bar so the
    organism grows — without raising the pass floor and without treating a
    plant-R fail as an entropy problem.
  - Process-R fail after volume-gate is plant-halt (HOLD), never explore_reduce.
  - Stage-1 **→ Stage-2 handoff** is fail-closed: cut toxic action prior + purge
    contaminated buffer. Eyes (encoder) may stay; hands (action head) reset.

Elon: survival is not permission to ship a broken control stick into stage 2.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage1_foundation")

# Learning target (NOT pass floor). Pass remains birth_survival_wr_floor (~0.20).
DEFAULT_FOUNDATION_TARGET_WR = 0.30
# Below this after volume gate → hard anti-thrash meta (still not pass-blocking).
DEFAULT_ANTI_THRASH_WR = 0.25


@dataclass(frozen=True, slots=True)
class Stage1FoundationSnapshot:
    trades: int
    wins: int
    winrate: float
    survival_wr_floor: float
    foundation_target_wr: float
    learning_gap: float  # max(0, target − wr) — reward/meta pressure
    survival_ok: bool
    foundation_pressure: bool
    anti_thrash: bool
    edge_vs_random: float | None
    volume_gate: bool

    def as_progress_fields(self) -> dict[str, Any]:
        return {
            "stage1_foundation_target_wr": round(float(self.foundation_target_wr), 4),
            "stage1_foundation_winrate": round(float(self.winrate), 4),
            "stage1_foundation_learning_gap": round(float(self.learning_gap), 4),
            "stage1_foundation_pressure": bool(self.foundation_pressure),
            "stage1_anti_thrash": bool(self.anti_thrash),
            "stage1_survival_ok": bool(self.survival_ok),
            "stage1_edge_vs_random": (
                round(float(self.edge_vs_random), 4)
                if self.edge_vs_random is not None
                else None
            ),
        }


def compute_stage1_foundation(
    *,
    stage_trades: int,
    stage_wins: int,
    required: int = 200,
    survival_wr_floor: float = 0.20,
    foundation_target_wr: float = DEFAULT_FOUNDATION_TARGET_WR,
    anti_thrash_wr: float = DEFAULT_ANTI_THRASH_WR,
    edge_vs_random: float | None = None,
    rolling_winrate: float | None = None,
) -> Stage1FoundationSnapshot:
    """Snapshot of Stage-1 survival vs foundation learning pressure."""
    trades = max(0, int(stage_trades))
    wins = max(0, int(stage_wins))
    lifetime = float(wins) / float(max(1, trades)) if trades > 0 else 0.0
    wr = max(lifetime, float(rolling_winrate)) if rolling_winrate is not None else lifetime
    surv = float(survival_wr_floor)
    target = float(foundation_target_wr)
    # Target must sit above survival (foundation aspires higher than breathe).
    target = max(surv + 0.02, min(0.45, target))
    thrash = float(anti_thrash_wr)
    thrash = max(surv, min(target, thrash))
    gap = max(0.0, target - wr)
    past_gate = trades >= max(1, int(required))
    return Stage1FoundationSnapshot(
        trades=trades,
        wins=wins,
        winrate=wr,
        survival_wr_floor=surv,
        foundation_target_wr=target,
        learning_gap=gap,
        survival_ok=wr + 1e-12 >= surv,
        foundation_pressure=bool(past_gate and gap > 1e-12),
        anti_thrash=bool(past_gate and wr + 1e-12 < thrash),
        edge_vs_random=(float(edge_vs_random) if edge_vs_random is not None else None),
        volume_gate=bool(past_gate),
    )


def stage1_foundation_learning_gap(
    *,
    stage_trades: int,
    stage_wins: int,
    required: int,
    cfg: Any = None,
    rolling_winrate: float | None = None,
    edge_vs_random: float | None = None,
) -> float:
    """Reward-seed gap: max(0, foundation_target − live WR) after volume gate.

    Converted to expectancy-scale by returning gap on WR scale (0–0.3 typical).
    Reward shaper already scales expectancy_gap; we map WR gap → exp-like units
    by treating gap_wr as the same order as (floor − exp) ≈ gap_wr.
    """
    if not bool(getattr(cfg, "stage1_foundation_pressure_enabled", True) if cfg else True):
        return 0.0
    surv = float(getattr(cfg, "birth_survival_wr_floor", 0.20) if cfg else 0.20)
    target = float(
        getattr(cfg, "stage1_foundation_target_wr", DEFAULT_FOUNDATION_TARGET_WR)
        if cfg
        else DEFAULT_FOUNDATION_TARGET_WR
    )
    thrash = float(
        getattr(cfg, "stage1_anti_thrash_wr", DEFAULT_ANTI_THRASH_WR)
        if cfg
        else DEFAULT_ANTI_THRASH_WR
    )
    snap = compute_stage1_foundation(
        stage_trades=stage_trades,
        stage_wins=stage_wins,
        required=required,
        survival_wr_floor=surv,
        foundation_target_wr=target,
        anti_thrash_wr=thrash,
        edge_vs_random=edge_vs_random,
        rolling_winrate=rolling_winrate,
    )
    if not snap.foundation_pressure:
        return 0.0
    # Map WR gap to reward gap units (same magnitude as Stage-2 exp gap).
    return float(min(0.30, snap.learning_gap))


def stage1_should_anti_thrash(snap: Stage1FoundationSnapshot | None, *, cfg: Any = None) -> bool:
    if snap is None:
        return False
    if not bool(getattr(cfg, "stage1_foundation_pressure_enabled", True) if cfg else True):
        return False
    return bool(snap.anti_thrash)


def purge_stage1_buffer(
    buffer: Any,
    *,
    keep_top_pct: float = 0.0,
    max_keep: int = 0,
) -> dict[str, Any]:
    """Remove Stage-1 trajectory poison from the shared PPO buffer.

    Default keep_top_pct=0 → full clear (cleanest handoff). Non-zero keeps only
    the highest-reward fraction (still decontamination, not theater).
    """
    out: dict[str, Any] = {"removed": 0, "kept": 0, "mode": "noop"}
    if buffer is None:
        out["mode"] = "no_buffer"
        return out
    try:
        before = len(buffer) if hasattr(buffer, "__len__") else 0
    except Exception:
        before = 0
    keep_pct = max(0.0, min(0.50, float(keep_top_pct)))
    try:
        # Default: full clear — cleanest umbilical cut.
        if keep_pct <= 1e-12:
            if hasattr(buffer, "clear"):
                buffer.clear()
                out["mode"] = "full_clear"
                out["removed"] = int(before)
                out["kept"] = 0
                return out
            out["mode"] = "unsupported_no_clear"
            return out
        # Optional: keep only top reward fraction (still decontamination).
        from lumina_core.birth.stage2_policy_bootstrap import curate_buffer_for_stage2_bootstrap

        cap = max(1, int(before * keep_pct)) if max_keep <= 0 else max(1, int(max_keep))
        out = curate_buffer_for_stage2_bootstrap(buffer, min_reward=0.0, max_keep=cap)
        out["mode"] = f"top_pct_{keep_pct:.2f}"
        return out
    except Exception as exc:
        logger.warning("birth.stage1.buffer_purge_failed: %s", exc)
        out["mode"] = f"error:{type(exc).__name__}"
        return out


def execute_stage1_transfer_handoff(
    *,
    host: Any,
    cfg: Any,
    stage_trades: int = 0,
    stage_wins: int = 0,
    edge_vs_random: float | None = None,
) -> dict[str, Any]:
    """Hard Stage-1 → Stage-2 umbilical cut.

    1) Purge/curate buffer (no Stage-1 anti-edge flood into Stage-2 PPO).
    2) Reinit action (+ value) head — keep feature encoder.
    3) Telemetry for progress/receipt.

    Does **not** change Stage-1 pass floors. Fail-soft on missing model/buffer
    but records honesty flags so operators see incomplete detox.
    """
    enabled = bool(getattr(cfg, "stage1_transfer_handoff_enabled", True))
    result: dict[str, Any] = {
        "ok": False,
        "enabled": enabled,
        "buffer_purge": {},
        "action_head_reinit": {},
        "stage1_wr": 0.0,
        "reason": "",
    }
    if not enabled:
        result["reason"] = "disabled"
        return result

    trades = max(0, int(stage_trades))
    wins = max(0, int(stage_wins))
    wr = float(wins) / float(max(1, trades)) if trades > 0 else 0.0
    result["stage1_wr"] = round(wr, 4)
    result["edge_vs_random"] = (
        round(float(edge_vs_random), 4) if edge_vs_random is not None else None
    )

    purge_on = bool(getattr(cfg, "stage1_transfer_purge_buffer", True))
    keep_pct = float(getattr(cfg, "stage1_transfer_keep_buffer_top_pct", 0.0) or 0.0)
    if purge_on:
        buf = getattr(host, "buffer", None)
        result["buffer_purge"] = purge_stage1_buffer(
            buf,
            keep_top_pct=keep_pct,
            max_keep=int(getattr(cfg, "stage1_transfer_max_buffer_keep", 0) or 0),
        )
    else:
        result["buffer_purge"] = {"mode": "skipped", "kept": -1, "removed": 0}

    reinit_on = bool(getattr(cfg, "stage1_transfer_reinit_action_head", True))
    if reinit_on:
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
    # Fail-closed honesty: handoff ok only if reinit succeeded when required.
    result["ok"] = (reinit_ok if reinit_on else True) and (purge_ok if purge_on else True)
    result["reason"] = "handoff_complete" if result["ok"] else "handoff_partial"
    # Host flags so Stage-2 bootstrap can see prior detox.
    try:
        host._stage1_transfer_handoff = dict(result)
        host._stage1_action_head_reinit = reinit_ok
    except Exception:
        pass
    logger.info(
        "birth.stage1.transfer_handoff ok=%s wr=%.3f purge=%s reinit=%s",
        result["ok"],
        wr,
        purge_mode,
        reinit_ok,
    )
    return result


def stage1_foundation_meta_fields(
    snap: Stage1FoundationSnapshot,
    *,
    exploration_steps: int = 2000,
    strong_recovery_explore_fraction: float = 0.35,
    median_loss_r: float | None = None,
) -> dict[str, Any] | None:
    """Meta plan when Stage-1 is thrashing under foundation target.

    Process-R fail after the volume gate is HOLD (plant-fix), never explore_reduce.
    WR-target pressure may explore_reduce only while median_loss_r ≤ 1.5.
    Never explore_boost while anti_thrash — quality first, still no floor move.
    """
    from lumina_core.birth.foundation_metrics import process_r_ok

    if bool(snap.volume_gate) and not process_r_ok(median_loss_r):
        return {
            "primary": "hold",
            "secondary": (),
            "explore_steps": max(
                200, int(float(exploration_steps) * float(strong_recovery_explore_fraction))
            ),
            "escalation_delta": 0,
            "mine": False,
            "rationale": "stage1_process_r_plant",
        }
    if not snap.anti_thrash and not snap.foundation_pressure:
        return None
    explore_floor = max(
        200, int(float(exploration_steps) * float(strong_recovery_explore_fraction))
    )
    if snap.anti_thrash:
        return {
            "primary": "explore_reduce",
            "secondary": ("reward_shaping_tweak", "pattern_inject"),
            "explore_steps": explore_floor,
            "escalation_delta": 1,
            "mine": True,
            "rationale": "stage1_foundation_anti_thrash",
        }
    # Mild pressure: prefer mine + modest reduce when gap open but not thrash-dead.
    return {
        "primary": "explore_reduce",
        "secondary": ("pattern_inject", "reward_shaping_tweak"),
        "explore_steps": max(explore_floor, int(exploration_steps)),
        "escalation_delta": 1,
        "mine": True,
        "rationale": "stage1_foundation_pressure",
    }


__all__ = [
    "DEFAULT_ANTI_THRASH_WR",
    "DEFAULT_FOUNDATION_TARGET_WR",
    "Stage1FoundationSnapshot",
    "compute_stage1_foundation",
    "execute_stage1_transfer_handoff",
    "purge_stage1_buffer",
    "stage1_foundation_learning_gap",
    "stage1_foundation_meta_fields",
    "stage1_should_anti_thrash",
]
