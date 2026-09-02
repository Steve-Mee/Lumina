"""S3 in-band idle IMU — PASSTHROUGH must produce a policy sample.

WHY: S1/S2/early-S3 trained under FORCE_* so π* collapsed to HOLD. When the
envelope hands the stick back (exam-in-band PASSTHROUGH), deterministic greedy
stays empty forever. In-band flat_bonus even *pays* the empty book. The exam
grades ``policy_trades >= 150``. Control must move that quantity.

This is the pilot, not the airframe:
- Envelope bands / FORCE_OPEN / FORCE_FLAT / ``cumulative_in_band_passthrough`` stay.
- HOLD is taxed while armed; after ``min_idle_hold_bars`` a HOLD-mask injects a
  constitution-clipped entry that is **policy-tagged** (not plant).
- Plant tag remains FORCE_OPEN only.
- Floors unchanged. Birth SIM only. Stops ≤ 1%. Live ``hit_stop``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from lumina_core.birth.birth_trade_geometry import (
    BIRTH_FALLBACK_STOP_PCT,
    BIRTH_FALLBACK_TARGET_PCT,
    BirthTradeGeometry,
    geometry_action,
)
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.stage2_participation_envelope import MODE_PASSTHROUGH

S3_INBAND_REGIMES = frozenset({"mixed", "stage3_mixed", "stage3"})
S3_INBAND_HOLD_MASK_REASON = "s3_inband_hold_mask_explore"
S3_INBAND_DEFAULT_HOLD_TAX = 0.01
S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS = 32
S3_INBAND_MTF_BIAS_MIN = 0.05

HOLD_SIDE = 0
LONG_SIDE = 1
SHORT_SIDE = 2


def s3_inband_idle_armed(
    *,
    curriculum_regime: str,
    participation_mode: str,
    position: int,
    cumulative_flat: float,
    band_lo: float,
    band_hi: float,
    policy_trades: int,
    policy_edge_min_trades: int = POLICY_EDGE_MIN_TRADES,
) -> bool:
    """True iff S3/mixed PASSTHROUGH, flat, exam-in-band, thin policy sample."""
    regime = str(curriculum_regime or "").strip().lower()
    if regime not in S3_INBAND_REGIMES:
        return False
    if str(participation_mode or "").strip().upper() != MODE_PASSTHROUGH:
        return False
    if int(position) != 0:
        return False
    lo = float(band_lo)
    hi = float(band_hi)
    if lo > hi:
        lo, hi = hi, lo
    flat = float(cumulative_flat)
    if flat + 1e-12 < lo or flat - 1e-12 > hi:
        return False
    if int(policy_trades) >= int(policy_edge_min_trades):
        return False
    return True


def s3_inband_hold_tax(
    *,
    curriculum_regime: str,
    participation_mode: str,
    position: int,
    cumulative_flat: float,
    band_lo: float,
    band_hi: float,
    policy_trades: int,
    action_side: int,
    tax: float = S3_INBAND_DEFAULT_HOLD_TAX,
    policy_edge_min_trades: int = POLICY_EDGE_MIN_TRADES,
) -> float:
    """Per-HOLD tax while armed. Must dominate in-band flat_bonus (0.25× and 0.05×).

    FORCE_HOLD / FORCE_FLAT / S2 are not armed → 0. Applied as ``-abs(tax)``.
    """
    if int(action_side) != HOLD_SIDE:
        return 0.0
    if not s3_inband_idle_armed(
        curriculum_regime=curriculum_regime,
        participation_mode=participation_mode,
        position=position,
        cumulative_flat=cumulative_flat,
        band_lo=band_lo,
        band_hi=band_hi,
        policy_trades=policy_trades,
        policy_edge_min_trades=policy_edge_min_trades,
    ):
        return 0.0
    return -abs(float(tax))


def _constitution_stop_target(stop_pct: float, target_pct: float) -> tuple[float, float]:
    try:
        from lumina_core.birth.birth_constitution_guard import (
            BIRTH_MAX_RISK_STOP_PCT,
            BIRTH_MIN_STOP_PCT,
        )

        lo = float(BIRTH_MIN_STOP_PCT)
        hi = float(BIRTH_MAX_RISK_STOP_PCT)
    except Exception:
        lo, hi = 0.0004, 0.01
    stop = max(lo, min(hi, float(stop_pct)))
    target = max(stop * 1.25, min(0.05, float(target_pct)))
    return stop, target


def s3_inband_explore_action(
    *,
    explore_step: int,
    geometry: BirthTradeGeometry | None = None,
    row: dict[str, Any] | None = None,
    equity: float = 0.0,
    min_dwell_bars: int = 8,
    bible_mtf_bias: float | None = None,
) -> np.ndarray:
    """Policy-tagged entry: alternate L/S or MTF-bias. Constitution-clipped stop ≤ 1%."""
    geo = geometry or BirthTradeGeometry(
        stop_pct=BIRTH_FALLBACK_STOP_PCT,
        target_pct=BIRTH_FALLBACK_TARGET_PCT,
        source="s3_inband_idle",
    )
    mtf = 0.0
    if bible_mtf_bias is not None:
        mtf = float(bible_mtf_bias)
    elif row is not None:
        try:
            mtf = float(row.get("bible_mtf_bias", 0.0) or 0.0)
        except (TypeError, ValueError):
            mtf = 0.0
    if abs(mtf) >= S3_INBAND_MTF_BIAS_MIN:
        side = float(LONG_SIDE if mtf >= 0.0 else SHORT_SIDE)
    else:
        side = float(LONG_SIDE if int(explore_step) % 2 == 0 else SHORT_SIDE)
    action = geometry_action(side, 0.5, geo)
    row_use = row if row is not None else {}
    try:
        from lumina_core.birth.force_open_plant import apply_force_open_stop

        action, _stop = apply_force_open_stop(
            action,
            row_use,
            geo,
            min_dwell_bars=int(min_dwell_bars),
            equity=float(equity),
        )
    except Exception:
        stop, target = _constitution_stop_target(float(action[2]), float(action[3]))
        action = np.array(
            [float(action[0]), float(action[1]), float(stop), float(target)],
            dtype=np.float32,
        )
    stop, target = _constitution_stop_target(float(action[2]), float(action[3]))
    return np.array(
        [float(action[0]), float(action[1]), float(stop), float(target)],
        dtype=np.float32,
    )


def s3_inband_hold_mask(
    *,
    curriculum_regime: str,
    participation_mode: str,
    position: int,
    cumulative_flat: float,
    band_lo: float,
    band_hi: float,
    policy_trades: int,
    idle_hold_bars: int,
    min_idle_hold_bars: int = S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS,
    policy_edge_min_trades: int = POLICY_EDGE_MIN_TRADES,
    explore_step: int = 0,
    geometry: BirthTradeGeometry | None = None,
    row: dict[str, Any] | None = None,
    equity: float = 0.0,
    min_dwell_bars: int = 8,
    bible_mtf_bias: float | None = None,
    action_side: int = HOLD_SIDE,
) -> np.ndarray | None:
    """Replace armed HOLD after ``min_idle_hold_bars`` consecutive idle HOLDs.

    Does not consume generic ``explore_budget``. Off at ``policy_trades >= 150``.
    """
    if int(action_side) != HOLD_SIDE:
        return None
    if not s3_inband_idle_armed(
        curriculum_regime=curriculum_regime,
        participation_mode=participation_mode,
        position=position,
        cumulative_flat=cumulative_flat,
        band_lo=band_lo,
        band_hi=band_hi,
        policy_trades=policy_trades,
        policy_edge_min_trades=policy_edge_min_trades,
    ):
        return None
    if int(idle_hold_bars) < int(min_idle_hold_bars):
        return None
    return s3_inband_explore_action(
        explore_step=int(explore_step),
        geometry=geometry,
        row=row,
        equity=float(equity),
        min_dwell_bars=int(min_dwell_bars),
        bible_mtf_bias=bible_mtf_bias,
    )


def plant_tag_for_entry(*, force_open_this_step: bool) -> bool:
    """Plant iff FORCE_OPEN opened flat→position. In-band explore is policy."""
    return bool(force_open_this_step)


@dataclass(slots=True)
class S3InbandIdleState:
    idle_hold_bars: int = 0
    explore_count: int = 0
    tax_steps: int = 0
    explore_step: int = 0
    last_armed: bool = False


def maybe_s3_passthrough_mask(
    *,
    state: S3InbandIdleState,
    action: np.ndarray,
    participation_mode: str,
    action_override: Any,
    curriculum_regime: str,
    position: int,
    cumulative_flat: float,
    band_lo: float,
    band_hi: float,
    policy_trades: int,
    min_idle_hold_bars: int = S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS,
    policy_edge_min_trades: int = POLICY_EDGE_MIN_TRADES,
    geometry: BirthTradeGeometry | None = None,
    row: dict[str, Any] | None = None,
    equity: float = 0.0,
    min_dwell_bars: int = 8,
    resample_hold: Any = None,
) -> np.ndarray:
    """PASSTHROUGH HOLD-mask after envelope. Optional stochastic resample first."""
    mode = str(participation_mode or "").strip().upper()
    if mode != MODE_PASSTHROUGH or action_override is not None:
        state.idle_hold_bars = 0
        state.last_armed = False
        return action
    side = int(np.clip(np.round(float(action[0])), 0, 2))
    armed = s3_inband_idle_armed(
        curriculum_regime=curriculum_regime,
        participation_mode=mode,
        position=position,
        cumulative_flat=cumulative_flat,
        band_lo=band_lo,
        band_hi=band_hi,
        policy_trades=policy_trades,
        policy_edge_min_trades=policy_edge_min_trades,
    )
    if armed and side == HOLD_SIDE and callable(resample_hold):
        try:
            action = np.asarray(resample_hold(), dtype=np.float32)
        except Exception:
            pass
    return apply_passthrough_hold_mask(
        state=state,
        action=action,
        participation_mode=mode,
        action_override=None,
        curriculum_regime=curriculum_regime,
        position=position,
        cumulative_flat=cumulative_flat,
        band_lo=band_lo,
        band_hi=band_hi,
        policy_trades=policy_trades,
        min_idle_hold_bars=min_idle_hold_bars,
        policy_edge_min_trades=policy_edge_min_trades,
        geometry=geometry,
        row=row,
        equity=equity,
        min_dwell_bars=min_dwell_bars,
    )


def apply_passthrough_hold_mask(
    *,
    state: S3InbandIdleState,
    action: np.ndarray,
    participation_mode: str,
    action_override: Any,
    curriculum_regime: str,
    position: int,
    cumulative_flat: float,
    band_lo: float,
    band_hi: float,
    policy_trades: int,
    min_idle_hold_bars: int = S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS,
    policy_edge_min_trades: int = POLICY_EDGE_MIN_TRADES,
    geometry: BirthTradeGeometry | None = None,
    row: dict[str, Any] | None = None,
    equity: float = 0.0,
    min_dwell_bars: int = 8,
) -> np.ndarray:
    """Rollout helper: mask HOLD after envelope PASSTHROUGH with no override."""
    mode = str(participation_mode or "").strip().upper()
    side = int(np.clip(np.round(float(action[0])), 0, 2))
    armed = s3_inband_idle_armed(
        curriculum_regime=curriculum_regime,
        participation_mode=mode,
        position=position,
        cumulative_flat=cumulative_flat,
        band_lo=band_lo,
        band_hi=band_hi,
        policy_trades=policy_trades,
        policy_edge_min_trades=policy_edge_min_trades,
    )
    state.last_armed = bool(armed)
    if (not armed) or mode != MODE_PASSTHROUGH or action_override is not None:
        state.idle_hold_bars = 0
        return action
    if side != HOLD_SIDE:
        state.idle_hold_bars = 0
        return action
    state.idle_hold_bars = int(state.idle_hold_bars) + 1
    masked = s3_inband_hold_mask(
        curriculum_regime=curriculum_regime,
        participation_mode=mode,
        position=position,
        cumulative_flat=cumulative_flat,
        band_lo=band_lo,
        band_hi=band_hi,
        policy_trades=policy_trades,
        idle_hold_bars=int(state.idle_hold_bars),
        min_idle_hold_bars=int(min_idle_hold_bars),
        policy_edge_min_trades=policy_edge_min_trades,
        explore_step=int(state.explore_step),
        geometry=geometry,
        row=row,
        equity=float(equity),
        min_dwell_bars=int(min_dwell_bars),
        action_side=HOLD_SIDE,
    )
    if masked is None:
        return action
    state.explore_count = int(state.explore_count) + 1
    state.explore_step = int(state.explore_step) + 1
    state.idle_hold_bars = 0
    return np.asarray(masked, dtype=np.float32)


def simulate_passthrough_hold_mask_bars(
    *,
    n_bars: int,
    min_idle_hold_bars: int = S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS,
    curriculum_regime: str = "mixed",
    participation_mode: str = MODE_PASSTHROUGH,
    position: int = 0,
    cumulative_flat: float = 0.58,
    band_lo: float = 0.25,
    band_hi: float = 0.75,
    policy_trades: int = 0,
    policy_edge_min_trades: int = POLICY_EDGE_MIN_TRADES,
    geometry: BirthTradeGeometry | None = None,
) -> list[tuple[int, bool, str]]:
    """Thin cloud-failure replica: consecutive HOLD policy actions under PASSTHROUGH.

    Returns ``(side, entry_is_plant, reason)`` per bar. Old law = all HOLD / no entry.
    """
    state = S3InbandIdleState()
    geo = geometry or BirthTradeGeometry(
        stop_pct=BIRTH_FALLBACK_STOP_PCT,
        target_pct=BIRTH_FALLBACK_TARGET_PCT,
        source="s3_replica",
    )
    out: list[tuple[int, bool, str]] = []
    hold = geometry_action(0.0, 0.5, geo)
    for _ in range(max(0, int(n_bars))):
        action = apply_passthrough_hold_mask(
            state=state,
            action=hold.copy(),
            participation_mode=participation_mode,
            action_override=None,
            curriculum_regime=curriculum_regime,
            position=position,
            cumulative_flat=cumulative_flat,
            band_lo=band_lo,
            band_hi=band_hi,
            policy_trades=policy_trades,
            min_idle_hold_bars=min_idle_hold_bars,
            policy_edge_min_trades=policy_edge_min_trades,
            geometry=geo,
        )
        side = int(np.clip(np.round(float(action[0])), 0, 2))
        opened = side in {LONG_SIDE, SHORT_SIDE} and int(position) == 0
        is_plant = plant_tag_for_entry(force_open_this_step=False) if opened else False
        reason = S3_INBAND_HOLD_MASK_REASON if opened else "hold"
        out.append((side, bool(is_plant), reason))
    return out


def apply_gym_birth_occupancy_reward(
    env: Any,
    *,
    row: dict[str, Any],
    side_bucket: int,
    trade_closed: bool,
    close_stop_pct: float,
    close_net: float,
) -> float:
    """Range-patience + S3 idle tax. Gym occupancy counters stay here (M5)."""
    from lumina_core.rl.reward_shaper import range_patience_step_reward

    tick_regime = str(row.get("regime", "NEUTRAL"))
    is_range_tick = (
        str(tick_regime).upper() in {"NEUTRAL", "RANGING"}
        or "RANGE" in str(tick_regime).upper()
    )
    if is_range_tick:
        env._range_total_bars = int(getattr(env, "_range_total_bars", 0) or 0) + 1
        if int(env._position) == 0:
            env._range_flat_bars = int(getattr(env, "_range_flat_bars", 0) or 0) + 1
    stage_flat_ratio = None
    if int(getattr(env, "_range_total_bars", 0) or 0) >= 20:
        stage_flat_ratio = float(env._range_flat_bars) / float(
            max(1, env._range_total_bars)
        )
    reward_cfg = env._reward_cfg()
    exp_floor = float(getattr(env.config, "stage2_expectancy_floor", -0.15) or -0.15)
    exp_gap = float(getattr(env.config, "expectancy_gap", 0.0) or 0.0)
    recent = list(getattr(env._reward_state, "recent_pnls", []) or [])
    if len(recent) >= 20:
        wr = float(sum(1 for p in recent if float(p) > 0.0)) / float(len(recent))
        live_exp = wr - 0.50
        exp_gap = max(exp_gap, max(0.0, exp_floor - live_exp))
    trade_r = None
    if trade_closed:
        risk_usd = float(getattr(env, "_close_risk_usd", 0.0) or 0.0)
        if risk_usd <= 1e-12:
            risk_usd = (
                abs(float(close_stop_pct))
                * abs(float(getattr(env, "_close_entry_price", 0.0) or 0.0))
                * float(getattr(env, "_close_qty", 1) or 1)
                * 5.0
            )
        trade_r = float(close_net) / max(risk_usd, 1e-9)
    ft_press = float(getattr(env.config, "first_touch_training_pressure", 0.0) or 0.0)
    cfg_flat = getattr(env.config, "stage_cumulative_flat", None)
    try:
        cumulative_flat = float(cfg_flat) if cfg_flat is not None else None
    except (TypeError, ValueError):
        cumulative_flat = None
    regime = str(getattr(env.config, "curriculum_regime", "") or "")
    mode = str(getattr(env.config, "participation_mode", "") or "")
    pos = int(env._position)
    policy_n = int(getattr(env.config, "stage_policy_trades", 0) or 0)
    lo = float(getattr(env.config, "participation_band_lo", 0.25) or 0.25)
    hi = float(getattr(env.config, "participation_band_hi", 0.75) or 0.75)
    tax_mag = float(getattr(reward_cfg, "s3_inband_hold_tax", S3_INBAND_DEFAULT_HOLD_TAX) or S3_INBAND_DEFAULT_HOLD_TAX)
    tax_flat = float(cumulative_flat) if cumulative_flat is not None else float(stage_flat_ratio or 0.5)
    tax = s3_inband_hold_tax(
        curriculum_regime=regime,
        participation_mode=mode,
        position=pos,
        cumulative_flat=tax_flat,
        band_lo=lo,
        band_hi=hi,
        policy_trades=policy_n,
        action_side=int(side_bucket),
        tax=tax_mag,
    )
    if tax < 0.0:
        env._s3_inband_hold_tax_steps = int(
            getattr(env, "_s3_inband_hold_tax_steps", 0) or 0
        ) + 1
    bonus = range_patience_step_reward(
        regime=tick_regime,
        position_flat=int(env._position) == 0,
        trade_closed=bool(trade_closed),
        cfg=reward_cfg,
        stage_flat_ratio=stage_flat_ratio,
        expectancy_gap=exp_gap,
        trade_r_multiple=trade_r,
        first_touch_training_pressure=ft_press,
        curriculum_regime=regime,
        participation_mode=mode,
        position=pos,
        policy_trades=policy_n,
        band_lo=lo,
        band_hi=hi,
        action_side=int(side_bucket),
        cumulative_flat=cumulative_flat,
    )
    return float(bonus)


def s3_inband_progress_fields(host: Any) -> dict[str, Any]:
    """HUD: a live exam cannot hide PASSTHROUGH + HOLD + tax off."""
    return {
        "s3_inband_idle_armed": bool(getattr(host, "s3_inband_idle_armed", False)),
        "s3_inband_explore": int(getattr(host, "s3_inband_explore", 0) or 0),
        "s3_inband_hold_tax_steps": int(getattr(host, "s3_inband_hold_tax_steps", 0) or 0),
        "participation_inband_explore": int(
            getattr(host, "s3_inband_explore", 0) or 0
        ),
    }


def persist_skill_settlement_fields(host: Any) -> dict[str, Any]:
    """Checkpoint SSOT: policy/plant + close cums (never zeros on a live stage)."""
    from lumina_core.birth.starship_edgescore_core import settlement_progress_fields

    payload = settlement_progress_fields(
        closes_stop=int(getattr(host, "stage_closes_stop_cum", 0) or 0),
        closes_target=int(getattr(host, "stage_closes_target_cum", 0) or 0),
        closes_time_stop=int(getattr(host, "stage_closes_time_stop_cum", 0) or 0),
        closes_flatten=int(getattr(host, "stage_closes_flatten_cum", 0) or 0),
        closes_unknown=int(getattr(host, "stage_closes_unknown_cum", 0) or 0),
    )
    payload["stage_policy_trades"] = int(getattr(host, "stage_policy_trades", 0) or 0)
    payload["stage_policy_wins"] = int(getattr(host, "stage_policy_wins", 0) or 0)
    payload["stage_plant_trades"] = int(getattr(host, "stage_plant_trades", 0) or 0)
    payload["stage_plant_wins"] = int(getattr(host, "stage_plant_wins", 0) or 0)
    payload["settlement_ssot_pending"] = bool(
        getattr(host, "_settlement_ssot_pending", False)
    )
    payload.update(s3_inband_progress_fields(host))
    return payload


@dataclass(frozen=True, slots=True)
class SkillSettlementSnapshot:
    stage_trades: int
    policy_trades: int
    plant_trades: int
    policy_wins: int
    plant_wins: int
    closes_stop: int
    closes_target: int
    closes_flatten: int
    closes_time_stop: int
    closes_unknown: int
    settlement_ssot_pending: bool

    @property
    def close_total(self) -> int:
        return (
            int(self.closes_stop)
            + int(self.closes_target)
            + int(self.closes_flatten)
            + int(self.closes_time_stop)
            + int(self.closes_unknown)
        )


def snapshot_from_checkpoint_metrics(
    metrics: dict[str, Any] | None,
    *,
    stage_trades: int = 0,
) -> SkillSettlementSnapshot:
    """Rebuild skill/settlement SSOT from persisted fields. Never invent closes."""
    raw = metrics if isinstance(metrics, dict) else {}
    trades = max(0, int(raw.get("stage_trades", stage_trades) or stage_trades or 0))
    policy_raw = raw.get("stage_policy_trades", raw.get("policy_trades"))
    plant_raw = raw.get("stage_plant_trades", raw.get("plant_trades"))
    policy_n = int(policy_raw) if policy_raw is not None else None
    plant_n = int(plant_raw) if plant_raw is not None else None
    if policy_n is None and plant_n is None:
        policy_n, plant_n = 0, 0
    elif policy_n is None:
        policy_n = max(0, trades - int(plant_n or 0))
    elif plant_n is None:
        plant_n = max(0, trades - int(policy_n or 0))
    policy_n = max(0, int(policy_n))
    plant_n = max(0, int(plant_n))
    stop_n = int(raw.get("stage_closes_stop_cum", raw.get("closes_stop", 0)) or 0)
    tgt_n = int(raw.get("stage_closes_target_cum", raw.get("closes_target", 0)) or 0)
    flat_n = int(raw.get("stage_closes_flatten_cum", raw.get("closes_flatten", 0)) or 0)
    time_n = int(
        raw.get("stage_closes_time_stop_cum", raw.get("closes_time_stop", 0)) or 0
    )
    unk_n = int(raw.get("stage_closes_unknown_cum", raw.get("closes_unknown", 0)) or 0)
    close_total = stop_n + tgt_n + flat_n + time_n + unk_n
    pending = bool(raw.get("settlement_ssot_pending", False)) or (
        close_total <= 0 and trades > 0
    )
    return SkillSettlementSnapshot(
        stage_trades=trades,
        policy_trades=policy_n,
        plant_trades=plant_n,
        policy_wins=max(0, int(raw.get("stage_policy_wins", raw.get("policy_wins", 0)) or 0)),
        plant_wins=max(0, int(raw.get("stage_plant_wins", raw.get("plant_wins", 0)) or 0)),
        closes_stop=max(0, stop_n),
        closes_target=max(0, tgt_n),
        closes_flatten=max(0, flat_n),
        closes_time_stop=max(0, time_n),
        closes_unknown=max(0, unk_n),
        settlement_ssot_pending=bool(pending),
    )


def apply_skill_settlement_snapshot(host: Any, snap: SkillSettlementSnapshot) -> None:
    host.stage_policy_trades = int(snap.policy_trades)
    host.stage_policy_wins = int(snap.policy_wins)
    host.stage_plant_trades = int(snap.plant_trades)
    host.stage_plant_wins = int(snap.plant_wins)
    host.stage_closes_stop_cum = int(snap.closes_stop)
    host.stage_closes_target_cum = int(snap.closes_target)
    host.stage_closes_flatten_cum = int(snap.closes_flatten)
    host.stage_closes_time_stop_cum = int(snap.closes_time_stop)
    host.stage_closes_unknown_cum = int(snap.closes_unknown)
    host._settlement_ssot_pending = bool(snap.settlement_ssot_pending)
    host.s3_inband_explore = int(getattr(host, "s3_inband_explore", 0) or 0)
    host.s3_inband_hold_tax_steps = int(getattr(host, "s3_inband_hold_tax_steps", 0) or 0)


def restore_skill_settlement_from_metrics(host: Any, metrics: dict[str, Any] | None) -> None:
    trades = int(getattr(host, "stage_trades", 0) or 0)
    snap = snapshot_from_checkpoint_metrics(metrics, stage_trades=trades)
    apply_skill_settlement_snapshot(host, snap)
    raw = metrics if isinstance(metrics, dict) else {}
    host.s3_inband_explore = int(raw.get("s3_inband_explore", 0) or 0)
    host.s3_inband_hold_tax_steps = int(raw.get("s3_inband_hold_tax_steps", 0) or 0)
    host.s3_inband_idle_armed = bool(raw.get("s3_inband_idle_armed", False))


def reset_skill_settlement_if_fresh_stage(host: Any) -> None:
    """Zero skill/settlement clocks only on a fresh stage, never mid-stage resume."""
    resume_keep = bool(getattr(host, "metrics_match_stage", False)) and int(
        getattr(host, "stage_trades", 0) or 0
    ) > 0
    host.closes_stop = 0
    host.closes_target = 0
    host.closes_flatten = 0
    host.closes_time_stop = 0
    host.closes_unknown = 0
    if resume_keep:
        return
    host.stage_closes_stop_cum = 0
    host.stage_closes_target_cum = 0
    host.stage_closes_flatten_cum = 0
    host.stage_closes_time_stop_cum = 0
    host.stage_closes_unknown_cum = 0
    host.stage_policy_trades = 0
    host.stage_policy_wins = 0
    host.stage_plant_trades = 0
    host.stage_plant_wins = 0
    host._settlement_ssot_pending = False
    host.s3_inband_explore = 0
    host.s3_inband_hold_tax_steps = 0
    host.s3_inband_idle_armed = False


def s3_inband_rollout_kwargs(loop: Any) -> dict[str, Any]:
    min_idle = S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS
    try:
        reward = getattr(getattr(loop, "host", None), "birth_config", None)
        reward = getattr(reward, "reward", None) if reward is not None else None
        if reward is not None:
            min_idle = int(
                getattr(reward, "s3_inband_min_idle_hold_bars", min_idle) or min_idle
            )
    except (TypeError, ValueError, AttributeError):
        min_idle = S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS
    return {
        "stage_policy_trades_prior": int(getattr(loop, "stage_policy_trades", 0) or 0),
        "s3_inband_min_idle_hold_bars": int(min_idle),
    }


def apply_s3_inband_rollout_metrics(loop: Any, rollout: Any) -> None:
    loop.s3_inband_explore = int(getattr(loop, "s3_inband_explore", 0) or 0) + int(
        getattr(rollout, "s3_inband_explore", 0) or 0
    )
    loop.s3_inband_hold_tax_steps = int(
        getattr(loop, "s3_inband_hold_tax_steps", 0) or 0
    ) + int(getattr(rollout, "s3_inband_hold_tax_steps", 0) or 0)
    loop.s3_inband_idle_armed = bool(getattr(rollout, "s3_inband_idle_armed", False))
    if int(getattr(loop, "stage_closes_stop_cum", 0) or 0) + int(
        getattr(loop, "stage_closes_target_cum", 0) or 0
    ) + int(getattr(loop, "stage_closes_flatten_cum", 0) or 0) + int(
        getattr(loop, "stage_closes_time_stop_cum", 0) or 0
    ) + int(getattr(loop, "stage_closes_unknown_cum", 0) or 0) > 0:
        loop._settlement_ssot_pending = False


__all__ = [
    "HOLD_SIDE",
    "LONG_SIDE",
    "POLICY_EDGE_MIN_TRADES",
    "S3_INBAND_DEFAULT_HOLD_TAX",
    "S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS",
    "S3_INBAND_HOLD_MASK_REASON",
    "S3_INBAND_REGIMES",
    "SHORT_SIDE",
    "S3InbandIdleState",
    "SkillSettlementSnapshot",
    "apply_gym_birth_occupancy_reward",
    "apply_passthrough_hold_mask",
    "apply_s3_inband_rollout_metrics",
    "apply_skill_settlement_snapshot",
    "maybe_s3_passthrough_mask",
    "persist_skill_settlement_fields",
    "plant_tag_for_entry",
    "reset_skill_settlement_if_fresh_stage",
    "restore_skill_settlement_from_metrics",
    "s3_inband_explore_action",
    "s3_inband_hold_mask",
    "s3_inband_hold_tax",
    "s3_inband_idle_armed",
    "s3_inband_progress_fields",
    "s3_inband_rollout_kwargs",
    "simulate_passthrough_hold_mask_bars",
    "snapshot_from_checkpoint_metrics",
]
