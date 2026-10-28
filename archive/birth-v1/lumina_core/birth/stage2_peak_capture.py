"""Stage-2 peak capture — freeze truth peaks, block recovery theater from burning them.

Live forensics 2026-08: lifetime exp peaked ~−0.153 at 150 trades (before volume
gate 300), then diluted; swarm probe ~22% WR destroyed the late window. This module
is the SSOT for:

- peak WR / expectancy snapshots (truthful, no floor move)
- near-miss lock (defer swarm when almost at −0.15 with volume+flat OK)
- collapse restore (reload best policy when rolling falls off the peak)
- swarm / phoenix gates (no thrash while near-miss or anti-edge with quality left)

Root-cause forensics 2026-08-12 (stuck −20% / never durable green):
1. Single lucky 50-trade chunk (38% WR) armed flash+finish; lifetime stayed ~30%.
2. flash/finish clamped hold to 35 bars while geometry needs ~120 → stop:target 3:1.
3. Every peak_restore was immediately followed by PPO on anti-edge trajectories
   (quality_rollouts_since_restore stuck at 0) — peak weights never re-evaluated.
4. OOS proxy 18% — hop was noise, not skill.

Honest fixes (floors unchanged): durable multi-window flash, geometry-respecting
hold under quality, PPO freeze after restore, quality-gated train.

Never lowers stage2_expectancy_floor (−0.15). Never fakes wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.stage2_peak")

# Near-miss band on WR−0.50 scale: floor −0.15, near = within 0.02 (≈33–35% WR).
DEFAULT_NEAR_MISS_DELTA = 0.02
# Collapse: restore when peak_wr − live_rolling ≥ this (truthful degradation).
DEFAULT_COLLAPSE_WR_DROP = 0.05
# Min trades before peak snapshot is trusted (chunk scale — flash green at 50).
# Live forensics 2026-08: 36% WR @ 50 was lost because min was 80.
DEFAULT_PEAK_MIN_TRADES = 50


@dataclass(slots=True)
class Stage2PeakState:
    """Mutable peak / near-miss / restore telemetry for one stage run."""

    peak_winrate: float = 0.0
    peak_expectancy: float = -1.0
    peak_at_trade: int = 0
    peak_policy_path: str = ""
    peak_flat: float = 0.0
    peak_edge_vs_random: float = 0.0
    near_miss_active: bool = False
    near_miss_count: int = 0
    restore_count: int = 0
    last_restore_at_trade: int = 0
    last_restore_reason: str = ""
    swarm_blocked_reason: str = ""
    phoenix_blocked_reason: str = ""
    quality_rollouts_since_restore: int = 0
    cumulative_closes_stop: int = 0
    cumulative_closes_target: int = 0
    cumulative_closes_flatten: int = 0
    cumulative_closes_time_stop: int = 0
    cumulative_closes_unknown: int = 0
    # PR-G: peak cleared exp floor before volume — arm graduation protect.
    peak_grad_armed: bool = False
    peak_grad_armed_at_trade: int = 0
    volume_rechallenge_done: bool = False
    volume_rechallenge_at_trade: int = 0
    finish_mode_active: bool = False
    consecutive_rolling_pass_windows: int = 0
    participation_force_exit_cum: int = 0
    # PR-L: first hop green (exp ≥ floor) captured at chunk scale before dilution.
    flash_green: bool = False
    flash_green_wr: float = 0.0
    flash_green_at_trade: int = 0
    # Durable green: ≥N consecutive green chunks (not a single life/roll print).
    # Hop-only flash must not arm thrash restore / finish hold clamps.
    flash_green_durable: bool = False
    consecutive_green_chunks: int = 0
    # Set True when restore loaded weights this cycle (PPO freeze gate).
    restored_this_cycle: bool = False
    # Flash-green quality lock: freeze PPO until durable rolling streak
    # AND occupancy in band. Envelope stays on (airframe). Same-cycle
    # arm+release is forbidden. C-band-only release at volume burned PID 19776.
    quality_lock_active: bool = False
    quality_lock_wr: float = 0.0
    quality_lock_at_trade: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)

    def as_progress_fields(self) -> dict[str, Any]:
        stop_t = int(self.cumulative_closes_stop)
        tgt_t = int(self.cumulative_closes_target)
        flat_t = int(self.cumulative_closes_flatten)
        time_t = int(self.cumulative_closes_time_stop)
        unk_t = int(self.cumulative_closes_unknown)
        from lumina_core.birth.starship_edgescore_core import settlement_progress_fields

        payload: dict[str, Any] = {
            "stage2_peak_winrate": round(float(self.peak_winrate), 4),
            "stage2_peak_expectancy": round(float(self.peak_expectancy), 4),
            "stage2_peak_at_trade": int(self.peak_at_trade),
            "stage2_peak_policy_path": str(self.peak_policy_path or ""),
            "stage2_peak_flat": round(float(self.peak_flat), 4),
            "stage2_peak_edge_vs_random": round(float(self.peak_edge_vs_random), 4),
            "stage2_near_miss_active": bool(self.near_miss_active),
            "stage2_near_miss_count": int(self.near_miss_count),
            "stage2_peak_restore_count": int(self.restore_count),
            "stage2_peak_last_restore_reason": str(self.last_restore_reason or ""),
            "stage2_swarm_blocked_reason": str(self.swarm_blocked_reason or ""),
            "stage2_phoenix_blocked_reason": str(self.phoenix_blocked_reason or ""),
            "stage2_quality_rollouts_since_restore": int(self.quality_rollouts_since_restore),
            "stage2_peak_grad_armed": bool(self.peak_grad_armed),
            "stage2_peak_grad_armed_at_trade": int(self.peak_grad_armed_at_trade),
            "stage2_volume_rechallenge_done": bool(self.volume_rechallenge_done),
            "stage2_finish_mode_active": bool(self.finish_mode_active),
            "stage2_finish_stable": bool(
                int(self.consecutive_rolling_pass_windows) >= 2
            ),
            "stage2_consecutive_rolling_pass_windows": int(
                self.consecutive_rolling_pass_windows
            ),
            "stage2_flash_green": bool(self.flash_green),
            "stage2_flash_green_wr": round(float(self.flash_green_wr), 4),
            "stage2_flash_green_at_trade": int(self.flash_green_at_trade),
            "stage2_flash_green_durable": bool(self.flash_green_durable),
            "stage2_consecutive_green_chunks": int(self.consecutive_green_chunks),
            "stage2_quality_lock_active": bool(self.quality_lock_active),
            "stage2_quality_lock_wr": round(float(self.quality_lock_wr), 4),
            "stage2_quality_lock_at_trade": int(self.quality_lock_at_trade),
            "stage_participation_force_exit_cum": int(self.participation_force_exit_cum),
            "stage_target_share_decisive": round(
                float(tgt_t) / float(max(1, stop_t + tgt_t)), 4
            ),
        }
        payload.update(
            settlement_progress_fields(
                closes_stop=stop_t,
                closes_target=tgt_t,
                closes_time_stop=time_t,
                closes_flatten=flat_t,
                closes_unknown=unk_t,
            )
        )
        return payload


def _cfg_float(cfg: Any, name: str, default: float) -> float:
    try:
        return float(getattr(cfg, name, default) if cfg is not None else default)
    except (TypeError, ValueError):
        return float(default)


def _cfg_int(cfg: Any, name: str, default: int) -> int:
    try:
        return int(getattr(cfg, name, default) if cfg is not None else default)
    except (TypeError, ValueError):
        return int(default)


def effective_stage2_winrate(
    *,
    stage_trades: int,
    stage_wins: int,
    rolling_winrate: float | None = None,
    chunk_winrate: float | None = None,
) -> float:
    """Best honest window: lifetime vs rolling vs last-chunk (flash green)."""
    lifetime = float(stage_wins) / float(max(1, stage_trades)) if stage_trades > 0 else 0.0
    wr = lifetime
    if rolling_winrate is not None:
        wr = max(wr, float(rolling_winrate))
    if chunk_winrate is not None:
        wr = max(wr, float(chunk_winrate))
    return wr


def stage2_expectancy_from_wr(wr: float) -> float:
    return float(wr) - 0.50


def is_near_miss_expectancy(
    *,
    expectancy: float,
    exp_floor: float = -0.15,
    near_delta: float = DEFAULT_NEAR_MISS_DELTA,
) -> bool:
    """True when below floor but within near_delta (e.g. −0.17..−0.15 exclusive of pass)."""
    floor = float(exp_floor)
    delta = max(0.005, float(near_delta))
    exp = float(expectancy)
    if exp + 1e-12 >= floor:
        return False  # at/above floor is pass territory, not near-miss
    return exp >= floor - delta - 1e-12


def update_stage2_peak(
    state: Stage2PeakState,
    *,
    stage_trades: int,
    stage_wins: int,
    range_flat_ratio: float,
    edge_vs_random: float | None = None,
    rolling_winrate: float | None = None,
    chunk_winrate: float | None = None,
    chunk_trades: int = 0,
    policy_path: str = "",
    cfg: Any = None,
) -> bool:
    """Update peak snapshot when live effective WR improves. Returns True if new peak.

    PR-L: min trades default 50 (chunk scale). Uses max(life, rolling, last_chunk)
    so first-hop 36% WR is not erased by dilution before peak_min=80.

    Durable green (2026-08-12): a single lucky chunk may save a hop snapshot, but
    finish/grad arming requires multi-window confirmation (floors unchanged).
    """
    min_tr = max(20, _cfg_int(cfg, "stage2_peak_min_trades", DEFAULT_PEAK_MIN_TRADES))
    # Flash path: honest chunk ≥40 with WR≥35% may capture even if lifetime trades
    # slightly below min_tr (still require chunk size).
    trades = max(0, int(stage_trades))
    flash_chunk = False
    try:
        from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

        floor = float(stage2_expectancy_floor(cfg)) if cfg is not None else -0.15
    except Exception:
        floor = float(getattr(cfg, "stage2_expectancy_floor", -0.15) or -0.15) if cfg else -0.15
    wr_floor = float(floor) + 0.50
    life_wr = (
        float(stage_wins) / float(max(1, trades)) if trades > 0 else 0.0
    )
    # Track consecutive green chunks (honest multi-window durability).
    if chunk_winrate is not None and int(chunk_trades) >= 40:
        if float(chunk_winrate) + 1e-12 >= wr_floor:
            state.consecutive_green_chunks = int(state.consecutive_green_chunks) + 1
        else:
            state.consecutive_green_chunks = 0
    if (
        chunk_winrate is not None
        and int(chunk_trades) >= 40
        and float(chunk_winrate) + 1e-12 >= wr_floor
        and 0.30 - 1e-12 <= float(range_flat_ratio) <= 0.70 + 1e-12
    ):
        flash_chunk = True
        min_tr = min(min_tr, max(40, int(chunk_trades)))
    if trades < min_tr and not flash_chunk:
        _refresh_flash_durable(
            state,
            life_wr=life_wr,
            rolling_winrate=rolling_winrate,
            wr_floor=wr_floor,
            cfg=cfg,
        )
        return False
    wr = effective_stage2_winrate(
        stage_trades=trades,
        stage_wins=int(stage_wins),
        rolling_winrate=rolling_winrate,
        chunk_winrate=chunk_winrate,
    )
    # If only flash chunk is green, prefer that window for peak (truthful hop).
    if flash_chunk and chunk_winrate is not None:
        wr = max(wr, float(chunk_winrate))
    exp = stage2_expectancy_from_wr(wr)
    improved = wr + 1e-12 > float(state.peak_winrate)
    if not improved:
        _refresh_flash_durable(
            state,
            life_wr=life_wr,
            rolling_winrate=rolling_winrate,
            wr_floor=wr_floor,
            cfg=cfg,
        )
        return False
    state.peak_winrate = float(wr)
    state.peak_expectancy = float(exp)
    state.peak_at_trade = int(trades)
    state.peak_flat = float(range_flat_ratio)
    if edge_vs_random is not None:
        state.peak_edge_vs_random = float(edge_vs_random)
    if policy_path:
        state.peak_policy_path = str(policy_path)
    # Hop telemetry: any green window. Finish mode only after durable confirm.
    if exp + 1e-12 >= float(floor):
        if not state.flash_green or float(wr) >= float(state.flash_green_wr):
            state.flash_green = True
            state.flash_green_wr = float(wr)
            state.flash_green_at_trade = int(trades)
            logger.info(
                "birth.stage2.flash_green wr=%.4f exp=%.4f at_trade=%s flat=%.3f "
                "consecutive_green_chunks=%s",
                wr,
                exp,
                trades,
                float(range_flat_ratio),
                int(state.consecutive_green_chunks),
            )
    _refresh_flash_durable(
        state,
        life_wr=life_wr,
        rolling_winrate=rolling_winrate,
        wr_floor=wr_floor,
        cfg=cfg,
    )
    if state.flash_green_durable:
        state.finish_mode_active = True
    state.history.append(
        {
            "trade": int(trades),
            "wr": round(wr, 4),
            "exp": round(exp, 4),
            "flat": round(float(range_flat_ratio), 4),
            "flash": bool(flash_chunk or state.flash_green),
            "durable": bool(state.flash_green_durable),
        }
    )
    if len(state.history) > 32:
        state.history = state.history[-32:]
    logger.info(
        "birth.stage2.peak_capture wr=%.4f exp=%.4f at_trade=%s flat=%.3f path=%s "
        "flash=%s durable=%s",
        wr,
        exp,
        trades,
        float(range_flat_ratio),
        Path(str(policy_path)).name if policy_path else "",
        bool(state.flash_green),
        bool(state.flash_green_durable),
    )
    return True


def _refresh_flash_durable(
    state: Stage2PeakState,
    *,
    life_wr: float,
    rolling_winrate: float | None,
    wr_floor: float,
    cfg: Any = None,
) -> None:
    """Mark flash durable when multi-window evidence clears the floor."""
    need_chunks = max(2, _cfg_int(cfg, "stage2_flash_durable_min_chunks", 2))
    multi_chunk = int(state.consecutive_green_chunks) >= need_chunks
    was = bool(state.flash_green_durable)
    # PID 33628: life_ok OR roll_ok latched durable on a single 38% hop, armed
    # peak_grad, then diluted. Multi-chunk only — floors unchanged.
    # Disarm leftover peak_grad even without a falling edge (resumed checkpoint
    # already had durable=false + peak_grad=true → 6 restore loops).
    state.flash_green_durable = bool(state.flash_green and multi_chunk)
    if (
        not state.flash_green_durable
        and state.peak_grad_armed
        and int(state.consecutive_rolling_pass_windows) < 2
    ):
        state.peak_grad_armed = False
        logger.info(
            "birth.stage2.peak_grad_disarmed durable_collapsed life=%.4f",
            float(life_wr),
        )
    if state.flash_green_durable and not was:
        state.finish_mode_active = True
        logger.info(
            "birth.stage2.flash_green_durable wr_life=%.4f roll=%s chunks=%s need=%s floor=%.2f",
            float(life_wr),
            None if rolling_winrate is None else round(float(rolling_winrate), 4),
            int(state.consecutive_green_chunks),
            need_chunks,
            float(wr_floor),
        )


def maybe_arm_peak_graduation(
    state: Stage2PeakState,
    *,
    stage_trades: int,
    range_flat_ratio: float,
    required: int,
    cfg: Any = None,
) -> bool:
    """Arm when peak cleared exp floor with flat OK before/around volume gate.

    Live forensics: peak 37.3% WR (exp −0.127) at 250 trades; volume needs 300.
    Floor unchanged — this only protects a truthful clear of altitude.

    2026-08-12: hop-only flash (single lucky chunk) must NOT arm graduation.
    Require durable multi-window green (or peak_grad would thrash restore forever).
    """
    if not bool(getattr(cfg, "stage2_peak_grad_enabled", True) if cfg is not None else True):
        return False
    if state.peak_grad_armed:
        return False
    try:
        from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

        floor = float(stage2_expectancy_floor(cfg)) if cfg is not None else -0.15
    except Exception:
        floor = float(getattr(cfg, "stage2_expectancy_floor", -0.15) or -0.15) if cfg else -0.15
    # Peak must clear floor on WR−0.50 scale (wr ≥ floor+0.50).
    wr_need = float(floor) + 0.50
    peak_wr = float(state.peak_winrate)
    flash_wr = float(state.flash_green_wr) if state.flash_green else 0.0
    best_wr = max(peak_wr, flash_wr)
    if best_wr + 1e-12 < wr_need:
        return False
    # Durable only — single hop is telemetry, not graduation altitude.
    if not bool(state.flash_green_durable):
        return False
    req = max(1, int(required))
    # PR-M: durable flash arms at multi-chunk scale, not only after 200 trades.
    flash_min = max(40, _cfg_int(cfg, "stage2_flash_green_min_trades", 50))
    late_min = max(
        flash_min,
        _cfg_int(cfg, "stage2_peak_grad_min_trades", 200),
    )
    late_min = min(late_min, req)
    at_peak = int(state.peak_at_trade or 0)
    at_flash = int(state.flash_green_at_trade or 0)
    at_live = int(stage_trades)
    if state.flash_green_durable or best_wr + 1e-12 >= wr_need:
        if max(at_peak, at_flash, at_live) < flash_min:
            return False
    else:
        if at_live < late_min and at_peak < late_min:
            return False
    flat = float(range_flat_ratio)
    if not (0.30 - 1e-12 <= flat <= 0.70 + 1e-12):
        # Allow arm on peak_flat if live flat briefly noisy.
        flat = float(state.peak_flat)
        if not (0.30 - 1e-12 <= flat <= 0.70 + 1e-12):
            return False
    state.peak_grad_armed = True
    state.peak_grad_armed_at_trade = int(
        state.flash_green_at_trade or state.peak_at_trade or stage_trades
    )
    state.finish_mode_active = True
    if state.flash_green and float(state.flash_green_wr) > float(state.peak_winrate):
        # Keep peak SSOT at least at flash green altitude.
        state.peak_winrate = float(state.flash_green_wr)
        state.peak_expectancy = stage2_expectancy_from_wr(state.peak_winrate)
    logger.info(
        "birth.stage2.peak_grad_armed peak_wr=%.4f peak_exp=%.4f at_trade=%s "
        "volume_gate=%s durable=%s (protect until volume re-challenge)",
        state.peak_winrate,
        state.peak_expectancy,
        state.peak_grad_armed_at_trade,
        req,
        bool(state.flash_green_durable),
    )
    return True


def _stage2_wr_floor(cfg: Any = None) -> float:
    try:
        from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

        return float(stage2_expectancy_floor(cfg)) + 0.50
    except Exception:
        return 0.35


def quality_lock_would_hop_fail(
    *,
    lock_wr: float,
    lifetime_wr: float | None,
    rolling_winrate: float | None,
    range_flat_ratio: float | None,
    wr_floor: float = 0.35,
) -> bool:
    """True when occupancy is in-band but the locked hop already missed.

    Rolling at/above the 35% floor is live exam green — not a failed hop.
    Stale peak 42% with life/roll ~30% (PID 40020) is a failed hop.
    """
    if lifetime_wr is None or range_flat_ratio is None:
        return False
    in_band = 0.30 - 1e-12 <= float(range_flat_ratio) <= 0.70 + 1e-12
    if not in_band:
        return False
    collapse = float(lock_wr) - float(lifetime_wr)
    if collapse + 1e-12 < 0.05:
        return False
    if rolling_winrate is not None and float(rolling_winrate) + 1e-12 >= float(
        wr_floor
    ):
        return False
    return True


def maybe_arm_quality_lock(
    state: Stage2PeakState,
    *,
    chunk_wr: float | None,
    chunk_exp: float | None = None,
    stage_trades: int,
    cfg: Any = None,
    rolling_winrate: float | None = None,
    lifetime_wr: float | None = None,
    range_flat_ratio: float | None = None,
) -> bool:
    """Lock a truthful flash-green (WR ≥ 36%, exp ≥ −0.14) so PPO cannot burn it.

    Arm from chunk, in-band peak, or rolling — not chunk-only. Live 13/08 PID
    19776: peak 44% @ 300 (rolling/effective) never locked until a 36% chunk at
    500; lock then released on C-band and PPO burned the peak. Floors unchanged.
    Graduation stays durable (life ≥ 30% + rolling streak). This only freezes
    training physics.

    PID 40020: after hop_failed, peak-source re-armed every rollout from a
    museum 42% @ 450 while live WR stayed ~30% → PPO skipped forever. Do not
    arm a lock that hop_failed_generalize would release on the next cycle.
    """
    if not bool(
        getattr(cfg, "stage2_quality_lock_enabled", True) if cfg is not None else True
    ):
        return False
    if state.quality_lock_active:
        return False
    wr_need = _cfg_float(cfg, "stage2_quality_lock_chunk_wr", 0.36)
    exp_need = _cfg_float(cfg, "stage2_quality_lock_exp_floor", -0.14)
    wr_floor = _stage2_wr_floor(cfg)

    candidates: list[tuple[float, float, str]] = []
    if chunk_wr is not None and float(chunk_wr) + 1e-12 >= wr_need:
        wr_c = float(chunk_wr)
        exp_c = float(chunk_exp) if chunk_exp is not None else (wr_c - 0.50)
        candidates.append((wr_c, exp_c, "chunk"))
    peak_wr = float(state.peak_winrate or 0.0)
    peak_flat = float(state.peak_flat or 0.0)
    peak_in_band = 0.30 - 1e-12 <= peak_flat <= 0.70 + 1e-12
    if (
        int(state.peak_at_trade or 0) > 0
        and peak_wr + 1e-12 >= wr_need
        and peak_in_band
    ):
        candidates.append((peak_wr, float(state.peak_expectancy), "peak"))
    if rolling_winrate is not None and float(rolling_winrate) + 1e-12 >= wr_need:
        wr_r = float(rolling_winrate)
        candidates.append((wr_r, wr_r - 0.50, "rolling"))

    for wr, exp, source in candidates:
        if float(exp) + 1e-12 < exp_need:
            continue
        if quality_lock_would_hop_fail(
            lock_wr=float(wr),
            lifetime_wr=lifetime_wr,
            rolling_winrate=rolling_winrate,
            range_flat_ratio=range_flat_ratio,
            wr_floor=wr_floor,
        ):
            logger.info(
                "birth.stage2.quality_lock skip source=%s wr=%.4f life=%s roll=%s "
                "flat=%s (would hop_fail; PPO stays on; floors unchanged)",
                source,
                float(wr),
                None if lifetime_wr is None else round(float(lifetime_wr), 4),
                None if rolling_winrate is None else round(float(rolling_winrate), 4),
                None if range_flat_ratio is None else round(float(range_flat_ratio), 4),
            )
            continue
        state.quality_lock_active = True
        state.quality_lock_wr = float(wr)
        state.quality_lock_at_trade = int(stage_trades)
        logger.info(
            "birth.stage2.quality_lock armed wr=%.4f exp=%.4f at_trade=%s source=%s "
            "(PPO freeze until durable rolling streak + occupancy in band; floors unchanged)",
            float(wr),
            float(exp),
            int(stage_trades),
            source,
        )
        return True
    return False


def maybe_release_quality_lock(
    state: Stage2PeakState,
    *,
    lifetime_wr: float,
    stage_trades: int,
    required: int,
    cfg: Any = None,
    rolling_winrate: float | None = None,
    consecutive_rolling_pass_windows: int = 0,
    range_flat_ratio: float | None = None,
) -> bool:
    """Release PPO freeze on durable exam green, or when a hop lock failed.

    Volume + lifetime C-band (30%) is **not** enough: live PID 19776 released
    at trade 500 with life ~31% / rolling 34% / flat 0.299, then PPO burned a
    44% peak. Fail-closed without rolling streak + occupancy in band.

    PID 33628: occupancy stayed in-band (~32%) but a 38% hop lock printed ~30%
    forever (PPO frozen, 6 restore loops). When occupancy airframe is holding
    the exam and the locked hop dropped ≥5pp, unfreeze so search can resume.
    Same-cycle arm+release stays forbidden. Floors unchanged.
    """
    if not state.quality_lock_active:
        return False
    trades = int(stage_trades)
    if trades <= int(state.quality_lock_at_trade):
        return False
    if trades < max(1, int(required)):
        return False
    wr_floor = _stage2_wr_floor(cfg)
    hop_failed = bool(
        quality_lock_would_hop_fail(
            lock_wr=float(state.quality_lock_wr or 0.0),
            lifetime_wr=float(lifetime_wr),
            rolling_winrate=rolling_winrate,
            range_flat_ratio=range_flat_ratio,
            wr_floor=wr_floor,
        )
        and int(consecutive_rolling_pass_windows) < 2
    )
    if hop_failed:
        state.quality_lock_active = False
        collapse = float(state.quality_lock_wr or 0.0) - float(lifetime_wr)
        logger.info(
            "birth.stage2.quality_lock released hop_failed_generalize "
            "lock_wr=%.4f life=%.4f collapse=%.3f flat=%.4f trades=%s "
            "(occupancy airframe holding; PPO may search; floors unchanged)",
            float(state.quality_lock_wr or 0.0),
            float(lifetime_wr),
            collapse,
            float(range_flat_ratio or 0.0),
            trades,
        )
        return True
    delta = _cfg_float(cfg, "stage2_pass_lifetime_delta", 0.05)
    life_min = wr_floor - max(0.0, min(0.15, delta))
    if float(lifetime_wr) + 1e-12 < life_min:
        return False
    # Durable rolling: 2 consecutive pass windows (finish protocol). A single
    # 35% print must not unfreeze PPO (flash then burn).
    if int(consecutive_rolling_pass_windows) < 2:
        return False
    if rolling_winrate is not None and float(rolling_winrate) + 1e-12 < wr_floor:
        return False
    if range_flat_ratio is None:
        return False
    flat = float(range_flat_ratio)
    if not (0.30 - 1e-12 <= flat <= 0.70 + 1e-12):
        return False
    state.quality_lock_active = False
    logger.info(
        "birth.stage2.quality_lock released lifetime_wr=%.4f rolling=%s "
        "streak=%s flat=%.4f trades=%s (durable exam green; floors unchanged)",
        float(lifetime_wr),
        None if rolling_winrate is None else round(float(rolling_winrate), 4),
        int(consecutive_rolling_pass_windows),
        flat,
        trades,
    )
    return True


def should_freeze_ppo_quality_lock(
    state: Stage2PeakState,
    *,
    cfg: Any = None,
) -> tuple[bool, str]:
    """Skip PPO while quality lock holds a flash-green peak."""
    if not bool(
        getattr(cfg, "stage2_quality_lock_enabled", True) if cfg is not None else True
    ):
        return False, ""
    if bool(state.quality_lock_active):
        return True, "quality_lock"
    return False, ""


def should_volume_rechallenge_peak(
    state: Stage2PeakState,
    *,
    stage_trades: int,
    required: int,
    cfg: Any = None,
) -> bool:
    """True once when volume first clears after peak_grad_armed or quality lock.

    Live forensics 2026-08-13: hop-only lock never armed peak_grad, so the 40%
    peak was never reloaded at the volume gate. Quality lock + peak path is
    enough — durable graduation still required separately. Floors unchanged.
    """
    if state.volume_rechallenge_done:
        return False
    lock_rechallenge = bool(state.quality_lock_active) and bool(
        str(state.peak_policy_path or "").strip()
    )
    if not (state.peak_grad_armed or lock_rechallenge):
        return False
    if int(stage_trades) < max(1, int(required)):
        return False
    return True


def mark_volume_rechallenge(state: Stage2PeakState, *, stage_trades: int) -> None:
    state.volume_rechallenge_done = True
    state.volume_rechallenge_at_trade = int(stage_trades)
    state.quality_rollouts_since_restore = 0
    logger.info(
        "birth.stage2.volume_rechallenge trades=%s peak_wr=%.4f path=%s",
        stage_trades,
        state.peak_winrate,
        Path(state.peak_policy_path).name if state.peak_policy_path else "",
    )


def update_finish_mode(
    state: Stage2PeakState,
    *,
    rolling_winrate: float | None,
    cfg: Any = None,
) -> None:
    """Near-miss / peak-grad finish: track consecutive rolling pass windows.

    Rolling streak is counted even outside finish-mode so lifetime-only durable
    can see two windows (PID 33628 deadlock: need streak to be durable to enter
    finish to count streak). Hop-only still does not activate finish protect.
    """
    try:
        from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

        floor = float(stage2_expectancy_floor(cfg)) if cfg is not None else -0.15
    except Exception:
        floor = -0.15
    wr_need = float(floor) + 0.50  # 0.35 at default floor
    if rolling_winrate is not None:
        if float(rolling_winrate) + 1e-12 >= wr_need:
            state.consecutive_rolling_pass_windows = (
                int(state.consecutive_rolling_pass_windows) + 1
            )
        else:
            state.consecutive_rolling_pass_windows = 0
    finish = bool(
        state.peak_grad_armed
        or state.near_miss_active
        or state.flash_green_durable
    )
    state.finish_mode_active = finish


def finish_mode_stable(state: Stage2PeakState) -> bool:
    """True when 2 consecutive rolling pass windows held (finish protocol)."""
    return int(state.consecutive_rolling_pass_windows) >= 2


def finish_mode_blocks_pattern_inject(state: Stage2PeakState) -> bool:
    """Block inject flood only while durable green is currently held.

    Live forensics 2026-08-12: hop-only flash_green blocked oracle inject for
    800+ trades while PPO freeze was stuck → zero learning, WR stuck ~29%.
    Hop telemetry must NOT kill truthful oracle distill recovery.

    Live 2026-08-13 PID 19776: peak_grad_armed stayed True after
    flash_green_durable dropped → inject skipped while PPO burned 44% → 31%.
    peak_grad / finish_mode / near_miss alone must not freeze the teacher.

    Quality lock: allow oracle distill of peak trajectories — freeze PPO,
    do not freeze the teacher.
    """
    if bool(getattr(state, "quality_lock_active", False)):
        return False
    return bool(state.flash_green_durable) or finish_mode_stable(state)


def flash_green_protect_active(state: Stage2PeakState) -> bool:
    """True when durable green / grad / finish — wall/swarm protect intensity.

    Hop-only flash does not clamp geometry hold and does not block inject.
    """
    return bool(
        state.flash_green_durable
        or state.peak_grad_armed
        or state.finish_mode_active
    )


def evaluate_near_miss(
    state: Stage2PeakState,
    *,
    stage_trades: int,
    stage_wins: int,
    required: int,
    range_flat_ratio: float,
    rolling_winrate: float | None = None,
    cfg: Any = None,
) -> bool:
    """Set near_miss_active when volume+flat OK and exp within near-miss of floor."""
    if stage_trades < max(1, int(required)):
        state.near_miss_active = False
        return False
    flat = float(range_flat_ratio)
    if not (0.30 - 1e-12 <= flat <= 0.70 + 1e-12):
        state.near_miss_active = False
        return False
    wr = effective_stage2_winrate(
        stage_trades=stage_trades,
        stage_wins=stage_wins,
        rolling_winrate=rolling_winrate,
    )
    exp = stage2_expectancy_from_wr(wr)
    try:
        from lumina_core.birth.starship_edgescore_stage2 import stage2_expectancy_floor

        floor = float(stage2_expectancy_floor(cfg)) if cfg is not None else -0.15
    except Exception:
        floor = float(getattr(cfg, "stage2_expectancy_floor", -0.15) or -0.15) if cfg else -0.15
    near_delta = _cfg_float(cfg, "stage2_near_miss_exp_delta", DEFAULT_NEAR_MISS_DELTA)
    active = is_near_miss_expectancy(expectancy=exp, exp_floor=floor, near_delta=near_delta)
    if active:
        state.near_miss_active = True
        state.near_miss_count += 1
    else:
        state.near_miss_active = False
    return active


def should_defer_swarm_for_exit_forensics(
    state: Stage2PeakState,
    *,
    cfg: Any = None,
) -> tuple[bool, str]:
    """Block swarm while stop-magnet dominates (exit skill not ready).

    Live forensics: stop:target ~4:1 → swarm only burns peak. Floor unchanged.
    """
    if bool(getattr(cfg, "stage2_exit_forensics_block_swarm", True) is False):
        return False, ""
    stop_n = int(state.cumulative_closes_stop)
    tgt_n = int(state.cumulative_closes_target)
    decisive = stop_n + tgt_n
    min_dec = max(20, _cfg_int(cfg, "stage2_exit_forensics_min_decisive", 40))
    if decisive < min_dec:
        return False, ""
    ratio_thr = _cfg_float(cfg, "stage2_exit_forensics_stop_target_max", 2.5)
    ratio = float(stop_n) / float(max(1, tgt_n))
    if ratio + 1e-12 > ratio_thr:
        return True, f"exit_stop_magnet_{ratio:.2f}"
    share_thr = _cfg_float(cfg, "stage2_exit_forensics_target_share_min", 0.30)
    share = float(tgt_n) / float(max(1, decisive))
    if share + 1e-12 < share_thr:
        return True, f"exit_target_share_{share:.2f}"
    return False, ""


def should_defer_swarm_for_peak(
    state: Stage2PeakState,
    *,
    edge_vs_random: float | None,
    quality_step: int,
    max_quality_steps: int,
    best_winrate: float,
    cfg: Any = None,
) -> tuple[bool, str]:
    """Extra swarm defer beyond flat/expectancy: near-miss + anti-edge + peak protect."""
    if bool(getattr(cfg, "stage2_peak_capture_enabled", True) is False):
        return False, ""
    # Exit forensics first — never swarm a stop-magnet.
    exit_block, exit_reason = should_defer_swarm_for_exit_forensics(state, cfg=cfg)
    if exit_block:
        return True, exit_reason
    if bool(state.quality_lock_active):
        return True, "quality_lock"
    # Durable flash / peak graduation: never swarm until volume re-challenge quality done.
    if state.flash_green_durable and not state.volume_rechallenge_done:
        return True, "flash_green_durable"
    if state.peak_grad_armed and not state.volume_rechallenge_done:
        return True, "peak_grad_armed"
    if state.peak_grad_armed and state.quality_rollouts_since_restore < 4:
        return True, "peak_grad_quality"
    # Near-miss / finish / durable flash: never swarm theater — only quality / restore.
    if (
        state.near_miss_active
        or state.finish_mode_active
        or state.flash_green_durable
    ):
        return True, "near_miss"
    # Anti-edge: never swarm until quality budget exhausted (stronger than before).
    max_q = max(1, min(12, int(max_quality_steps)))
    # Mid-30s peak protect (live: peak 30% never armed 0.33 gate).
    peak_protect = _cfg_float(cfg, "stage2_swarm_block_if_peak_wr_above", 0.28)
    if edge_vs_random is not None and float(edge_vs_random) < -1e-12:
        if int(quality_step) < max_q:
            return True, "anti_edge_quality"
        # Even after quality steps: protect any peak at/above protect threshold.
        if float(state.peak_winrate) + 1e-12 >= peak_protect:
            return True, "anti_edge_protect_peak"
    # Peak was useful — block swarm thrash while quality still has room.
    if float(state.peak_winrate) + 1e-12 >= peak_protect and float(best_winrate) + 1e-12 >= 0.26:
        if int(quality_step) < max_q + 2:  # short extra defer after ladder
            return True, "protect_peak_wr"
    return False, ""


def should_restore_peak_policy(
    state: Stage2PeakState,
    *,
    stage_trades: int,
    stage_wins: int,
    rolling_winrate: float | None,
    range_flat_ratio: float,
    cfg: Any = None,
    required: int | None = None,
    chunk_winrate: float | None = None,
    chunk_trades: int = 0,
) -> tuple[bool, str]:
    """True when live skill collapsed vs peak while occupancy still OK.

    Hop-only flash (not durable) must not thrash restore every 50 trades — that
    path saved a lucky chunk as peak then restored forever while PPO destroyed it.
    """
    if not bool(getattr(cfg, "stage2_peak_restore_enabled", True) if cfg is not None else True):
        return False, ""
    if not state.peak_policy_path or state.peak_winrate <= 0:
        return False, ""
    # Hop-only: save peak weights for later, but do not thrash restore/PPO cycle.
    hop_only = bool(state.flash_green) and not bool(state.flash_green_durable)
    lock_on = bool(getattr(state, "quality_lock_active", False))
    flat_now = float(range_flat_ratio)
    in_exam_band = 0.30 - 1e-12 <= flat_now <= 0.70 + 1e-12
    if hop_only and not state.peak_grad_armed:
        if lock_on and in_exam_band:
            return False, "hop_only_lock_in_band_no_thrash"
        if not lock_on:
            return False, "hop_only_no_restore_thrash"
    # PR-G/M: durable flash / graduation → shorter gap + tighter collapse.
    armed = bool(state.peak_grad_armed or state.flash_green_durable)
    min_gap_default = 40 if armed else 50
    cooldown_default = 50 if armed else 80
    min_gap_trades = max(
        25,
        _cfg_int(
            cfg,
            "stage2_peak_restore_min_trades_since_peak",
            min_gap_default,
        ),
    )
    if armed:
        min_gap_trades = min(min_gap_trades, 50)
    ref_trade = int(state.peak_at_trade or state.flash_green_at_trade or 0)
    if int(stage_trades) - ref_trade < min_gap_trades:
        return False, ""
    cooldown = max(
        30,
        _cfg_int(cfg, "stage2_peak_restore_cooldown_trades", cooldown_default),
    )
    if armed:
        # Allow pure eval after restore (PPO freeze window needs headroom).
        cooldown = max(cooldown, 50)
        cooldown = min(cooldown, 100)
    if state.last_restore_at_trade > 0 and (
        int(stage_trades) - int(state.last_restore_at_trade) < cooldown
    ):
        return False, ""
    # Never restore again until freeze window completes (rollouts OR trades).
    freeze_n = max(1, _cfg_int(cfg, "stage2_ppo_freeze_rollouts_after_restore", 3))
    freeze_trades = max(
        40, _cfg_int(cfg, "stage2_ppo_freeze_trades_after_restore", 120)
    )
    if state.restore_count > 0 and state.last_restore_at_trade > 0:
        q_pending = int(state.quality_rollouts_since_restore) < freeze_n
        t_pending = (
            int(stage_trades) - int(state.last_restore_at_trade)
        ) < freeze_trades
        if q_pending and t_pending:
            return False, "ppo_freeze_eval_pending"
    flat = float(range_flat_ratio)
    if not (0.25 <= flat <= 0.75):  # soft band: still trying occupancy
        if lock_on:
            return True, f"lock_flat_out_{flat:.3f}"
        return False, "flat_out"
    live = effective_stage2_winrate(
        stage_trades=stage_trades,
        stage_wins=stage_wins,
        rolling_winrate=rolling_winrate,
    )
    peak_ref = max(float(state.peak_winrate), float(state.flash_green_wr or 0.0))
    drop = peak_ref - live
    thr = _cfg_float(cfg, "stage2_peak_collapse_wr_drop", DEFAULT_COLLAPSE_WR_DROP)
    if armed:
        # Durable collapse: 5pp (was 3pp — over-restored noise peaks).
        thr = min(thr, _cfg_float(cfg, "stage2_peak_grad_collapse_wr_drop", 0.05))
        thr = max(thr, 0.04)
    if drop + 1e-12 >= thr:
        tag = "flash_collapse" if state.flash_green_durable else (
            "grad_collapse" if state.peak_grad_armed else "collapse_drop"
        )
        return True, f"{tag}_{drop:.3f}"
    # After volume, durable flash + rolling still under 0.34 → restore.
    req = int(required) if required is not None else 0
    if (
        state.flash_green_durable
        and req > 0
        and int(stage_trades) >= req
        and rolling_winrate is not None
        and float(rolling_winrate) + 1e-12 < 0.34
    ):
        return True, f"flash_post_volume_roll_{float(rolling_winrate):.3f}"
    # Durable flash + next chunk toxic (<30%) → restore at chunk boundary.
    if (
        state.flash_green_durable
        and int(chunk_trades) >= 40
        and chunk_winrate is not None
        and float(chunk_winrate) + 1e-12 < 0.30
    ):
        return True, f"flash_toxic_chunk_{float(chunk_winrate):.3f}"
    return False, ""


def should_block_phoenix_for_peak(
    state: Stage2PeakState,
    *,
    cfg: Any = None,
) -> tuple[bool, str]:
    """Block phoenix expand until restore attempted after a real peak."""
    if not bool(getattr(cfg, "stage2_peak_block_phoenix_enabled", True) if cfg is not None else True):
        return False, ""
    if bool(state.quality_lock_active):
        return True, "quality_lock"
    if (
        state.peak_grad_armed
        or state.finish_mode_active
        or state.near_miss_active
        or state.flash_green_durable
    ):
        return True, "peak_grad_or_finish"
    # Exit magnet: never phoenix-reinit while stop-heavy.
    exit_block, exit_reason = should_defer_swarm_for_exit_forensics(state, cfg=cfg)
    if exit_block:
        return True, exit_reason
    # Mid-30s peaks count (live peak 30% was below old 0.32 gate).
    peak_floor = _cfg_float(cfg, "stage2_swarm_block_if_peak_wr_above", 0.28)
    if state.peak_winrate + 1e-12 < peak_floor:
        return False, ""
    min_restores = max(0, _cfg_int(cfg, "stage2_peak_phoenix_min_restores", 1))
    min_quality_rollouts = max(0, _cfg_int(cfg, "stage2_peak_phoenix_min_quality_rollouts", 4))
    if state.restore_count < min_restores:
        return True, "peak_restore_not_tried"
    if state.quality_rollouts_since_restore < min_quality_rollouts and state.restore_count > 0:
        return True, "peak_quality_rollouts_pending"
    return False, ""


def record_restore(state: Stage2PeakState, *, stage_trades: int, reason: str) -> None:
    state.restore_count += 1
    state.last_restore_at_trade = int(stage_trades)
    state.last_restore_reason = str(reason)
    state.quality_rollouts_since_restore = 0
    state.restored_this_cycle = True
    logger.info(
        "birth.stage2.peak_restore trades=%s reason=%s path=%s peak_wr=%.4f",
        stage_trades,
        reason,
        Path(state.peak_policy_path).name if state.peak_policy_path else "",
        state.peak_winrate,
    )


def note_quality_rollout(state: Stage2PeakState) -> None:
    state.quality_rollouts_since_restore += 1
    state.restored_this_cycle = False


def should_freeze_ppo_after_restore(
    state: Stage2PeakState,
    *,
    cfg: Any = None,
    stage_trades: int | None = None,
) -> tuple[bool, str]:
    """Skip PPO update after restore so peak weights can re-prove on pure eval.

    Live forensics: every peak_restore was followed by ppo.train on anti-edge
    trajectories → peak destroyed before next pure rollout.

    2026-08-12: quality_rollouts counter stuck at 1 for 800+ trades while freeze
    blocked all learning. Hard unstick: freeze ends after max(trades, rollouts).
    """
    if not bool(
        getattr(cfg, "stage2_ppo_freeze_after_restore_enabled", True)
        if cfg is not None
        else True
    ):
        return False, ""
    freeze_n = max(1, _cfg_int(cfg, "stage2_ppo_freeze_rollouts_after_restore", 3))
    freeze_trades = max(
        40, _cfg_int(cfg, "stage2_ppo_freeze_trades_after_restore", 120)
    )
    if bool(state.restored_this_cycle):
        return True, "restored_this_cycle"
    if state.restore_count <= 0:
        return False, ""
    # Trade-based unstick (primary): even if note_quality never fires again.
    try:
        st = int(stage_trades) if stage_trades is not None else 0
    except (TypeError, ValueError):
        st = 0
    last = int(state.last_restore_at_trade or 0)
    if last > 0 and st > 0 and (st - last) >= freeze_trades:
        return False, ""
    if int(state.quality_rollouts_since_restore) >= freeze_n:
        return False, ""
    # Still inside freeze window.
    if last > 0 and st > 0:
        return True, (
            f"quality_rollouts_{state.quality_rollouts_since_restore}/{freeze_n}"
            f"_trades_{st - last}/{freeze_trades}"
        )
    if int(state.quality_rollouts_since_restore) < freeze_n:
        return True, f"quality_rollouts_{state.quality_rollouts_since_restore}/{freeze_n}"
    return False, ""


def should_skip_ppo_quality_gate(
    *,
    chunk_winrate: float | None,
    chunk_trades: int,
    first_touch_wr: float | None = None,
    edge_vs_random: float | None = None,
    lifetime_winrate: float | None = None,
    cfg: Any = None,
) -> tuple[bool, str]:
    """Skip PPO when the just-collected chunk is clearly toxic garbage.

    Floor unchanged. Small chunks (<40) are noisy — do not hard-block learning.
    Allow train when chunk improves vs lifetime (honest gradient), even if still
    below first-touch.
    """
    if not bool(
        getattr(cfg, "stage2_ppo_quality_gate_enabled", True) if cfg is not None else True
    ):
        return False, ""
    # Need a real chunk; micro 8-trade rollouts are noise — never hard-block.
    if chunk_winrate is None or int(chunk_trades) < 40:
        return False, ""
    min_wr = _cfg_float(cfg, "stage2_ppo_quality_min_chunk_wr", 0.26)
    # Improving vs lifetime is always allowed (truthful learning signal).
    if lifetime_winrate is not None and float(chunk_winrate) + 1e-12 >= float(
        lifetime_winrate
    ) - 0.005:
        return False, ""
    if first_touch_wr is not None and float(first_touch_wr) > 0:
        # Soft band: within 6pp of random first-touch (was 4pp — blocked recovery).
        min_wr = max(min_wr, float(first_touch_wr) - 0.06)
    if float(chunk_winrate) + 1e-12 < float(min_wr):
        return True, f"toxic_chunk_wr_{float(chunk_winrate):.3f}<{float(min_wr):.3f}"
    if edge_vs_random is not None and float(edge_vs_random) < -0.03:
        if first_touch_wr is not None and float(chunk_winrate) + 1e-12 < float(
            first_touch_wr
        ) - 0.05:
            return True, f"anti_edge_chunk_{float(chunk_winrate):.3f}"
    return False, ""


def accumulate_exit_physics(
    state: Stage2PeakState,
    *,
    closes_stop: int,
    closes_target: int,
    closes_flatten: int,
    closes_time_stop: int = 0,
    closes_unknown: int = 0,
) -> None:
    state.cumulative_closes_stop += max(0, int(closes_stop))
    state.cumulative_closes_target += max(0, int(closes_target))
    state.cumulative_closes_flatten += max(0, int(closes_flatten))
    state.cumulative_closes_time_stop += max(0, int(closes_time_stop))
    state.cumulative_closes_unknown += max(0, int(closes_unknown))


def best_policy_path_for_restore(state: Stage2PeakState, plateau_state: Any = None) -> str:
    """Prefer peak path; fall back to plateau best paths."""
    peak = str(state.peak_policy_path or "").strip()
    if peak and Path(peak).is_file():
        return peak
    if plateau_state is not None:
        for attr in ("best_rolling_policy_path", "best_policy_path"):
            p = str(getattr(plateau_state, attr, "") or "").strip()
            if p and Path(p).is_file():
                return p
    return peak


def save_peak_policy_copy(
    *,
    host: Any,
    stage_value: str,
    state: Stage2PeakState,
) -> str:
    """Persist current policy as peak snapshot path; return path or ''."""
    try:
        root = Path(getattr(host, "workspace_root", ".") or ".")
        dest = root / "lumina_agents" / "ppo" / f"birth_peak_{stage_value}.zip"
        dest.parent.mkdir(parents=True, exist_ok=True)
        trainer = getattr(host, "ppo_trainer", None)
        if trainer is None:
            return ""
        save = getattr(trainer, "save_weights", None) or getattr(trainer, "save_final_birth_policy", None)
        if not callable(save):
            # try save_final_birth_policy(path)
            s2 = getattr(trainer, "save_final_birth_policy", None)
            if callable(s2):
                s2(str(dest))
                state.peak_policy_path = str(dest)
                return str(dest)
            return ""
        try:
            save(str(dest))
        except TypeError:
            save(path=str(dest))
        state.peak_policy_path = str(dest)
        return str(dest)
    except Exception as exc:
        logger.warning("birth.stage2.peak_save_failed: %s", exc)
        return ""


def restore_policy_from_path(host: Any, path: str) -> bool:
    p = str(path or "").strip()
    if not p or not Path(p).is_file():
        return False
    try:
        trainer = getattr(host, "ppo_trainer", None)
        if trainer is None:
            return False
        load = getattr(trainer, "load_weights", None)
        if not callable(load):
            return False
        loaded = load(p)
        if loaded is not None:
            host.current_policy = loaded
        try:
            eng = getattr(host, "runtime", None) or getattr(host, "engine", None)
            if eng is not None and hasattr(eng, "set_rl_policy") and host.current_policy is not None:
                eng.set_rl_policy(host.current_policy)
        except Exception:
            pass
        return True
    except Exception as exc:
        logger.warning("birth.stage2.peak_restore_load_failed: %s", exc)
        return False


__all__ = [
    "DEFAULT_COLLAPSE_WR_DROP",
    "DEFAULT_NEAR_MISS_DELTA",
    "DEFAULT_PEAK_MIN_TRADES",
    "Stage2PeakState",
    "accumulate_exit_physics",
    "best_policy_path_for_restore",
    "effective_stage2_winrate",
    "evaluate_near_miss",
    "is_near_miss_expectancy",
    "note_quality_rollout",
    "record_restore",
    "restore_policy_from_path",
    "save_peak_policy_copy",
    "finish_mode_blocks_pattern_inject",
    "finish_mode_stable",
    "flash_green_protect_active",
    "mark_volume_rechallenge",
    "maybe_arm_peak_graduation",
    "maybe_arm_quality_lock",
    "maybe_release_quality_lock",
    "quality_lock_would_hop_fail",
    "should_block_phoenix_for_peak",
    "should_defer_swarm_for_exit_forensics",
    "should_defer_swarm_for_peak",
    "should_freeze_ppo_after_restore",
    "should_freeze_ppo_quality_lock",
    "should_skip_ppo_quality_gate",
    "should_restore_peak_policy",
    "should_volume_rechallenge_peak",
    "stage2_expectancy_from_wr",
    "update_finish_mode",
    "update_stage2_peak",
]
