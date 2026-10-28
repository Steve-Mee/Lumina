"""G2: ONE fix matching G1 cause. FIX_KIND equals cause. No oracle regime stamp."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from lumina_core.birth.awakening_coupling_diagnose import (
    BASELINE_SHA256,
    DIAGNOSE_SEED,
    ENR_THRESHOLD_NEG,
    ENR_THRESHOLD_POS,
    EXAM_SEED,
    FORBIDDEN_TAPE_PREFIXES,
    MIN_HOLDOUT_TICKS,
    MIN_TICKS_PER_LEG,
    CouplingProtocolError,
    attempt2_spec,
    phase_label,
)
from lumina_core.birth.awakening_physics_tape import (
    PHYSICS_DAYS,
    PHYSICS_ETH_SEC,
    PHYSICS_HOLD_PCT,
    PHYSICS_RTH_SEC,
    count_regimes_post_enrich,
    intended_for_price,
    trend_fracs,
    world_ok_fracs,
)
from lumina_core.birth.data_source_honesty import host_real_data_pct, real_data_percentage
from lumina_core.birth.genesis_cloud_const import GENESIS_INSTRUMENT, GENESIS_START_PRICE
from lumina_core.birth.genesis_mark_eyes_eval import split_holdout_ab
from lumina_core.birth.synthetic_cloud_fixture import (
    NQ_TICK_SIZE,
    SOURCE_LABEL,
    CloudFixtureSpec,
    _iter_session_times,
    _is_rth,
    _round_tick,
)
from lumina_core.birth.synthetic_cloud_fixture_persist import persist_cloud_fixture, write_fixture_sidecar
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim

ET = ZoneInfo("America/New_York")
EXAM_START_ET = datetime(2026, 3, 2, 18, 0, tzinfo=ET)
FIX_KIND = ""  # FIX_KIND equals cause
PHYSICS_FLOOR = 1_000.0


class NotUsed(RuntimeError):
    """Branch exists only as an explicit raise — not a live fallback."""


def bind_fix_kind(cause: str) -> str:
    """FIX_KIND equals cause."""
    global FIX_KIND
    FIX_KIND = str(cause)
    return FIX_KIND


def refuse_this_tape_hash(sha: str) -> str:
    text = str(sha or "").strip().lower()
    if text.startswith(FORBIDDEN_TAPE_PREFIXES):
        raise CouplingProtocolError(f"refused old tape hash {text[:16]} as THIS exam tape")
    return text


def refuse_oracle_regime(_tick: dict[str, Any], _gen_phase: str) -> None:
    # no post-enrich oracle regime assign
    raise CouplingProtocolError("forbidden: tick['regime'] from generator after enrich")


def symmetrize_physics_drift(drift_up: float, drift_down: float) -> tuple[float, float]:
    mag = max(abs(float(drift_up)), abs(float(drift_down)))
    return mag, mag


def apply_gen_asym_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    if FIX_KIND != "GEN_ASYM":
        raise NotUsed("GEN_ASYM")
    up, down = symmetrize_physics_drift(float(kwargs["drift_rth"]), float(kwargs["drift_down_rth"]))
    out = dict(kwargs)
    out["drift_rth"] = up
    out["drift_down_rth"] = down
    return out


def apply_floor_clip_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    if FIX_KIND != "FLOOR_CLIP":
        raise NotUsed("FLOOR_CLIP")
    out = dict(kwargs)
    out["start_price"] = float(GENESIS_START_PRICE) * 2.0
    out["floor_price"] = float(NQ_TICK_SIZE)
    out["bounce"] = False
    return out


def enr_asym_thresholds(mean_slope_up: float, mean_slope_down: float) -> tuple[float, float]:
    mag_up = max(abs(float(mean_slope_up)), 1e-9)
    mag_down = max(abs(float(mean_slope_down)), 1e-9)
    pos = float(ENR_THRESHOLD_POS)
    neg = -abs(pos) * (mag_up / mag_down)
    return pos, float(neg)


def apply_enr_asym_wrapper(
    ticks: list[dict[str, Any]], *, threshold_pos: float, threshold_neg: float
) -> list[dict[str, Any]]:
    if FIX_KIND != "ENR_ASYM":
        raise NotUsed("ENR_ASYM")
    out = enrich_ticks_for_sim([dict(t) for t in ticks])
    for tick in out:
        strength = float(tick.get("trend_regime_strength") or 0.0)
        if strength > float(threshold_pos):
            tick["regime"] = "TREND_UP"
        elif strength < float(threshold_neg):
            tick["regime"] = "TREND_DOWN"
        else:
            tick["regime"] = "NEUTRAL"
    return out


def exam_base_kwargs() -> dict[str, Any]:
    spec = attempt2_spec()
    return {
        "seed": int(EXAM_SEED),
        "start_et": EXAM_START_ET,
        "start_price": float(GENESIS_START_PRICE),
        "drift_rth": float(spec.drift_rth),
        "drift_eth": float(spec.drift_eth),
        "drift_down_rth": float(spec.drift_rth),
        "range_kappa": float(spec.range_kappa),
        "phase_blocks": int(spec.phase_blocks),
        "shock": float(spec.shock),
        "floor_price": float(PHYSICS_FLOOR),
        "bounce": True,
        "days": int(PHYSICS_DAYS),
        "rth_sec": int(PHYSICS_RTH_SEC),
        "eth_sec": int(PHYSICS_ETH_SEC),
    }


def generate_exam_raw_ticks(kwargs: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    stamps = _iter_session_times(
        start_et=kwargs["start_et"],
        calendar_days=int(kwargs["days"]),
        rth_bar_seconds=int(kwargs["rth_sec"]),
        eth_bar_seconds=int(kwargs["eth_sec"]),
    )
    rng = np.random.default_rng(int(kwargs["seed"]))
    n = len(stamps)
    price = float(kwargs["start_price"])
    floor_px = float(kwargs["floor_price"])
    bounce = bool(kwargs["bounce"])
    ewma_var = (0.00018) ** 2
    session_anchor = price
    last_et_date = stamps[0].date()
    ticks: list[dict[str, Any]] = []
    phases: list[str] = []
    prev_ts_utc: datetime | None = None
    for i, ts_et in enumerate(stamps):
        if ts_et.date() != last_et_date:
            nxt = price * (1.0 + float(rng.standard_t(5) * 0.003))
            price = max(floor_px, nxt) if bounce else max(NQ_TICK_SIZE, nxt)
            session_anchor = price
            last_et_date = ts_et.date()
            ewma_var = min(ewma_var * 1.4, 4e-7)
        rth = _is_rth(ts_et)
        minutes = ts_et.hour * 60 + ts_et.minute
        near_open = rth and (9 * 60 + 30) <= minutes < (9 * 60 + 40)
        near_close = rth and (15 * 60 + 50) <= minutes < (16 * 60)
        intended = intended_for_price(i, n, int(kwargs["phase_blocks"]))
        shock = float(rng.standard_t(5))
        ewma_var = 0.94 * ewma_var + 0.06 * (shock * float(kwargs["shock"])) ** 2
        sigma = math.sqrt(max(ewma_var, 1e-10))
        if not rth:
            sigma *= 0.55
        if near_open:
            sigma *= 1.8
        drift = float(kwargs["drift_rth"] if rth else kwargs["drift_eth"])
        if intended == "TREND_UP":
            ret = drift + sigma * shock
        elif intended == "TREND_DOWN":
            ret = -float(kwargs["drift_down_rth"] if rth else kwargs["drift_eth"]) + sigma * shock
        else:
            ret = -float(kwargs["range_kappa"]) * math.log(max(price, 1.0) / max(session_anchor, 1.0)) + sigma * shock
        raw_px = _round_tick(price * (1.0 + ret))
        price = max(floor_px, raw_px) if bounce else max(NQ_TICK_SIZE, raw_px)
        half = max(NQ_TICK_SIZE, abs(shock) * sigma * price * 8.0)
        high, low = _round_tick(price + half), _round_tick(max(NQ_TICK_SIZE, price - half))
        burst = near_open or (sigma > 0.0004)
        volume = int(rng.integers(400, 2_400) if rth else rng.integers(40, 280))
        if rth and burst:
            volume = int(rng.integers(4_000, 16_000))
        spread_ticks = 4.0 if (near_open or near_close) else (3.0 if burst else (1.0 if rth else 2.0))
        spread = spread_ticks * NQ_TICK_SIZE
        bid, ask = _round_tick(price - spread / 2.0), _round_tick(price + spread / 2.0)
        if ask <= bid:
            ask = bid + NQ_TICK_SIZE
        ts_utc = ts_et.astimezone(timezone.utc)
        if prev_ts_utc is not None and ts_utc <= prev_ts_utc:
            ts_utc = prev_ts_utc + timedelta(milliseconds=1)
        prev_ts_utc = ts_utc
        ticks.append(
            {
                "timestamp": ts_utc.isoformat(),
                "last": float(price),
                "close": float(price),
                "open": float(price),
                "high": float(high),
                "low": float(low),
                "bid": float(bid),
                "ask": float(ask),
                "volume": int(volume),
                "imbalance": 1.0,
                "source": SOURCE_LABEL,
                "instrument": GENESIS_INSTRUMENT,
                "session": "RTH" if rth else "ETH",
            }
        )
        phases.append(phase_label(intended))
    if any("regime" in row for row in ticks):
        raise CouplingProtocolError("exam generator must not write tick['regime']")
    return ticks, phases


def persist_coupling_exam(
    work: Path,
    art: Path,
    *,
    cause: str,
    g1_numbers: dict[str, Any],
) -> dict[str, Any]:
    bind_fix_kind(cause)
    kwargs = exam_base_kwargs()
    thr_pos, thr_neg = float(ENR_THRESHOLD_POS), float(ENR_THRESHOLD_NEG)
    enrich_custom = False
    if cause == "OTHER":
        raise CouplingProtocolError("OTHER skips G3")
    if cause == "GEN_ASYM":
        kwargs = apply_gen_asym_kwargs(kwargs)
    elif cause == "FLOOR_CLIP":
        kwargs = apply_floor_clip_kwargs(kwargs)
    elif cause == "ENR_ASYM":
        thr_pos, thr_neg = enr_asym_thresholds(
            float(g1_numbers.get("mean_slope_emitted_up") or 0.0),
            float(g1_numbers.get("mean_slope_emitted_down") or 0.0),
        )
        enrich_custom = True
    else:
        raise CouplingProtocolError(f"unknown cause {cause}")
    raw, _phases = generate_exam_raw_ticks(kwargs)
    spec = CloudFixtureSpec(
        instrument=GENESIS_INSTRUMENT,
        calendar_days=int(kwargs["days"]),
        holdout_pct=float(PHYSICS_HOLD_PCT),
        start_price=float(kwargs["start_price"]),
        seed=int(kwargs["seed"]),
        start_et=kwargs["start_et"],
        rth_bar_seconds=int(kwargs["rth_sec"]),
        eth_bar_seconds=int(kwargs["eth_sec"]),
    )
    if enrich_custom:
        enriched = apply_enr_asym_wrapper(raw, threshold_pos=thr_pos, threshold_neg=thr_neg)
        result = persist_cloud_fixture(work, spec=spec, ticks=enriched, enrich=False)
    else:
        result = persist_cloud_fixture(work, spec=spec, ticks=raw, enrich=True)
    train = list(result.split.train)
    holdout = list(result.split.holdout)
    tr_c, ho_c = count_regimes_post_enrich(train), count_regimes_post_enrich(holdout)
    train_up, train_down = trend_fracs(tr_c)
    hold_up, hold_down = trend_fracs(ho_c)
    world_ok = world_ok_fracs(train_up=train_up, train_down=train_down, hold_up=hold_up, hold_down=hold_down)
    payload = dict(result.fixture_manifest)
    payload.update(
        {
            "real_data_pct": float(real_data_percentage(result.ticks)),
            "host_real_data_pct": float(host_real_data_pct(result.ticks, certified_cache=True)),
            "fixture_seed": int(EXAM_SEED),
            "diagnose_seed": int(DIAGNOSE_SEED),
            "start_et": EXAM_START_ET.isoformat(),
            "source": SOURCE_LABEL,
            "train_regime_counts": tr_c,
            "holdout_regime_counts": ho_c,
            "trend_up_frac_train": float(train_up),
            "trend_down_frac_train": float(train_down),
            "trend_up_frac_holdout": float(hold_up),
            "trend_down_frac_holdout": float(hold_down),
            "ticks_per_leg": [len(x) for x in split_holdout_ab(holdout)],
            "world_ok": bool(world_ok),
            "fix_kind": str(FIX_KIND),
            "enr_threshold_pos": float(thr_pos),
            "enr_threshold_neg": float(thr_neg),
            "baseline_sha256": BASELINE_SHA256,
        }
    )
    refuse_this_tape_hash(str(payload.get("hash") or ""))
    if float(payload.get("real_data_pct") or 0.0) != 0.0:
        raise CouplingProtocolError("real_data_percentage must be 0.0")
    if str(payload.get("source")) != SOURCE_LABEL:
        raise CouplingProtocolError("source must stay synthetic_cloud_fixture")
    if int(payload.get("holdout_tick_count") or 0) < MIN_HOLDOUT_TICKS:
        raise CouplingProtocolError("holdout < 80k")
    legs = list(payload.get("ticks_per_leg") or [])
    if len(legs) != 2 or int(legs[0]) < MIN_TICKS_PER_LEG or int(legs[1]) < MIN_TICKS_PER_LEG:
        raise CouplingProtocolError("each chronological half must be >= 40000")
    sidecar = art / "01_coupling_fixture_manifest.json"
    write_fixture_sidecar(sidecar, payload)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


__all__ = [
    "FIX_KIND",
    "NotUsed",
    "bind_fix_kind",
    "persist_coupling_exam",
    "refuse_oracle_regime",
]
