"""G1: physical 8.0e-6 drift identity. At most three seeds. No clip-as-success."""

from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

from lumina_core.birth.awakening_band_tape import decide_world_ok, tape_in_band
from lumina_core.birth.awakening_conv_enrich import PHYSICS_SLOPE_ABS, PROD_SLOPE_ABS, enrich_ticks_for_conv
from lumina_core.birth.awakening_mark_eyes import MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_occupancy_tape import (
    _SHOCK,
    assert_gen_counts_balanced,
    count_generator_labels,
    count_regimes_post_enrich,
    generator_labels,
    trend_fracs,
    world_ok_fracs,
)
from lumina_core.birth.awakening_strat_split import SPLITTER_NAME, STRAT_HOLD_PCT, split_per_phase_60_40
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
NQ_MIN = 12000.0  # NQ_MIN 12000 NQ_MAX 28000
NQ_MAX = 28000.0
START = 21150.0
DRIFT_RTH = 8.0e-6  # DRIFT_RTH==8.0e-6
DRIFT_ETH = 2.0e-6
RANGE_KAPPA = 0.01
PHASE_BLOCKS = 6
DRIFT_SEEDS = (20260917, 20260918, 20260919)  # at most three seeds
DRIFT_START_ET = datetime(2025, 10, 6, 18, 0, tzinfo=ET)
DRIFT_START_ET_ISO = DRIFT_START_ET.isoformat()
DRIFT_DAYS = 90
DRIFT_RTH_SEC, DRIFT_ETH_SEC, DRIFT_TIMESTEPS = 10, 60, 10_000
MIN_TREND_UP_FRAC = MIN_TREND_DOWN_FRAC = 0.25
MIN_HOLDOUT_TICKS, MIN_TICKS_PER_LEG = 80_000, 40_000
BASELINE_SHA256 = "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b"
ORIGIN_EYES_ZIP = GENESIS_ART / "genesis_mark_eyes_pi_star.zip"
BASELINE_ZIP_NAME = "baseline_a9ffa852_pi_star.zip"
CHILD_ZIP_NAME = "awakening_drift_v1_pi_star.zip"
CHILD_META_NAME = "awakening_drift_v1_pi_star.json"
CHILD_SCHEMA = "awakening_drift_v1_pi_star_v1"
FLAGS_NAME = "awakening_drift_flags.json"
DRIFT_ROOT = REPO_ROOT / "reports" / "awakening_drift_run"
DRIFT_WORK, DRIFT_ART = DRIFT_ROOT / "workspace", DRIFT_ROOT / "artifacts"
FORBIDDEN_TAPE_PREFIXES = (
    "5726ae7e",
    "e963d1ce",
    "afcea4fa",
    "5e7eae98",
    "8d1aa6f8",
    "9b66a162",
    "7923fa61",
    "b1f16c99",
    "39304755",
    "7e86c2bb",
)
FORBIDDEN_INIT_SHA16 = frozenset(
    {"a9ffa852", "cf70ae5b", "a8a93d6e", "cebe1804", "1123282f", "8cc435c6", "d313b107", "53df2d78"}
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
        "awakening_obj_v1_pi_star.zip",
        "awakening_band_v1_pi_star.zip",
    }
)
assert POLICY_EDGE_MIN_TRADES == 150 and MARK_EYES_OBS_DIM == 46
assert DRIFT_RTH == 8.0e-6 and DRIFT_ETH == 2.0e-6 and RANGE_KAPPA == 0.01
assert PHASE_BLOCKS == 6 and len(DRIFT_SEEDS) == 3 and START == 21150.0 == float(GENESIS_START_PRICE)
assert MIN_TREND_UP_FRAC == 0.25 and PHYSICS_SLOPE_ABS == 0.12 and PROD_SLOPE_ABS == 0.15
assert NQ_MIN == 12000.0 and NQ_MAX == 28000.0 and BASELINE_SHA256.startswith("a9ffa852")


class DriftProtocolError(RuntimeError):
    """AWAKENING_PHYSICAL_DRIFT protocol crime (fail-closed)."""


def assert_physical_drift(drift_rth: float) -> float:
    value = float(drift_rth)
    if abs(value - 2.4e-4) < 1e-12:
        raise DriftProtocolError("used_old_drift_00024")
    if abs(value - DRIFT_RTH) > 1e-15:
        raise DriftProtocolError(f"DRIFT_RTH used must be 8.0e-6, got {value}")
    return value


def drift_ret(
    label: str, rth: bool, price: float, anchor: float, sigma: float, shock: float, *, drift_rth: float = DRIFT_RTH
) -> float:
    drift = assert_physical_drift(drift_rth) if rth else float(DRIFT_ETH)
    if label == "UP":
        return drift + sigma * shock
    if label == "DOWN":
        return -drift + sigma * shock
    return -RANGE_KAPPA * math.log(max(price, 1.0) / max(anchor, 1.0)) + sigma * shock


def next_drift_seed(attempts: list[dict[str, Any]]) -> int | None:
    if len(attempts) >= 3:  # at most three seeds
        return None
    return int(DRIFT_SEEDS[len(attempts)])


def refuse_this_tape_hash(sha: str) -> str:
    text = str(sha or "").strip().lower()
    extras = _band_disk_hash_prefixes()
    if text.startswith(FORBIDDEN_TAPE_PREFIXES) or (extras and text.startswith(extras)):
        raise DriftProtocolError(f"refused old tape hash {text[:16]} as THIS exam tape")
    return text


def _band_disk_hash_prefixes() -> tuple[str, ...]:
    extras: list[str] = []
    roots = (
        "reports/awakening_band_run/artifacts/awakening_band_flags.json",
        "reports/awakening_band_run/artifacts/01_band_fixture_manifest.json",
    )
    for rel in roots:
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("hash", "fixture_train_hash", "raw_ticks_hash"):
            val = str(data.get(key) or "").strip().lower()
            if len(val) >= 8:
                extras.append(val[:8])
        for att in data.get("attempts") or []:
            val = str(att.get("hash") or "").strip().lower()
            if len(val) >= 8:
                extras.append(val[:8])
    return tuple(extras)


def assert_forbidden_init(path: Path | str, sha: str = "") -> Path:
    target = Path(path)
    text = str(sha or "").strip().lower()
    posix = str(target).replace("\\", "/")
    if text[:8] in FORBIDDEN_INIT_SHA16:
        raise DriftProtocolError(f"refused forbidden init sha {text[:8]}")
    if target.name in FORBIDDEN_INIT_NAMES or is_gitignored_ppo_zip(target) or "/lumina_agents/ppo/" in f"/{posix}":
        raise DriftProtocolError(f"refused forbidden init {target.name}")
    return target


def generate_drift_tape_ticks(
    *, seed: int, start_price: float = START, drift_rth: float = DRIFT_RTH
) -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    pinned = assert_physical_drift(drift_rth)
    stamps = _iter_session_times(
        start_et=DRIFT_START_ET, calendar_days=DRIFT_DAYS, rth_bar_seconds=DRIFT_RTH_SEC, eth_bar_seconds=DRIFT_ETH_SEC
    )
    if len(stamps) < 1_000:
        raise DriftProtocolError(f"drift fixture too thin: {len(stamps)}")
    rng = np.random.default_rng(int(seed))
    labels = generator_labels(len(stamps), PHASE_BLOCKS)
    gen_counts = assert_gen_counts_balanced(count_generator_labels(labels))
    price = float(start_price)
    ewma_var = (0.00018) ** 2
    session_anchor = price
    last_et_date = stamps[0].date()
    ticks: list[dict[str, Any]] = []
    prev_ts_utc: datetime | None = None
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
        ret = drift_ret(labels[i], rth, price, session_anchor, sigma, shock, drift_rth=pinned)
        price = max(1_000.0, _round_tick(price * (1.0 + ret)))
        half = max(NQ_TICK_SIZE, abs(shock) * sigma * price * 8.0)
        burst = near_open or (sigma > 0.0004)
        volume = int(
            rng.integers(4_000, 16_000) if rth and burst else rng.integers(400, 2_400) if rth else rng.integers(40, 280)
        )
        near_close = rth and (15 * 60 + 50) <= minutes < (16 * 60)
        spread = (4.0 if (near_open or near_close) else (3.0 if burst else (1.0 if rth else 2.0))) * NQ_TICK_SIZE
        bid, ask = _round_tick(price - spread / 2.0), _round_tick(price + spread / 2.0)
        if ask <= bid:
            ask = bid + NQ_TICK_SIZE
        ts_utc = ts_et.astimezone(timezone.utc)
        if prev_ts_utc is not None and ts_utc <= prev_ts_utc:
            ts_utc = prev_ts_utc + timedelta(milliseconds=1)
        prev_ts_utc = ts_utc
        # fmt: off
        ticks.append({"timestamp": ts_utc.isoformat(), "last": float(price), "close": float(price), "open": float(price),
                      "high": float(_round_tick(price + half)), "low": float(_round_tick(max(NQ_TICK_SIZE, price - half))),
                      "bid": float(bid), "ask": float(ask), "volume": int(volume), "imbalance": 1.0,
                      "source": SOURCE_LABEL, "instrument": GENESIS_INSTRUMENT, "session": "RTH" if rth else "ETH"})
        # fmt: on
    if any("regime" in row or "gen_phase" in row for row in ticks):
        raise DriftProtocolError("no oracle")
    return ticks, labels, gen_counts


def try_drift_seeds() -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for seed in DRIFT_SEEDS:  # at most three seeds
        ticks, labels, gen_counts = generate_drift_tape_ticks(seed=int(seed), drift_rth=DRIFT_RTH)
        in_band, mn, mx = tape_in_band(ticks)
        attempts.append({"seed": int(seed), "min": float(mn), "max": float(mx), "in_band": bool(in_band)})
        if in_band:
            # fmt: off
            return {"ticks": ticks, "labels": labels, "gen_counts": gen_counts, "attempts": attempts,
                    "seed_used": int(seed), "in_band": True, "price_min": float(mn), "price_max": float(mx), "world_fail": False}
            # fmt: on
    last = attempts[-1]
    # fmt: off
    return {"ticks": [], "labels": [], "gen_counts": {}, "attempts": attempts, "seed_used": 0,
            "in_band": False, "price_min": float(last["min"]), "price_max": float(last["max"]), "world_fail": True}
    # fmt: on


def persist_drift_fixture(work: Path, art: Path) -> dict[str, Any]:
    probe = try_drift_seeds()
    art.mkdir(parents=True, exist_ok=True)
    # fmt: off
    base = {
        "seed_used": int(probe.get("seed_used") or 0), "attempts": list(probe.get("attempts") or []),
        "price_min": float(probe.get("price_min") or 0.0), "price_max": float(probe.get("price_max") or 0.0),
        "in_band": bool(probe.get("in_band")), "world_ok": False, "world_fail": bool(probe.get("world_fail")),
        "enrich_fail": False, "train_up_frac": 0.0, "train_down_frac": 0.0, "hold_up_frac": 0.0, "hold_down_frac": 0.0,
        "hash": "", "source": SOURCE_LABEL, "real_data_pct": 0.0, "drift_rth": float(DRIFT_RTH),
        "slope_abs_used": float(PHYSICS_SLOPE_ABS), "prod_slope_abs": float(PROD_SLOPE_ABS),
        "phase_blocks": int(PHASE_BLOCKS), "splitter": SPLITTER_NAME, "start_et": DRIFT_START_ET_ISO,
        "start_price": float(START), "nq_min": float(NQ_MIN), "nq_max": float(NQ_MAX), "clipped": False,
    }
    # fmt: on
    if bool(probe.get("world_fail")):
        sidecar = art / "01_drift_fixture_manifest.json"
        write_fixture_sidecar(sidecar, base)
        sidecar.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return base
    raw, phases, gen_counts = list(probe["ticks"]), list(probe["labels"]), dict(probe["gen_counts"])
    cache = work / "state" / "birth_enrichment_cache"
    if cache.is_dir():
        shutil.rmtree(cache)
    raw_hash = compute_ticks_fingerprint(raw)
    enriched = enrich_ticks_for_conv(
        [dict(t) for t in raw], workspace_root=work, raw_ticks_hash=raw_hash, enrich_version=ENRICH_VERSION
    )
    for row in enriched:
        row["source"] = SOURCE_LABEL
        row.pop("gen_phase", None)
    if any("gen_phase" in row for row in enriched):
        raise DriftProtocolError("generator phase side-channel must be stripped before persist")
    split = split_per_phase_60_40(enriched, phases)
    tr_c, ho_c = count_regimes_post_enrich(split.train), count_regimes_post_enrich(split.holdout)
    train_up, train_down = trend_fracs(tr_c)
    hold_up, hold_down = trend_fracs(ho_c)
    from lumina_core.birth.data_pipeline_types import train_hash as _train_hash

    t_hash = refuse_this_tape_hash(_train_hash(split.train))
    actual_days = actual_calendar_days_from_ticks(enriched)
    days = {str(row.get("timestamp") or "")[:10] for row in split.holdout}
    train_days = {str(row.get("timestamp") or "")[:10] for row in split.train}
    # fmt: off
    purged = PurgedSplit(train=list(split.train), holdout=list(split.holdout), holdout_days=len(days), train_days=len(train_days))
    paths = save_birth_data_cache(
        work, ticks=enriched, split=purged, holdout_pct=float(STRAT_HOLD_PCT), raw_ticks_hash=raw_hash,
        train_hash=t_hash, enrich_version=ENRICH_VERSION,
        requested_days=max(FOUNDATION_HISTORY_START_DAYS, DRIFT_DAYS), actual_calendar_days=actual_days,
        instruments=[GENESIS_INSTRUMENT], stitched=False, stitched_from=[],
    )
    fracs_ok = world_ok_fracs(train_up=train_up, train_down=train_down, hold_up=hold_up, hold_down=hold_down)
    world_ok = decide_world_ok(in_band=True, fracs_ok=fracs_ok, clipped=False)
    legs = [len(x) for x in split_holdout_ab(split.holdout)]
    payload = {
        **base, "symbol": GENESIS_INSTRUMENT, "days": actual_days,
        "requested_days": max(FOUNDATION_HISTORY_START_DAYS, DRIFT_DAYS),
        "tick_count": len(enriched), "train_tick_count": len(split.train), "holdout_tick_count": len(split.holdout),
        "gen_counts": dict(gen_counts), "gen_up": int(gen_counts["UP"]), "gen_down": int(gen_counts["DOWN"]),
        "gen_range": int(gen_counts["RANGE"]), "train_gen_counts": dict(split.train_gen),
        "hold_gen_counts": dict(split.hold_gen), "train_regime_counts": tr_c, "holdout_regime_counts": ho_c,
        "train_up_frac": float(train_up), "train_down_frac": float(train_down),
        "hold_up_frac": float(hold_up), "hold_down_frac": float(hold_down),
        "hash": t_hash, "raw_ticks_hash": raw_hash, "real_data_pct": float(real_data_percentage(enriched)),
        "host_real_data_pct": float(host_real_data_pct(enriched, certified_cache=True)),
        "ticks_per_leg": legs, "path": paths["cache_manifest_path"],
        "ticks_path": paths["ticks_cache_path"], "split_path": paths["split_cache_path"],
        "world_ok": bool(world_ok), "world_fail": False, "in_band": True, "enrich_fail": not bool(world_ok),
    }
    # fmt: on
    if float(payload["real_data_pct"]) != 0.0:
        raise DriftProtocolError("real_data_percentage must be 0.0")
    if int(payload["holdout_tick_count"]) < MIN_HOLDOUT_TICKS or len(legs) != 2 or min(legs) < MIN_TICKS_PER_LEG:
        raise DriftProtocolError("holdout/leg density failed")
    sidecar = art / "01_drift_fixture_manifest.json"
    write_fixture_sidecar(sidecar, payload)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def load_drift_train_split(work: Path) -> dict[str, Any]:
    split = load_split_cache(work, holdout_pct=STRAT_HOLD_PCT)
    if split is None or not split.train:
        raise DriftProtocolError("drift train split missing")
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


def inspect_drift_protocol() -> dict[str, Any]:
    sites = {
        "drift_rth_8e_6": ("lumina_core/birth/awakening_drift_tape.py", "DRIFT_RTH==8.0e-6"),
        "phase_blocks_6": ("lumina_core/birth/awakening_drift_tape.py", "PHASE_BLOCKS = 6"),
        "nq_min_max": ("lumina_core/birth/awakening_drift_tape.py", "NQ_MIN 12000 NQ_MAX 28000"),
        "no_clip_as_success": ("lumina_core/birth/awakening_drift_tape.py", "no clip-as-success"),
        "at_most_three_seeds": ("lumina_core/birth/awakening_drift_tape.py", "at most three seeds"),
        "seeds_20260917_19": ("lumina_core/birth/awakening_drift_tape.py", "20260917, 20260918, 20260919"),
        "guard_1pct_unedited": ("lumina_core/birth/birth_constitution_guard.py", "risk_exceeds_1pct"),
        # fmt: off
        "force_open_train_only": ("lumina_core/birth/awakening_mark_eyes_env.py", "FORCE_OPEN true only on train factory"),
        # fmt: on
        "eval_refuses_true": ("lumina_core/birth/awakening_mark_eyes_env.py", "eval refuses True"),
        "floor_150": ("lumina_core/birth/foundation_metrics.py", "POLICY_EDGE_MIN_TRADES = 150"),
        "both_leg_license": ("lumina_core/birth/awakening_drift_flags.py", "both-leg license"),
        "genesis_eyes_ok_false": ("lumina_core/birth/awakening_drift_flags.py", "GENESIS_EYES_OK false"),
    }
    dump: dict[str, Any] = {k: f"{p}:{_line_of(p, n)}" for k, (p, n) in sites.items()}
    dump["missing_sites"] = [k for k, v in dump.items() if str(v).endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump
