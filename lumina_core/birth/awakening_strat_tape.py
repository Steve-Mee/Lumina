"""G1: NEW 2/2/2 occupancy tape. Seed 20260911. Drift frozen. Split is not here."""

from __future__ import annotations

import json
import math
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np

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
)
from lumina_core.birth.awakening_strat_split import (
    SPLITTER_NAME,
    STRAT_HOLD_PCT,
    StratProtocolError,
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
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim
from lumina_core.rl.trend_features import ENRICH_VERSION

ET = ZoneInfo("America/New_York")
STRAT_SEED = 20260911  # seed 20260911 start_et 2026-01-05
STRAT_START_ET = datetime(2026, 1, 5, 18, 0, tzinfo=ET)
STRAT_START_ET_ISO = "2026-01-05T18:00:00-05:00"
STRAT_DAYS = 90
STRAT_RTH_SEC = 10
STRAT_ETH_SEC = 60
STRAT_DRIFT_RTH = 0.00024  # drift 0.00024 frozen
STRAT_RANGE_KAPPA = 0.01
STRAT_PHASE_BLOCKS = 6
STRAT_TIMESTEPS = 10_000
TRAIN_SEED = 20260911
DELTA_MEAN_R_MIN = 0.05
HOLE_BLOW_MAX = 5
MIN_TREND_UP_FRAC = 0.25
MIN_TREND_DOWN_FRAC = 0.25
MIN_HOLDOUT_TICKS = 80_000
MIN_TICKS_PER_LEG = 40_000
FAMILY = "AWAKENING_MARK_EYES"
BASELINE_SHA256 = "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b"
ORIGIN_EYES_ZIP = GENESIS_ART / "genesis_mark_eyes_pi_star.zip"
BASELINE_ZIP_NAME = "baseline_a9ffa852_pi_star.zip"
CHILD_ZIP_NAME = "awakening_strat_v1_pi_star.zip"
CHILD_META_NAME = "awakening_strat_v1_pi_star.json"
CHILD_SCHEMA = "awakening_strat_v1_pi_star_v1"
SOURCE = "awakening_stratified_split"
FLAGS_NAME = "awakening_strat_flags.json"
STRAT_ROOT = REPO_ROOT / "reports" / "awakening_strat_run"
STRAT_WORK, STRAT_ART = STRAT_ROOT / "workspace", STRAT_ROOT / "artifacts"
FORBIDDEN_TAPE_PREFIXES = (
    "5726ae7e",
    "e963d1ce",
    "afcea4fa",
    "5e7eae98",
    "8d1aa6f8",
    "9b66a162",
    "7e86c2bb",
)
FORBIDDEN_INIT_SHA16 = frozenset({"a9ffa852", "cebe1804", "1123282f", "8cc435c6", "d313b107", "53df2d78"})
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
    }
)
assert POLICY_EDGE_MIN_TRADES == 150 and MARK_EYES_OBS_DIM == 46
assert STRAT_DRIFT_RTH == 0.00024 == OCCUPANCY_DRIFT_RTH
assert STRAT_RANGE_KAPPA == 0.01 == OCCUPANCY_RANGE_KAPPA
assert STRAT_HOLD_PCT == 0.40 and STRAT_PHASE_BLOCKS == 6
assert MIN_TREND_UP_FRAC == 0.25 and MIN_TREND_DOWN_FRAC == 0.25


def refuse_this_tape_hash(sha: str) -> str:
    text = str(sha or "").strip().lower()
    if text.startswith(FORBIDDEN_TAPE_PREFIXES):
        raise StratProtocolError(f"refused old tape hash {text[:16]} as THIS exam tape")
    return text


def assert_forbidden_init(path: Path | str, sha: str = "") -> Path:
    target = Path(path)
    text = str(sha or "").strip().lower()
    posix = str(target).replace("\\", "/")
    if text[:8] in FORBIDDEN_INIT_SHA16:
        raise StratProtocolError(f"refused forbidden init sha {text[:8]}")
    if target.name in FORBIDDEN_INIT_NAMES or is_gitignored_ppo_zip(target) or "/lumina_agents/ppo/" in f"/{posix}":
        raise StratProtocolError(f"refused forbidden init {target.name}")
    return target


def generate_strat_tape_ticks() -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    stamps = _iter_session_times(
        start_et=STRAT_START_ET,
        calendar_days=STRAT_DAYS,
        rth_bar_seconds=STRAT_RTH_SEC,
        eth_bar_seconds=STRAT_ETH_SEC,
    )
    if len(stamps) < 1_000:
        raise StratProtocolError(f"strat fixture too thin: {len(stamps)}")
    rng = np.random.default_rng(STRAT_SEED)
    labels = generator_labels(len(stamps), STRAT_PHASE_BLOCKS)
    gen_counts = assert_gen_counts_balanced(count_generator_labels(labels))
    price = float(GENESIS_START_PRICE)
    ewma_var = (0.00018) ** 2
    session_anchor = price
    last_et_date = stamps[0].date()
    ticks: list[dict[str, Any]] = []
    prev_ts_utc: datetime | None = None
    # no oracle regime — price must earn TREND_* via enrich_ticks_for_sim
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
        raise StratProtocolError("no oracle regime")
    return ticks, labels, gen_counts


def _unique_days(ticks: list[dict[str, Any]]) -> int:
    return len({str(row.get("timestamp") or "")[:10] for row in ticks})


def persist_strat_fixture(work: Path, art: Path) -> dict[str, Any]:
    raw, phases, gen_counts = generate_strat_tape_ticks()
    cache = work / "state" / "birth_enrichment_cache"
    if cache.is_dir():
        shutil.rmtree(cache)
    raw_hash = compute_ticks_fingerprint(raw)
    # enrich full tape then slice by the same index masks
    enriched = enrich_ticks_for_sim(
        [dict(t) for t in raw],
        workspace_root=work,
        raw_ticks_hash=raw_hash,
        enrich_version=ENRICH_VERSION,
    )
    for row in enriched:
        row["source"] = SOURCE_LABEL
        row.pop("gen_phase", None)
    if any("gen_phase" in row for row in enriched):
        raise StratProtocolError("generator phase side-channel must be stripped before persist")
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
        requested_days=max(FOUNDATION_HISTORY_START_DAYS, STRAT_DAYS),
        actual_calendar_days=actual_days,
        instruments=[GENESIS_INSTRUMENT],
        stitched=False,
        stitched_from=[],
    )
    payload = {
        "symbol": GENESIS_INSTRUMENT,
        "days": actual_days,
        "requested_days": max(FOUNDATION_HISTORY_START_DAYS, STRAT_DAYS),
        "tick_count": len(enriched),
        "train_tick_count": len(split.train),
        "holdout_tick_count": len(split.holdout),
        "gen_counts": dict(gen_counts),
        "gen_up": int(gen_counts["UP"]),
        "gen_down": int(gen_counts["DOWN"]),
        "gen_range": int(gen_counts["RANGE"]),
        "train_gen_counts": dict(split.train_gen),
        "hold_gen_counts": dict(split.hold_gen),
        "train_gen_up": int(split.train_gen["UP"]),
        "train_gen_down": int(split.train_gen["DOWN"]),
        "train_gen_range": int(split.train_gen["RANGE"]),
        "hold_gen_up": int(split.hold_gen["UP"]),
        "hold_gen_down": int(split.hold_gen["DOWN"]),
        "hold_gen_range": int(split.hold_gen["RANGE"]),
        "train_regime_counts": tr_c,
        "holdout_regime_counts": ho_c,
        "train_up_frac": float(train_up),
        "train_down_frac": float(train_down),
        "hold_up_frac": float(hold_up),
        "hold_down_frac": float(hold_down),
        "hash": t_hash,
        "raw_ticks_hash": raw_hash,
        "source": SOURCE_LABEL,
        "real_data_pct": float(real_data_percentage(enriched)),
        "host_real_data_pct": float(host_real_data_pct(enriched, certified_cache=True)),
        "fixture_seed": STRAT_SEED,
        "start_et": STRAT_START_ET_ISO,
        "phase_blocks": int(STRAT_PHASE_BLOCKS),
        "splitter": SPLITTER_NAME,
        "ticks_per_leg": [len(x) for x in split_holdout_ab(split.holdout)],
        "path": paths["cache_manifest_path"],
        "ticks_path": paths["ticks_cache_path"],
        "split_path": paths["split_cache_path"],
        "world_ok": world_ok_fracs(  # 25/25 train AND holdout
            train_up=train_up, train_down=train_down, hold_up=hold_up, hold_down=hold_down
        ),
    }
    if float(payload["real_data_pct"]) != 0.0:
        raise StratProtocolError("real_data_percentage must be 0.0")
    if int(payload["holdout_tick_count"]) < MIN_HOLDOUT_TICKS:
        raise StratProtocolError("holdout < 80k")
    legs = list(payload["ticks_per_leg"])
    if len(legs) != 2 or int(legs[0]) < MIN_TICKS_PER_LEG or int(legs[1]) < MIN_TICKS_PER_LEG:
        raise StratProtocolError("each chronological half must be >= 40000")
    sidecar = art / "01_strat_fixture_manifest.json"
    write_fixture_sidecar(sidecar, payload)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def load_strat_train_split(work: Path) -> dict[str, Any]:
    split = load_split_cache(work, holdout_pct=STRAT_HOLD_PCT)
    if split is None or not split.train:
        raise StratProtocolError("strat train split missing")
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


def inspect_strat_protocol() -> dict[str, Any]:
    split_rel = "lumina_core/birth/awakening_strat_split.py"
    tape_rel = "lumina_core/birth/awakening_strat_tape.py"
    sites = {
        "per_block_cut_060": (split_rel, "per-block cut 0.60"),
        "no_shuffle": (split_rel, "no shuffle"),
        "gen_counts_per_split": (split_rel, "gen counts per split n/3 ± 2"),
        "exam_seed_start_et": (tape_rel, "seed 20260911 start_et 2026-01-05"),
        "drift_00024_frozen": (tape_rel, "drift 0.00024 frozen"),
        "fracs_25_25": (tape_rel, "25/25 train AND holdout"),
        "no_oracle_regime": (tape_rel, "no oracle regime"),
        "enrich_full_then_slice": (tape_rel, "enrich full tape then slice by the same index masks"),
        "body_skipped": ("lumina_core/birth/awakening_strat_run.py", "body skipped when not world_ok"),
        "floor_150": ("lumina_core/birth/foundation_metrics.py", "POLICY_EDGE_MIN_TRADES = 150"),
        "both_leg_license": ("lumina_core/birth/awakening_strat_flags.py", "both-leg license"),
        "genesis_eyes_ok_false": ("lumina_core/birth/awakening_strat_flags.py", "GENESIS_EYES_OK false"),
        "hooks_default_false": (
            "lumina_core/birth/awakening_path_exit_k3.py",
            'ContextVar("path_exit_k3_shadow", default=False)',
        ),
        "honesty_synthetic_0": ("lumina_core/birth/data_source_honesty.py", "synthetic_cloud_fixture"),
    }
    dump: dict[str, Any] = {k: f"{p}:{_line_of(p, n)}" for k, (p, n) in sites.items()}
    dump["missing_sites"] = [k for k, v in dump.items() if str(v).endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump
