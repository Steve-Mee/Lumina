"""G1: NEW #44-physics tape. Seed 20260913. Isolated enrich 0.12. Split imported."""

from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from lumina_core.birth.awakening_conv_enrich import (
    PHYSICS_SLOPE_ABS,
    PROD_SLOPE_ABS,
    enrich_ticks_for_conv,
)
from lumina_core.birth.awakening_mark_eyes import MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_occupancy_tape import (
    OCCUPANCY_DRIFT_RTH,
    OCCUPANCY_RANGE_KAPPA,
    _SHOCK,
    _ret,
    assert_gen_counts_balanced,
    count_generator_labels,
    count_regimes_post_enrich,
    generator_labels,
    trend_fracs,
    world_ok_fracs,
    write_bytes_sha,
)
from lumina_core.birth.awakening_strat_split import (  # per-phase 60/40 import
    SPLITTER_NAME,
    STRAT_HOLD_PCT,
    split_per_phase_60_40,
)
from lumina_core.birth.birth_exit_policy_export import is_gitignored_ppo_zip
from lumina_core.birth.data_source_honesty import host_real_data_pct, real_data_percentage
from lumina_core.birth.foundation_history import FOUNDATION_HISTORY_START_DAYS
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import GENESIS_ART, GENESIS_INSTRUMENT, GENESIS_START_PRICE, REPO_ROOT
from lumina_core.birth.genesis_mark_eyes_eval import split_holdout_ab
from lumina_core.birth.history_loader import actual_calendar_days_from_ticks
from lumina_core.birth.purged_split import PurgedSplit
from lumina_core.birth.synthetic_cloud_fixture import (
    NQ_TICK_SIZE,
    SOURCE_LABEL,
    write_fixture_sidecar,
    _iter_session_times,
    _is_rth,
    _round_tick,
)
from lumina_core.birth.tick_cache_persist import (
    compute_ticks_fingerprint,
    load_cache_manifest,
    load_split_cache,
    save_birth_data_cache,
)
from lumina_core.rl.trend_features import ENRICH_VERSION

ET = ZoneInfo("America/New_York")
OBJ_SEED = 20260913  # seed 20260913
OBJ_START_ET = datetime(2025, 11, 3, 18, 0, tzinfo=ET)
OBJ_START_ET_ISO = OBJ_START_ET.isoformat()
OBJ_DAYS = 90
OBJ_RTH_SEC = 10
OBJ_ETH_SEC = 60
OBJ_DRIFT_RTH = 0.00024
OBJ_RANGE_KAPPA = 0.01
OBJ_PHASE_BLOCKS = 6
OBJ_TIMESTEPS = 10_000
TRAIN_SEED = 20260913
MIN_TREND_UP_FRAC = 0.25
MIN_TREND_DOWN_FRAC = 0.25
MIN_HOLDOUT_TICKS = 80_000
MIN_TICKS_PER_LEG = 40_000
BASELINE_SHA256 = "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b"
ORIGIN_EYES_ZIP = GENESIS_ART / "genesis_mark_eyes_pi_star.zip"
BASELINE_ZIP_NAME = "baseline_a9ffa852_pi_star.zip"
CHILD_ZIP_NAME = "awakening_obj_v1_pi_star.zip"
CHILD_META_NAME = "awakening_obj_v1_pi_star.json"
CHILD_SCHEMA = "awakening_obj_v1_pi_star_v1"
FLAGS_NAME = "awakening_obj_flags.json"
OBJ_ROOT = REPO_ROOT / "reports" / "awakening_obj_run"
OBJ_WORK, OBJ_ART = OBJ_ROOT / "workspace", OBJ_ROOT / "artifacts"
FORBIDDEN_TAPE_PREFIXES = (
    "5726ae7e",
    "e963d1ce",
    "afcea4fa",
    "5e7eae98",
    "8d1aa6f8",
    "9b66a162",
    "7923fa61",
    "b1f16c99",
    "7e86c2bb",
)
FORBIDDEN_INIT_SHA16 = frozenset(
    {"a9ffa852", "a8a93d6e", "cebe1804", "1123282f", "8cc435c6", "d313b107", "53df2d78"}
)
FORBIDDEN_INIT_NAMES = frozenset(
    {
        "genesis_mark_eyes_pi_star.zip",
        "baseline_a9ffa852_pi_star.zip",
        "baseline_mark_eyes_v1_pi_star.zip",
        "awakening_mark_eyes_polish_pi_star.zip",
        "awakening_mark_eyes_v2_pi_star.zip",
        "init_mark_eyes_pi_star.zip",
        "birth_exit_pi_star.zip",
        "genesis_birth_exit_pi_star.zip",
        "awakening_mark_eyes_pi_star.zip",
        "awakening_occupancy_v1_pi_star.zip",
        "awakening_strat_v1_pi_star.zip",
        "awakening_conv_v1_pi_star.zip",
    }
)
assert POLICY_EDGE_MIN_TRADES == 150 and MARK_EYES_OBS_DIM == 46
assert OBJ_DRIFT_RTH == 0.00024 == OCCUPANCY_DRIFT_RTH
assert OBJ_RANGE_KAPPA == 0.01 == OCCUPANCY_RANGE_KAPPA
assert OBJ_PHASE_BLOCKS == 6 and OBJ_SEED == 20260913
assert MIN_TREND_UP_FRAC == 0.25 and MIN_TREND_DOWN_FRAC == 0.25
assert PHYSICS_SLOPE_ABS == 0.12 and PROD_SLOPE_ABS == 0.15  # slope 0.12 isolated, prod 0.15
assert BASELINE_SHA256.startswith("a9ffa852")


class ObjProtocolError(RuntimeError):
    """AWAKENING_OBJECTIVE_TRADE protocol crime (fail-closed)."""


def refuse_this_tape_hash(sha: str) -> str:
    text = str(sha or "").strip().lower()
    if text.startswith(FORBIDDEN_TAPE_PREFIXES):
        raise ObjProtocolError(f"refused old tape hash {text[:16]} as THIS exam tape")
    return text


def assert_forbidden_init(path: Path | str, sha: str = "") -> Path:
    target = Path(path)
    text = str(sha or "").strip().lower()
    posix = str(target).replace("\\", "/")
    if text[:8] in FORBIDDEN_INIT_SHA16:
        raise ObjProtocolError(f"refused forbidden init sha {text[:8]}")
    if target.name in FORBIDDEN_INIT_NAMES or is_gitignored_ppo_zip(target) or "/lumina_agents/ppo/" in f"/{posix}":
        raise ObjProtocolError(f"refused forbidden init {target.name}")
    return target


def generate_obj_tape_ticks() -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    stamps = _iter_session_times(
        start_et=OBJ_START_ET,
        calendar_days=OBJ_DAYS,
        rth_bar_seconds=OBJ_RTH_SEC,
        eth_bar_seconds=OBJ_ETH_SEC,
    )
    if len(stamps) < 1_000:
        raise ObjProtocolError(f"obj fixture too thin: {len(stamps)}")
    rng = np.random.default_rng(OBJ_SEED)
    labels = generator_labels(len(stamps), OBJ_PHASE_BLOCKS)
    gen_counts = assert_gen_counts_balanced(count_generator_labels(labels))
    price = float(GENESIS_START_PRICE)
    ewma_var = (0.00018) ** 2
    session_anchor = price
    last_et_date = stamps[0].date()
    ticks: list[dict[str, Any]] = []
    prev_ts_utc: datetime | None = None
    # no oracle — price must earn TREND_* via isolated wrapper
    for i, ts_et in enumerate(stamps):
        if ts_et.date() != last_et_date:
            price = max(1_000.0, price * (1.0 + float(rng.standard_t(5) * 0.003)))
            session_anchor, last_et_date, ewma_var = price, ts_et.date(), min(ewma_var * 1.4, 4e-7)
        rth = _is_rth(ts_et)
        minutes = ts_et.hour * 60 + ts_et.minute
        near_open = rth and (9 * 60 + 30) <= minutes < (9 * 60 + 40)
        shock = float(rng.standard_t(5))
        ewma_var = 0.94 * ewma_var + 0.06 * (shock * _SHOCK) ** 2
        sigma = math.sqrt(max(ewma_var, 1e-10)) * (1.8 if near_open else 1.0) * (1.0 if rth else 0.55)
        price = max(1_000.0, _round_tick(price * (1.0 + _ret(labels[i], rth, price, session_anchor, sigma, shock))))
        half = max(NQ_TICK_SIZE, abs(shock) * sigma * price * 8.0)
        burst = near_open or (sigma > 0.0004)
        volume = int(rng.integers(4_000, 16_000) if rth and burst else rng.integers(400, 2_400) if rth else rng.integers(40, 280))
        near_close = rth and (15 * 60 + 50) <= minutes < (16 * 60)
        spread = (4.0 if (near_open or near_close) else (3.0 if burst else (1.0 if rth else 2.0))) * NQ_TICK_SIZE
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
                "high": float(_round_tick(price + half)),
                "low": float(_round_tick(max(NQ_TICK_SIZE, price - half))),
                "bid": float(bid),
                "ask": float(ask),
                "volume": int(volume),
                "imbalance": 1.0,
                "source": SOURCE_LABEL,
                "instrument": GENESIS_INSTRUMENT,
                "session": "RTH" if rth else "ETH",
            }
        )
    if any("regime" in row or "gen_phase" in row for row in ticks):
        raise ObjProtocolError("no oracle")
    return ticks, labels, gen_counts


def _unique_days(ticks: list[dict[str, Any]]) -> int:
    return len({str(row.get("timestamp") or "")[:10] for row in ticks})


def persist_obj_fixture(work: Path, art: Path) -> dict[str, Any]:
    raw, phases, gen_counts = generate_obj_tape_ticks()
    cache = work / "state" / "birth_enrichment_cache"
    if cache.is_dir():
        shutil.rmtree(cache)
    raw_hash = compute_ticks_fingerprint(raw)
    enriched = enrich_ticks_for_conv(
        [dict(t) for t in raw],
        workspace_root=work,
        raw_ticks_hash=raw_hash,
        enrich_version=ENRICH_VERSION,
    )
    for row in enriched:
        row["source"] = SOURCE_LABEL
        row.pop("gen_phase", None)
    if any("gen_phase" in row for row in enriched):
        raise ObjProtocolError("generator phase side-channel must be stripped before persist")
    split = split_per_phase_60_40(enriched, phases)
    tr_c, ho_c = count_regimes_post_enrich(split.train), count_regimes_post_enrich(split.holdout)
    train_up, train_down = trend_fracs(tr_c)
    hold_up, hold_down = trend_fracs(ho_c)
    from lumina_core.birth.data_pipeline_types import train_hash as _train_hash

    t_hash = refuse_this_tape_hash(_train_hash(split.train))
    actual_days = actual_calendar_days_from_ticks(enriched)
    purged = PurgedSplit(
        train=list(split.train),
        holdout=list(split.holdout),
        holdout_days=_unique_days(split.holdout),
        train_days=_unique_days(split.train),
    )
    paths = save_birth_data_cache(
        work,
        ticks=enriched,
        split=purged,
        holdout_pct=float(STRAT_HOLD_PCT),
        raw_ticks_hash=raw_hash,
        train_hash=t_hash,
        enrich_version=ENRICH_VERSION,
        requested_days=max(FOUNDATION_HISTORY_START_DAYS, OBJ_DAYS),
        actual_calendar_days=actual_days,
        instruments=[GENESIS_INSTRUMENT],
        stitched=False,
        stitched_from=[],
    )
    world_ok = world_ok_fracs(  # 25/25 both splits
        train_up=train_up, train_down=train_down, hold_up=hold_up, hold_down=hold_down
    )
    payload = {
        "symbol": GENESIS_INSTRUMENT,
        "days": actual_days,
        "requested_days": max(FOUNDATION_HISTORY_START_DAYS, OBJ_DAYS),
        "tick_count": len(enriched),
        "train_tick_count": len(split.train),
        "holdout_tick_count": len(split.holdout),
        "gen_counts": dict(gen_counts),
        "gen_up": int(gen_counts["UP"]),
        "gen_down": int(gen_counts["DOWN"]),
        "gen_range": int(gen_counts["RANGE"]),
        "train_gen_counts": dict(split.train_gen),
        "hold_gen_counts": dict(split.hold_gen),
        "train_regime_counts": tr_c,
        "holdout_regime_counts": ho_c,
        "train_up_frac": float(train_up),
        "train_down_frac": float(train_down),
        "hold_up_frac": float(hold_up),
        "hold_down_frac": float(hold_down),
        "slope_abs_used": float(PHYSICS_SLOPE_ABS),
        "prod_slope_abs": float(PROD_SLOPE_ABS),
        "hash": t_hash,
        "raw_ticks_hash": raw_hash,
        "source": SOURCE_LABEL,
        "real_data_pct": float(real_data_percentage(enriched)),
        "host_real_data_pct": float(host_real_data_pct(enriched, certified_cache=True)),
        "fixture_seed": OBJ_SEED,
        "start_et": OBJ_START_ET_ISO,
        "phase_blocks": int(OBJ_PHASE_BLOCKS),
        "splitter": SPLITTER_NAME,
        "ticks_per_leg": [len(x) for x in split_holdout_ab(split.holdout)],
        "path": paths["cache_manifest_path"],
        "ticks_path": paths["ticks_cache_path"],
        "split_path": paths["split_cache_path"],
        "world_ok": bool(world_ok),
    }
    if float(payload["real_data_pct"]) != 0.0:
        raise ObjProtocolError("real_data_percentage must be 0.0")
    if int(payload["holdout_tick_count"]) < MIN_HOLDOUT_TICKS:
        raise ObjProtocolError("holdout < 80k")
    legs = list(payload["ticks_per_leg"])
    if len(legs) != 2 or int(legs[0]) < MIN_TICKS_PER_LEG or int(legs[1]) < MIN_TICKS_PER_LEG:
        raise ObjProtocolError("each chronological half must be >= 40000")
    sidecar = art / "01_obj_fixture_manifest.json"
    write_fixture_sidecar(sidecar, payload)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not world_ok:
        raise ObjProtocolError("S_MISSING: post-enrich 25/25 both splits failed")
    return payload


def load_obj_train_split(work: Path) -> dict[str, Any]:
    split = load_split_cache(work, holdout_pct=STRAT_HOLD_PCT)
    if split is None or not split.train:
        raise ObjProtocolError("obj train split missing")
    manifest = load_cache_manifest(work) or {}
    return {
        "train": list(split.train),
        "holdout": list(split.holdout),
        "train_hash": str(manifest.get("hash") or manifest.get("train_hash") or ""),
    }


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def inspect_obj_protocol() -> dict[str, Any]:
    sites = {
        "force_open_train_only": ("lumina_core/birth/awakening_mark_eyes_env.py", "FORCE_OPEN true only on train factory"),
        "eval_refuses_true": ("lumina_core/birth/awakening_mark_eyes_env.py", "eval refuses True"),
        "slope_012_isolated": ("lumina_core/birth/awakening_obj_tape.py", "slope 0.12 isolated, prod 0.15"),
        "prod_default_015": ("lumina_core/birth/awakening_conv_enrich.py", "production default still 0.15"),
        "exam_seed_20260913": ("lumina_core/birth/awakening_obj_tape.py", "seed 20260913"),
        "floor_150": ("lumina_core/birth/foundation_metrics.py", "POLICY_EDGE_MIN_TRADES = 150"),
        "both_leg_license": ("lumina_core/birth/awakening_obj_flags.py", "both-leg license"),
        "genesis_eyes_ok_false": ("lumina_core/birth/awakening_obj_flags.py", "GENESIS_EYES_OK false"),
        "no_oracle": ("lumina_core/birth/awakening_obj_tape.py", "no oracle"),
    }
    dump: dict[str, Any] = {k: f"{p}:{_line_of(p, n)}" for k, (p, n) in sites.items()}
    dump["missing_sites"] = [k for k, v in dump.items() if str(v).endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = [
    "BASELINE_SHA256",
    "BASELINE_ZIP_NAME",
    "CHILD_META_NAME",
    "CHILD_SCHEMA",
    "CHILD_ZIP_NAME",
    "FLAGS_NAME",
    "OBJ_ART",
    "OBJ_ROOT",
    "OBJ_SEED",
    "OBJ_TIMESTEPS",
    "OBJ_WORK",
    "ORIGIN_EYES_ZIP",
    "TRAIN_SEED",
    "ObjProtocolError",
    "assert_forbidden_init",
    "inspect_obj_protocol",
    "load_obj_train_split",
    "persist_obj_fixture",
    "refuse_this_tape_hash",
    "write_bytes_sha",
]
