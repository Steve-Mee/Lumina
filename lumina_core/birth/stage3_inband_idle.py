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

S4 Gate B2 (same tape): envelope is off for ``stage4_viable_plant``, so the book
is PASSTHROUGH at flat=1.0. S3 idle stayed dead (regime-gated + in-band). The
one measured follow-up is stage-local: arm the same tax/mask on S4 PASSTHROUGH
even when over-flat. S2 dual IMU and S3 in-band law are unchanged.
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
# S4 envelope is off (pre_caps is_s2/is_s3 only). Idle must still produce a
# policy sample under PASSTHROUGH — including over-flat HOLD collapse.
S4_IDLE_REGIMES = frozenset({"stage4_viable_plant", "stage4", "viable_plant"})
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
    """True iff S3 in-band or S4 PASSTHROUGH, flat, thin policy sample."""
    regime = str(curriculum_regime or "").strip().lower()
    s4_idle = regime in S4_IDLE_REGIMES
    if regime not in S3_INBAND_REGIMES and not s4_idle:
        return False
    if str(participation_mode or "").strip().upper() != MODE_PASSTHROUGH:
        return False
    if int(position) != 0:
        return False
    # S3: envelope owns over/under. S4: no envelope — PASSTHROUGH is the book.
    if not s4_idle:
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


__all__ = [
    "HOLD_SIDE",
    "LONG_SIDE",
    "POLICY_EDGE_MIN_TRADES",
    "S3_INBAND_DEFAULT_HOLD_TAX",
    "S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS",
    "S3_INBAND_HOLD_MASK_REASON",
    "S3_INBAND_REGIMES",
    "S4_IDLE_REGIMES",
    "SHORT_SIDE",
    "S3InbandIdleState",
    "apply_passthrough_hold_mask",
    "maybe_s3_passthrough_mask",
    "plant_tag_for_entry",
    "s3_inband_explore_action",
    "s3_inband_hold_mask",
    "s3_inband_hold_tax",
    "s3_inband_idle_armed",
]
