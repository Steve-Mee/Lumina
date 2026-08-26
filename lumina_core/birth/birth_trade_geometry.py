"""Birth trade geometry SSOT: stop/target scale from real tick move distribution.

Oracle mining, live SIM defaults, exploration actions, and Stage-2 participation
force-open must share the same physics. Legacy 0.75%/1.5% stops never hit on
1-min MES (median move ~0.15%) and poison expectancy learning transfer.

CRITICAL (forensics 2026-08): peak-move calibration MUST run on time-ordered
bars only. Shuffled / IID-sampled pools make "180 consecutive rows" span random
price jumps → hard-cap 0.8%/1.5% with a false ``move_distribution`` label.

CRITICAL (forensics 2026-08 expectancy): min-floor micro stops can be
cost-inviable on MES (fees+slip >> target). Cost-aware lift keeps net RR
honest without inventing edge or lowering expectancy floors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from lumina_core.birth.birth_constitution_guard import (
    BIRTH_MAX_RISK_STOP_PCT,
    BIRTH_MIN_STOP_PCT,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.trade_geometry")

# Birth-scale fallbacks when ticks are too thin to calibrate.
BIRTH_FALLBACK_STOP_PCT = 0.0012
BIRTH_FALLBACK_TARGET_PCT = 0.0020
# Hard constitution-safe ceiling (Birth SIM plant law) — SSOT with constitution guard.
BIRTH_MAX_STOP_PCT = float(BIRTH_MAX_RISK_STOP_PCT)
BIRTH_MAX_TARGET_PCT = 0.05
# Floor SSOT with constitution (must not re-widen calibrated micro stops below this).
BIRTH_GEO_MIN_STOP_PCT = float(BIRTH_MIN_STOP_PCT)
# Legacy mis-scale (pre-calib) — never use as default in birth rollouts.
LEGACY_MACRO_STOP_PCT = 0.0075
LEGACY_MACRO_TARGET_PCT = 0.015
# Peak-move calib hard caps (still constitution-safe, but never from disordered pools).
_PEAK_STOP_CAP = 0.008
_PEAK_TARGET_CAP = 0.015
MACRO_STOP_THRESHOLD = 0.005
_ORDERED_PAIR_FRACTION = 0.85
SOFT_PRIOR_DEFAULT_MULTIPLE = 2.5
_GAP_MEDIAN_MULT = 8.0
_GAP_MIN_SEC = 300.0
SEGMENT_BREAK_KEY = "_segment_break"
SEGMENT_ID_KEY = "_segment_id"

# Cost model defaults (MES SIM — truthful friction, not a loophole).
MES_POINT_VALUE_USD = 5.0
MES_TICK_SIZE = 0.25
DEFAULT_FEE_RT_USD = 2.50
DEFAULT_SLIP_TICKS_PER_SIDE = 1.0
# After costs: net_win / |net_loss| must be ≥ this (still lose more often if WR low).
MIN_NET_RR_AFTER_COST = 0.80
# Target gross RR when lifting for cost viability (still ≥ 1.25 clamp).
COST_LIFT_GROSS_RR = 1.50
# Prefer geometries where break-even WR after cost is ≤ this when data allows.
# Honest: if data cannot reach it under constitution caps, set econ_proxy_mismatch.
TARGET_BE_WR_AFTER_COST = 0.48
# Higher gross RR candidate for BE-WR scale (still capped by peak/constitution).
COST_LIFT_GROSS_RR_STRETCH = 1.75


def economic_skill_gap(*, be_wr: float, skill_wr: float) -> float:
    """max(0, economic BE-WR − skill WR). Training pressure only — floors unchanged.

    Live forensics 2026-08-13: using TARGET_BE_WR (0.48) as the skill-side floor
    zeroed pressure whenever geometry BE was already < 0.48 (e.g. 43%) while
    skill WR sat at 30%.
    """
    return max(0.0, float(be_wr) - float(skill_wr))


@dataclass(frozen=True, slots=True)
class BirthTradeGeometry:
    stop_pct: float
    target_pct: float
    source: str = "fallback"
    time_ordered: bool = True
    p40_raw: float = 0.0
    hold_bars: int = 0
    pool_size: int = 0
    macro_rejected: bool = False
    floor_bound: bool = False
    net_rr_after_cost: float = 0.0
    breakeven_wr_after_cost: float = 0.0
    cost_usd: float = 0.0
    ref_price: float = 0.0
    # True when best data-driven geometry still has BE-WR > proxy-relevant target.
    # Does NOT lower expectancy floors — honest plant diagnostic only.
    econ_proxy_mismatch: bool = False

    def as_action_tail(self) -> tuple[float, float]:
        return float(self.stop_pct), float(self.target_pct)


def _tick_price(tick: dict[str, Any]) -> float:
    try:
        return float(tick.get("last") or tick.get("close") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _bar_index(tick: dict[str, Any]) -> float | None:
    for key in ("bar_index", "bar_idx", "index"):
        raw = tick.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def _timestamp_key(tick: dict[str, Any]) -> float | None:
    raw = tick.get("timestamp") or tick.get("ts") or tick.get("time")
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        from datetime import datetime

        s = str(raw).replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        try:
            return float(str(raw))
        except (TypeError, ValueError):
            return None


def is_time_ordered(ticks: list[dict[str, Any]] | None, *, min_pairs: int = 20) -> bool:
    """True when bar_index or timestamp is predominantly non-decreasing."""
    pool = list(ticks or [])
    if len(pool) < 3:
        return True

    idxs: list[float] = []
    for t in pool:
        bi = _bar_index(t)
        if bi is not None:
            idxs.append(bi)
    use_idx = len(idxs) >= max(min_pairs, int(0.5 * len(pool)))

    if use_idx:
        series = idxs
    else:
        stamps: list[float] = []
        for t in pool:
            ts = _timestamp_key(t)
            if ts is not None:
                stamps.append(ts)
        if len(stamps) < max(min_pairs, int(0.5 * len(pool))):
            return True
        series = stamps

    if len(series) < 3:
        return True
    ok = 0
    total = 0
    for a, b in zip(series, series[1:]):
        total += 1
        if b >= a - 1e-12:
            ok += 1
    if total < 2:
        return True
    return (ok / float(total)) >= _ORDERED_PAIR_FRACTION


def clamp_birth_geometry(
    stop_pct: float,
    target_pct: float,
) -> tuple[float, float]:
    """Constitution-safe clamps; preserve RR ≥ 1.25 when possible."""
    stop = max(BIRTH_GEO_MIN_STOP_PCT, min(BIRTH_MAX_STOP_PCT, float(stop_pct)))
    target = max(stop * 1.25, min(BIRTH_MAX_TARGET_PCT, float(target_pct)))
    return float(stop), float(target)


def median_tick_price(ticks: list[dict[str, Any]] | None) -> float:
    prices = [_tick_price(t) for t in (ticks or [])]
    prices = [p for p in prices if p > 0]
    if not prices:
        return 7500.0
    return float(np.median(np.asarray(prices, dtype=float)))


def estimate_round_trip_cost_usd(
    *,
    price: float = 7500.0,
    point_value: float = MES_POINT_VALUE_USD,
    tick_size: float = MES_TICK_SIZE,
    fee_rt_usd: float = DEFAULT_FEE_RT_USD,
    slip_ticks_per_side: float = DEFAULT_SLIP_TICKS_PER_SIDE,
) -> float:
    """Truthful MES-like round-trip friction (entry+exit slip + fees)."""
    px = max(1.0, float(price))
    tick_val = max(1e-9, float(point_value) * float(tick_size))
    slip = 2.0 * max(0.0, float(slip_ticks_per_side)) * tick_val
    fees = max(0.0, float(fee_rt_usd))
    _ = px  # price reserved for future % fee models
    return float(slip + fees)


def economics_after_cost(
    stop_pct: float,
    target_pct: float,
    *,
    price: float,
    cost_usd: float | None = None,
    point_value: float = MES_POINT_VALUE_USD,
) -> tuple[float, float, float, float, float]:
    """Return (net_win, net_loss_abs, net_rr, breakeven_wr, cost_usd)."""
    px = max(1.0, float(price))
    pv = max(1e-9, float(point_value))
    cost = float(cost_usd) if cost_usd is not None else estimate_round_trip_cost_usd(price=px)
    risk_usd = max(0.0, float(stop_pct) * px * pv)
    tgt_usd = max(0.0, float(target_pct) * px * pv)
    net_win = tgt_usd - cost
    net_loss = risk_usd + cost
    if net_win > 0 and net_loss > 0:
        net_rr = net_win / net_loss
        breakeven = net_loss / (net_win + net_loss)
    elif net_win <= 0:
        net_rr = 0.0
        breakeven = 1.0
    else:
        net_rr = 99.0
        breakeven = 0.0
    return float(net_win), float(net_loss), float(net_rr), float(breakeven), float(cost)


def _apply_cost_viability(
    stop: float,
    target: float,
    *,
    price: float,
    atr_med: float | None,
    p50: float | None,
    source: str,
) -> tuple[float, float, str, bool, float, float, float, bool]:
    """Lift stop/target data-driven until net RR after cost ≥ MIN_NET_RR_AFTER_COST
    and, when data allows, break-even WR ≤ TARGET_BE_WR_AFTER_COST.

    Never invents edge: only raises to ATR/p50 bands or cost-required minimums
    still inside constitution caps. Floor-bound flag set when constitution min bound.
    Returns econ_proxy_mismatch when best effort still has BE-WR above target
    (35% WR proxy is then not dollar-+EV — honest diagnostic, no floor change).
    """
    px = max(1.0, float(price))
    cost = estimate_round_trip_cost_usd(price=px)
    s, t = clamp_birth_geometry(stop, target)
    floor_bound = abs(s - BIRTH_GEO_MIN_STOP_PCT) < 1e-12
    net_win, net_loss, net_rr, be_wr, cost = economics_after_cost(s, t, price=px, cost_usd=cost)
    be_target = float(TARGET_BE_WR_AFTER_COST)
    # Already cost-viable AND BE-WR at/under target → no lift needed.
    if (
        net_rr >= MIN_NET_RR_AFTER_COST
        and net_win > 0
        and be_wr <= be_target + 1e-12
    ):
        return s, t, source, floor_bound, net_rr, be_wr, cost, False

    # Data-driven lift candidates (never legacy macro defaults).
    candidates: list[float] = [s]
    if atr_med is not None and atr_med > 0:
        candidates.append(float(atr_med) * 0.9)
        candidates.append(float(atr_med) * 1.1)
        candidates.append(float(atr_med) * 1.25)
        candidates.append(float(atr_med) * 1.5)
    if p50 is not None and p50 > 0:
        candidates.append(float(p50) * 0.85)
        candidates.append(float(p50) * 1.0)
        candidates.append(float(p50) * 1.15)
        candidates.append(float(p50) * 1.35)
    # Minimum stop so that with gross RR, net_rr >= min:
    # (rr*R - C) / (R + C) >= k  =>  R*(rr-k) >= C(1+k)
    rr_levels = (COST_LIFT_GROSS_RR, COST_LIFT_GROSS_RR_STRETCH)
    k = MIN_NET_RR_AFTER_COST
    for rr in rr_levels:
        if rr > k + 1e-9:
            min_risk_usd = cost * (1.0 + k) / (rr - k)
            min_stop = min_risk_usd / (px * MES_POINT_VALUE_USD)
            candidates.append(min_stop)
            # Also size so BE-WR ≈ target: be = L/(W+L) => W/L = (1-be)/be = net_rr
            # With gross rr: (rr*R - C)/(R + C) = target_net_rr_for_be
            # target net_rr for be: (1-be)/be
            target_nrr = (1.0 - be_target) / max(1e-9, be_target)
            if rr > target_nrr + 1e-9:
                # (rr*R - C) >= target_nrr * (R + C) => R*(rr - target_nrr) >= C*(1+target_nrr)
                min_risk_be = cost * (1.0 + target_nrr) / (rr - target_nrr)
                candidates.append(min_risk_be / (px * MES_POINT_VALUE_USD))

    best_s, best_t = s, t
    best_rr, best_be = net_rr, be_wr
    # Prefer candidates that clear min net RR, then lowest break-even WR.
    scored: list[tuple[float, float, float, float, float]] = []
    for cand in sorted(set(max(BIRTH_GEO_MIN_STOP_PCT, min(_PEAK_STOP_CAP, c)) for c in candidates)):
        for rr in rr_levels:
            cand_t = max(cand * rr, cand * 1.25)
            cand_t = min(_PEAK_TARGET_CAP, cand_t)
            cs, ct = clamp_birth_geometry(cand, cand_t)
            nw, nl, nrr, be, _ = economics_after_cost(cs, ct, price=px, cost_usd=cost)
            if nw <= 0:
                continue
            # score: primary net_rr (higher better), secondary -be_wr (lower better)
            scored.append((nrr, -be, cs, ct, be))
    if scored:
        scored.sort(reverse=True)
        viable = [row for row in scored if row[0] + 1e-12 >= MIN_NET_RR_AFTER_COST]
        if viable:
            # Prefer BE-WR under target; among those (or all viable) lowest BE-WR.
            under_be = [row for row in viable if row[4] <= be_target + 1e-12]
            pool = under_be if under_be else viable
            pick = min(pool, key=lambda r: r[4])
        else:
            pick = scored[0]
        best_rr, _, best_s, best_t, best_be = pick

    out_source = source
    if best_s > s + 1e-12 or best_t > t + 1e-12:
        out_source = f"{source}+cost_lift"
        floor_bound = abs(best_s - BIRTH_GEO_MIN_STOP_PCT) < 1e-12
        logger.info(
            "birth.geometry.cost_lift stop=%.6f→%.6f tgt=%.6f→%.6f net_rr=%.3f be_wr=%.3f cost=%.2f",
            s,
            best_s,
            t,
            best_t,
            best_rr,
            best_be,
            cost,
        )
    else:
        floor_bound = abs(best_s - BIRTH_GEO_MIN_STOP_PCT) < 1e-12

    econ_mismatch = bool(best_be > be_target + 1e-12)
    if econ_mismatch:
        logger.info(
            "birth.geometry.econ_proxy_mismatch be_wr=%.3f target=%.3f net_rr=%.3f "
            "(35%% WR proxy is not dollar-+EV at this plant — floors unchanged)",
            best_be,
            be_target,
            best_rr,
        )
    return best_s, best_t, out_source, floor_bound, best_rr, best_be, cost, econ_mismatch


def _finalize_geometry(
    stop: float,
    target: float,
    *,
    source: str,
    time_ordered: bool,
    hold: int,
    pool_size: int,
    macro_rejected: bool = False,
    p40_raw: float = 0.0,
    price: float = 7500.0,
    atr_med: float | None = None,
    p50: float | None = None,
    apply_cost: bool = True,
) -> BirthTradeGeometry:
    s, t = clamp_birth_geometry(stop, target)
    floor_bound = abs(s - BIRTH_GEO_MIN_STOP_PCT) < 1e-12
    net_rr = be_wr = cost = 0.0
    econ_mismatch = False
    out_source = source
    if apply_cost:
        s, t, out_source, floor_bound, net_rr, be_wr, cost, econ_mismatch = _apply_cost_viability(
            s,
            t,
            price=price,
            atr_med=atr_med,
            p50=p50,
            source=source,
        )
    else:
        _, _, net_rr, be_wr, cost = economics_after_cost(s, t, price=price)
        econ_mismatch = bool(be_wr > float(TARGET_BE_WR_AFTER_COST) + 1e-12)
    return BirthTradeGeometry(
        stop_pct=float(s),
        target_pct=float(t),
        source=out_source,
        time_ordered=time_ordered,
        p40_raw=float(p40_raw),
        hold_bars=int(hold),
        pool_size=int(pool_size),
        macro_rejected=bool(macro_rejected),
        floor_bound=bool(floor_bound),
        net_rr_after_cost=float(net_rr),
        breakeven_wr_after_cost=float(be_wr),
        cost_usd=float(cost),
        ref_price=float(price),
        econ_proxy_mismatch=bool(econ_mismatch),
    )


def _geometry_from_atr(
    atr_samples: list[float],
    *,
    source: str,
    time_ordered: bool,
    hold: int,
    pool_size: int,
    macro_rejected: bool = False,
    p40_raw: float = 0.0,
    price: float = 7500.0,
) -> BirthTradeGeometry:
    atr_med = float(np.median(np.asarray(atr_samples, dtype=float)))
    stop = max(BIRTH_GEO_MIN_STOP_PCT, min(_PEAK_STOP_CAP, atr_med * 0.9))
    target = max(stop * 1.25, min(_PEAK_TARGET_CAP, atr_med * 1.5))
    return _finalize_geometry(
        stop,
        target,
        source=source,
        time_ordered=time_ordered,
        hold=hold,
        pool_size=pool_size,
        macro_rejected=macro_rejected,
        p40_raw=p40_raw,
        price=price,
        atr_med=atr_med,
        p50=None,
    )


def _fallback_geometry(
    *,
    source: str,
    time_ordered: bool = True,
    hold: int = 0,
    pool_size: int = 0,
    macro_rejected: bool = False,
    p40_raw: float = 0.0,
    price: float = 7500.0,
) -> BirthTradeGeometry:
    return _finalize_geometry(
        BIRTH_FALLBACK_STOP_PCT,
        BIRTH_FALLBACK_TARGET_PCT,
        source=source,
        time_ordered=time_ordered,
        hold=hold,
        pool_size=pool_size,
        macro_rejected=macro_rejected,
        p40_raw=p40_raw,
        price=price,
        atr_med=None,
        p50=None,
    )


def _collect_atr_samples(pool: list[dict[str, Any]], *, stride: int) -> list[float]:
    atr_samples: list[float] = []
    for i in range(0, len(pool), max(1, stride)):
        entry = _tick_price(pool[i])
        atr = float(pool[i].get("trend_atr_norm", 0.0) or 0.0)
        if atr > 0:
            if entry > 0 and atr >= 0.05:
                atr = atr / entry
            atr_samples.append(min(0.02, max(0.0003, atr)))
    return atr_samples


def _median_bar_seconds(pool: list[dict[str, Any]]) -> float:
    deltas: list[float] = []
    for a, b in zip(pool, pool[1:]):
        if bool(b.get(SEGMENT_BREAK_KEY)):
            continue
        ta, tb = _timestamp_key(a), _timestamp_key(b)
        if ta is None or tb is None:
            continue
        d = float(tb - ta)
        if 0.0 < d < 86_400.0:
            deltas.append(d)
    if len(deltas) < 5:
        return 60.0
    return float(np.median(np.asarray(deltas, dtype=float)))


def _crosses_segment_gap(
    prev: dict[str, Any],
    curr: dict[str, Any],
    *,
    max_gap_sec: float,
) -> bool:
    if bool(curr.get(SEGMENT_BREAK_KEY)):
        return True
    sid0, sid1 = prev.get(SEGMENT_ID_KEY), curr.get(SEGMENT_ID_KEY)
    if sid0 is not None and sid1 is not None and sid0 != sid1:
        return True
    ta, tb = _timestamp_key(prev), _timestamp_key(curr)
    if ta is not None and tb is not None:
        gap = float(tb - ta)
        if gap < 0 or gap > max_gap_sec:
            return True
    bi0, bi1 = _bar_index(prev), _bar_index(curr)
    if bi0 is not None and bi1 is not None:
        if bi1 + 1e-9 < bi0:
            return True
        if ta is None and tb is None and (bi1 - bi0) > 50:
            return True
    return False


def _peak_moves_gap_aware(
    pool: list[dict[str, Any]],
    *,
    hold: int,
    stride: int,
) -> list[float]:
    max_gap = max(_GAP_MIN_SEC, _median_bar_seconds(pool) * _GAP_MEDIAN_MULT)
    abs_moves: list[float] = []
    pool_size = len(pool)
    end = pool_size - hold - 1
    for i in range(20, max(21, end), max(1, stride)):
        entry = _tick_price(pool[i])
        if entry <= 0:
            continue
        peak = 0.0
        for j in range(i + 1, min(pool_size, i + hold + 1)):
            if _crosses_segment_gap(pool[j - 1], pool[j], max_gap_sec=max_gap):
                break
            price = _tick_price(pool[j])
            if price <= 0:
                continue
            peak = max(peak, abs(price - entry) / entry)
        if peak > 0:
            abs_moves.append(peak)
    return abs_moves


def calibrate_birth_stops(
    ticks: list[dict[str, Any]] | None,
    *,
    max_hold_bars: int = 90,
    sample_stride: int = 10,
) -> BirthTradeGeometry:
    """Derive stop/target from realized move distribution (fail-closed + cost-aware)."""
    pool = list(ticks or [])
    pool_size = len(pool)
    hold = max(20, int(max_hold_bars))
    price = median_tick_price(pool)
    if pool_size < 40:
        return _fallback_geometry(
            source="fallback_thin",
            time_ordered=True,
            hold=hold,
            pool_size=pool_size,
            price=price,
        )

    ordered = is_time_ordered(pool)
    stride = max(1, int(sample_stride))
    atr_samples = _collect_atr_samples(pool, stride=stride)
    atr_med = float(np.median(np.asarray(atr_samples, dtype=float))) if atr_samples else None

    if not ordered:
        logger.warning(
            "birth.geometry.poison_shuffle_detected pool=%s hold=%s — refusing peak-move "
            "on disordered pool (use ATR/fallback micro)",
            pool_size,
            hold,
        )
        if atr_samples:
            return _geometry_from_atr(
                atr_samples,
                source="atr_median_disordered",
                time_ordered=False,
                hold=hold,
                pool_size=pool_size,
                macro_rejected=True,
                price=price,
            )
        return _fallback_geometry(
            source="fallback_disordered_pool",
            time_ordered=False,
            hold=hold,
            pool_size=pool_size,
            macro_rejected=True,
            price=price,
        )

    abs_moves = _peak_moves_gap_aware(pool, hold=hold, stride=stride)

    if not abs_moves and not atr_samples:
        return _fallback_geometry(
            source="fallback_empty",
            time_ordered=True,
            hold=hold,
            pool_size=pool_size,
            price=price,
        )

    if abs_moves:
        arr = np.asarray(abs_moves, dtype=float)
        p40 = float(np.percentile(arr, 40))
        p50 = float(np.percentile(arr, 50))
        p60 = float(np.percentile(arr, 60))
        stop = max(BIRTH_GEO_MIN_STOP_PCT, min(_PEAK_STOP_CAP, p40 * 0.85))
        target = max(stop * 1.25, min(_PEAK_TARGET_CAP, p60 * 1.05))
        if stop >= MACRO_STOP_THRESHOLD and atr_samples:
            atr_m = float(np.median(np.asarray(atr_samples, dtype=float)))
            if atr_m > 0 and atr_m * 3.0 < stop:
                logger.warning(
                    "birth.geometry.macro_vs_atr peak_stop=%.5f atr_med=%.5f — prefer ATR",
                    stop,
                    atr_m,
                )
                return _geometry_from_atr(
                    atr_samples,
                    source="atr_median_macro_guard",
                    time_ordered=True,
                    hold=hold,
                    pool_size=pool_size,
                    macro_rejected=True,
                    p40_raw=p40,
                    price=price,
                )
        return _finalize_geometry(
            stop,
            target,
            source="move_distribution",
            time_ordered=True,
            hold=hold,
            pool_size=pool_size,
            macro_rejected=False,
            p40_raw=p40,
            price=price,
            atr_med=atr_med,
            p50=p50,
        )

    return _geometry_from_atr(
        atr_samples,
        source="atr_median",
        time_ordered=True,
        hold=hold,
        pool_size=pool_size,
        price=price,
    )


def calibrate_oracle_stops(
    ticks: list[dict[str, Any]],
    *,
    max_hold_bars: int = 90,
    sample_stride: int = 10,
) -> tuple[float, float]:
    """API-compat for pattern miner / callers expecting a 2-tuple."""
    geo = calibrate_birth_stops(
        ticks, max_hold_bars=max_hold_bars, sample_stride=sample_stride
    )
    return geo.stop_pct, geo.target_pct


def first_touch_target_hit_rate(
    ticks: list[dict[str, Any]] | None,
    *,
    stop_pct: float,
    target_pct: float,
    max_hold_bars: int = 90,
    sample_stride: int = 25,
) -> float:
    """Random long/short first-touch target rate among decisive exits (truthful baseline)."""
    pool = list(ticks or [])
    hold = max(20, int(max_hold_bars))
    if len(pool) < hold + 40:
        return 0.0
    stop = max(1e-9, float(stop_pct))
    target = max(stop * 1.01, float(target_pct))
    stride = max(5, int(sample_stride))
    stops = targets = 0
    for i in range(20, len(pool) - hold - 1, stride):
        entry = _tick_price(pool[i])
        if entry <= 0:
            continue
        for side in (1.0, -1.0):
            outcome = "timeout"
            for j in range(i + 1, i + hold + 1):
                price = _tick_price(pool[j])
                if price <= 0:
                    continue
                ret = (price - entry) / entry * side
                if ret <= -stop:
                    outcome = "stop"
                    break
                if ret >= target:
                    outcome = "target"
                    break
            if outcome == "stop":
                stops += 1
            elif outcome == "target":
                targets += 1
    dec = stops + targets
    if dec <= 0:
        return 0.0
    return float(targets) / float(dec)


def soft_prior_action_stops(
    stop_pct: float,
    target_pct: float,
    *,
    geometry: BirthTradeGeometry,
    max_multiple: float = SOFT_PRIOR_DEFAULT_MULTIPLE,
) -> tuple[float, float]:
    """Pull grossly mis-scaled policy stops toward calibrated birth geometry."""
    cal_s = float(geometry.stop_pct)
    cal_t = float(geometry.target_pct)
    mult = max(1.5, float(max_multiple))
    stop = float(stop_pct)
    target = float(target_pct)
    if stop > cal_s * mult:
        stop = cal_s * min(mult, stop / max(cal_s, 1e-9))
        stop = min(stop, cal_s * mult)
    if stop < cal_s / mult:
        stop = max(cal_s / mult, stop)
    min_t = stop * 1.25
    if target < min_t:
        target = min_t
    if target > cal_t * mult * 1.5:
        target = cal_t * mult
    return clamp_birth_geometry(stop, target)


def geometry_action(
    side: float,
    qty_frac: float,
    geometry: BirthTradeGeometry,
) -> "np.ndarray":
    """Build a 4-dim action with calibrated stop/target."""
    s, t = geometry.as_action_tail()
    return np.array([float(side), float(qty_frac), float(s), float(t)], dtype=np.float32)


_GEOMETRY_PASS_KEYS = frozenset({"geometry_net_rr", "geometry_net_rr_after_cost"})


def geometry_forensics_fields(geometry: BirthTradeGeometry | None) -> dict[str, Any]:
    """Progress/scorecard keys for geometry truth (always safe scalars)."""
    if geometry is None:
        return {
            "geometry_time_ordered": False,
            "geometry_p40_raw": 0.0,
            "geometry_hold_bars": 0,
            "geometry_pool_size": 0,
            "geometry_macro_rejected": False,
            "geometry_floor_bound": False,
            "geometry_breakeven_wr_after_cost": 0.0,
            "geometry_cost_usd": 0.0,
            "geometry_ref_price": 0.0,
            "geometry_econ_proxy_mismatch": False,
        }
    return {
        "geometry_time_ordered": bool(geometry.time_ordered),
        "geometry_p40_raw": round(float(geometry.p40_raw), 8),
        "geometry_hold_bars": int(geometry.hold_bars),
        "geometry_pool_size": int(geometry.pool_size),
        "geometry_macro_rejected": bool(geometry.macro_rejected),
        "geometry_floor_bound": bool(geometry.floor_bound),
        "geometry_net_rr": round(float(geometry.net_rr_after_cost), 4),
        "geometry_net_rr_after_cost": round(float(geometry.net_rr_after_cost), 4),
        "geometry_breakeven_wr_after_cost": round(float(geometry.breakeven_wr_after_cost), 4),
        "geometry_cost_usd": round(float(geometry.cost_usd), 4),
        "geometry_ref_price": round(float(geometry.ref_price), 2),
        "geometry_econ_proxy_mismatch": bool(getattr(geometry, "econ_proxy_mismatch", False)),
    }


def apply_geometry_forensics(
    payload: dict[str, Any],
    geometry: BirthTradeGeometry | None,
) -> None:
    """Merge forensics without clobbering FoundationSnapshot net RR."""
    fields = geometry_forensics_fields(geometry)
    for key, value in fields.items():
        if key in _GEOMETRY_PASS_KEYS:
            if payload.get(key) is not None:
                continue
            if geometry is None:
                continue
        payload[key] = value


__all__ = [
    "BIRTH_FALLBACK_STOP_PCT",
    "BIRTH_FALLBACK_TARGET_PCT",
    "BIRTH_MAX_STOP_PCT",
    "BIRTH_MAX_TARGET_PCT",
    "BIRTH_GEO_MIN_STOP_PCT",
    "LEGACY_MACRO_STOP_PCT",
    "LEGACY_MACRO_TARGET_PCT",
    "MACRO_STOP_THRESHOLD",
    "MIN_NET_RR_AFTER_COST",
    "TARGET_BE_WR_AFTER_COST",
    "economic_skill_gap",
    "SEGMENT_BREAK_KEY",
    "SEGMENT_ID_KEY",
    "SOFT_PRIOR_DEFAULT_MULTIPLE",
    "BirthTradeGeometry",
    "calibrate_birth_stops",
    "calibrate_oracle_stops",
    "clamp_birth_geometry",
    "economics_after_cost",
    "estimate_round_trip_cost_usd",
    "first_touch_target_hit_rate",
    "geometry_action",
    "apply_geometry_forensics",
    "geometry_forensics_fields",
    "is_time_ordered",
    "median_tick_price",
    "soft_prior_action_stops",
]
