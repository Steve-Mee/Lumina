"""AWAKENING_OCCUPANCY: equal UP/DOWN/RANGE generator blocks. Not an enricher knob."""

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
from lumina_core.birth.birth_exit_policy_export import file_sha256, is_gitignored_ppo_zip
from lumina_core.birth.data_source_honesty import host_real_data_pct, real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import GENESIS_ART, GENESIS_INSTRUMENT, GENESIS_START_PRICE, REPO_ROOT
from lumina_core.birth.genesis_mark_eyes_eval import split_holdout_ab
from lumina_core.birth.synthetic_cloud_fixture import (
    NQ_TICK_SIZE,
    SOURCE_LABEL,
    CloudFixtureSpec,
    persist_cloud_fixture,
    write_fixture_sidecar,
    _iter_session_times,
    _is_rth,
    _round_tick,
)
from lumina_core.birth.tick_cache_persist import load_cache_manifest, load_split_cache

ET = ZoneInfo("America/New_York")
OCCUPANCY_SEED = 20260910  # exam seed 20260910 start_et 2026-02-02
OCCUPANCY_START_ET = datetime(2026, 2, 2, 18, 0, tzinfo=ET)
OCCUPANCY_START_ET_ISO = "2026-02-02T18:00:00-05:00"
OCCUPANCY_HOLD_PCT = 0.40
OCCUPANCY_DAYS = 90
OCCUPANCY_RTH_SEC = 10
OCCUPANCY_ETH_SEC = 60
OCCUPANCY_DRIFT_RTH = 0.00024  # drift 0.00024 kappa 0.01 (not a third retune family)
OCCUPANCY_DRIFT_ETH = 0.00006
OCCUPANCY_RANGE_KAPPA = 0.01
OCCUPANCY_PHASE_BLOCKS = 6
ALLOWED_PHASE_BLOCKS = frozenset({6, 12})  # PHASE_BLOCKS in {6,12}
MIN_TREND_UP_FRAC = 0.25
MIN_TREND_DOWN_FRAC = 0.25
OCCUPANCY_TIMESTEPS = 10_000
TRAIN_SEED = 20260910
DELTA_MEAN_R_MIN = 0.05
HOLE_BLOW_MAX = 5
MIN_HOLDOUT_TICKS = 80_000
MIN_TICKS_PER_LEG = 40_000
FAMILY = "AWAKENING_MARK_EYES"
BASELINE_SHA256 = "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b"
ORIGIN_EYES_ZIP = GENESIS_ART / "genesis_mark_eyes_pi_star.zip"
BASELINE_ZIP_NAME = "baseline_a9ffa852_pi_star.zip"
CHILD_ZIP_NAME = "awakening_occupancy_v1_pi_star.zip"
CHILD_META_NAME = "awakening_occupancy_v1_pi_star.json"
CHILD_SCHEMA = "awakening_occupancy_v1_pi_star_v1"
SOURCE = "awakening_occupancy_balance"
FLAGS_NAME = "awakening_occupancy_flags.json"
OCCUPANCY_ROOT = REPO_ROOT / "reports" / "awakening_occupancy_run"
OCCUPANCY_WORK, OCCUPANCY_ART = OCCUPANCY_ROOT / "workspace", OCCUPANCY_ROOT / "artifacts"
PHASE_LABELS = ("UP", "DOWN", "RANGE")
FORBIDDEN_TAPE_PREFIXES = ("5726ae7e", "e963d1ce", "afcea4fa", "5e7eae98", "8d1aa6f8", "7e86c2bb")
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
    }
)
_SHOCK = 0.00030
assert POLICY_EDGE_MIN_TRADES == 150 and MARK_EYES_OBS_DIM == 46
assert OCCUPANCY_DRIFT_RTH == 0.00024 and OCCUPANCY_RANGE_KAPPA == 0.01
assert MIN_TREND_UP_FRAC == 0.25 and MIN_TREND_DOWN_FRAC == 0.25


class OccupancyProtocolError(RuntimeError):
    """AWAKENING_OCCUPANCY_BALANCE protocol crime (fail-closed)."""


def phase_index(i: int, n: int, blocks: int) -> int:
    """phase formula % 3 — equal wrap, never 3/2/1 occupancy."""
    assert_phase_blocks(blocks)
    return (int(i) * int(blocks) // max(1, int(n))) % 3


def assert_phase_blocks(blocks: int) -> int:
    value = int(blocks)
    if value not in ALLOWED_PHASE_BLOCKS:
        raise OccupancyProtocolError("PHASE_BLOCKS in {6,12} only")
    return value


def generator_labels(n: int, blocks: int) -> list[str]:
    return [PHASE_LABELS[phase_index(i, n, blocks)] for i in range(int(n))]


def count_generator_labels(labels: list[str]) -> dict[str, int]:
    counts = {name: 0 for name in PHASE_LABELS}
    for label in labels:
        key = str(label).upper()
        if key not in counts:
            raise OccupancyProtocolError(f"unknown generator label {key}")
        counts[key] += 1
    return counts


def assert_gen_counts_balanced(counts: dict[str, int]) -> dict[str, int]:
    """generator counts n/3 ± 2; max-min ≤ 2. 3/2/1 occupancy is S_MISSING."""
    vals = [int(counts.get("UP") or 0), int(counts.get("DOWN") or 0), int(counts.get("RANGE") or 0)]
    n = int(sum(vals))
    if n < 3:
        raise OccupancyProtocolError("S_MISSING: generator tape thinner than 3 ticks")
    three_two_one = sorted([n * 3 // 6, n * 2 // 6, n * 1 // 6])
    if n >= 6 and sorted(vals) == three_two_one and len(set(vals)) == 3:
        raise OccupancyProtocolError("S_MISSING: helper still emits 3/2/1")
    target = n // 3
    if max(vals) - min(vals) > 2:
        raise OccupancyProtocolError("S_MISSING: generator counts not n/3 ± 2")
    if any(abs(v - target) > 2 for v in vals):
        raise OccupancyProtocolError("S_MISSING: generator counts not n/3 ± 2")
    return {"UP": vals[0], "DOWN": vals[1], "RANGE": vals[2]}


def _ret(label: str, rth: bool, price: float, anchor: float, sigma: float, shock: float) -> float:
    drift = OCCUPANCY_DRIFT_RTH if rth else OCCUPANCY_DRIFT_ETH
    if label == "UP":
        return drift + sigma * shock
    if label == "DOWN":
        return -drift + sigma * shock
    return -OCCUPANCY_RANGE_KAPPA * math.log(max(price, 1.0) / max(anchor, 1.0)) + sigma * shock


def generate_occupancy_tape_ticks(*, blocks: int = OCCUPANCY_PHASE_BLOCKS) -> tuple[list[dict[str, Any]], dict[str, int]]:
    blocks = assert_phase_blocks(blocks)
    stamps = _iter_session_times(
        start_et=OCCUPANCY_START_ET,
        calendar_days=OCCUPANCY_DAYS,
        rth_bar_seconds=OCCUPANCY_RTH_SEC,
        eth_bar_seconds=OCCUPANCY_ETH_SEC,
    )
    if len(stamps) < 1_000:
        raise OccupancyProtocolError(f"occupancy fixture too thin: {len(stamps)}")
    rng = np.random.default_rng(OCCUPANCY_SEED)
    labels = generator_labels(len(stamps), blocks)
    gen_counts = assert_gen_counts_balanced(count_generator_labels(labels))
    price = float(GENESIS_START_PRICE)
    ewma_var = (0.00018) ** 2
    session_anchor = price
    last_et_date = stamps[0].date()
    ticks: list[dict[str, Any]] = []
    prev_ts_utc: datetime | None = None
    # no oracle regime assign — price must earn TREND_* via enrich_ticks_for_sim
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
    if any("regime" in row for row in ticks):
        raise OccupancyProtocolError("no oracle regime assign")
    return ticks, gen_counts


def count_regimes_post_enrich(ticks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in ticks:
        key = str(row.get("regime") or "NEUTRAL").upper()
        counts[key] = counts.get(key, 0) + 1
    return counts


def trend_fracs(counts: dict[str, int]) -> tuple[float, float]:
    n = max(1, sum(int(v) for v in counts.values()))
    return counts.get("TREND_UP", 0) / n, counts.get("TREND_DOWN", 0) / n


def world_ok_fracs(*, train_up: float, train_down: float, hold_up: float, hold_down: float) -> bool:
    """25/25 train AND holdout — post-enrich TREND_* floor."""
    return train_up >= MIN_TREND_UP_FRAC and train_down >= MIN_TREND_DOWN_FRAC and hold_up >= MIN_TREND_UP_FRAC and hold_down >= MIN_TREND_DOWN_FRAC


def refuse_this_tape_hash(sha: str) -> str:
    text = str(sha or "").strip().lower()
    if text.startswith(FORBIDDEN_TAPE_PREFIXES):
        raise OccupancyProtocolError(f"refused old tape hash {text[:16]} as THIS exam tape")
    return text


def assert_forbidden_init(path: Path | str, sha: str = "") -> Path:
    target = Path(path)
    text = str(sha or "").strip().lower()
    posix = str(target).replace("\\", "/")
    if text[:8] in FORBIDDEN_INIT_SHA16:
        raise OccupancyProtocolError(f"refused forbidden init sha {text[:8]}")
    if target.name in FORBIDDEN_INIT_NAMES or is_gitignored_ppo_zip(target) or "/lumina_agents/ppo/" in f"/{posix}":
        raise OccupancyProtocolError(f"refused forbidden init {target.name}")
    return target


def write_bytes_sha(path: Path) -> str:
    digest = file_sha256(path)
    path.with_name(path.name + ".sha256").write_text(digest + "\n", encoding="utf-8")
    return digest


def _cloud_spec() -> CloudFixtureSpec:
    return CloudFixtureSpec(
        instrument=GENESIS_INSTRUMENT,
        calendar_days=int(OCCUPANCY_DAYS),
        holdout_pct=float(OCCUPANCY_HOLD_PCT),
        start_price=float(GENESIS_START_PRICE),
        seed=int(OCCUPANCY_SEED),
        start_et=OCCUPANCY_START_ET,
        rth_bar_seconds=int(OCCUPANCY_RTH_SEC),
        eth_bar_seconds=int(OCCUPANCY_ETH_SEC),
    )


def _empty_manifest(*, gen_counts: dict[str, int], blocks: int, reason: str) -> dict[str, Any]:
    up, down, rng = (int(gen_counts.get(k) or 0) for k in PHASE_LABELS)
    return {
        "gen_counts": dict(gen_counts),
        "gen_up": up,
        "gen_down": down,
        "gen_range": rng,
        "train_regime_counts": {},
        "holdout_regime_counts": {},
        "train_up_frac": 0.0,
        "train_down_frac": 0.0,
        "hold_up_frac": 0.0,
        "hold_down_frac": 0.0,
        "hash": "",
        "source": SOURCE_LABEL,
        "real_data_pct": 0.0,
        "phase_blocks_used": int(blocks),
        "world_ok": False,
        "fixture_seed": OCCUPANCY_SEED,
        "start_et": OCCUPANCY_START_ET_ISO,
        "reason": reason,
    }


def persist_occupancy_fixture(work: Path, art: Path) -> dict[str, Any]:
    last_err = "S_MISSING: generator counts failed both 6 and 12"
    payload: dict[str, Any] = _empty_manifest(gen_counts={}, blocks=6, reason=last_err)
    for blocks in (6, 12):
        try:
            raw, gen_counts = generate_occupancy_tape_ticks(blocks=blocks)
        except OccupancyProtocolError as exc:
            last_err = str(exc)
            payload = _empty_manifest(gen_counts={}, blocks=blocks, reason=last_err)
            continue
        cache = work / "state" / "birth_enrichment_cache"
        if cache.is_dir():
            shutil.rmtree(cache)
        try:
            result = persist_cloud_fixture(work, spec=_cloud_spec(), ticks=raw)
        except Exception as exc:
            last_err = str(exc)
            payload = _empty_manifest(gen_counts=gen_counts, blocks=blocks, reason=last_err)
            break
        train = list(result.split.train)
        holdout = list(result.split.holdout)
        tr_c, ho_c = count_regimes_post_enrich(train), count_regimes_post_enrich(holdout)
        train_up, train_down = trend_fracs(tr_c)
        hold_up, hold_down = trend_fracs(ho_c)
        payload = dict(result.fixture_manifest)
        payload.update(
            {
                "real_data_pct": float(real_data_percentage(result.ticks)),
                "host_real_data_pct": float(host_real_data_pct(result.ticks, certified_cache=True)),
                "fixture_seed": OCCUPANCY_SEED,
                "start_et": OCCUPANCY_START_ET_ISO,
                "source": SOURCE_LABEL,
                "gen_counts": dict(gen_counts),
                "gen_up": int(gen_counts["UP"]),
                "gen_down": int(gen_counts["DOWN"]),
                "gen_range": int(gen_counts["RANGE"]),
                "train_regime_counts": tr_c,
                "holdout_regime_counts": ho_c,
                "train_up_frac": float(train_up),
                "train_down_frac": float(train_down),
                "hold_up_frac": float(hold_up),
                "hold_down_frac": float(hold_down),
                "phase_blocks_used": int(blocks),
                "ticks_per_leg": [len(x) for x in split_holdout_ab(holdout)],
                "world_ok": world_ok_fracs(
                    train_up=train_up, train_down=train_down, hold_up=hold_up, hold_down=hold_down
                ),
            }
        )
        refuse_this_tape_hash(str(payload.get("hash") or ""))
        if float(payload.get("real_data_pct") or 0.0) != 0.0:
            raise OccupancyProtocolError("real_data_percentage must be 0.0")
        if int(payload.get("holdout_tick_count") or 0) < MIN_HOLDOUT_TICKS:
            raise OccupancyProtocolError("holdout < 80k")
        legs = list(payload.get("ticks_per_leg") or [])
        if len(legs) != 2 or int(legs[0]) < MIN_TICKS_PER_LEG or int(legs[1]) < MIN_TICKS_PER_LEG:
            raise OccupancyProtocolError("each chronological half must be >= 40000")
        break
    else:
        raise OccupancyProtocolError(last_err)
    sidecar = art / "01_occupancy_fixture_manifest.json"
    write_fixture_sidecar(sidecar, payload)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def load_occupancy_train_split(work: Path) -> dict[str, Any]:
    split = load_split_cache(work, holdout_pct=OCCUPANCY_HOLD_PCT)
    if split is None or not split.train:
        raise OccupancyProtocolError("occupancy train split missing")
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


def inspect_occupancy_protocol() -> dict[str, Any]:
    rel = "lumina_core/birth/awakening_occupancy_tape.py"
    sites = {
        "phase_formula_mod_3": (rel, "phase formula % 3"),
        "phase_blocks_6_or_12": (rel, "PHASE_BLOCKS in {6,12}"),
        "gen_counts_n3": (rel, "n/3 ± 2"),
        "exam_seed_20260910": (rel, "20260910"),
        "start_et_2026_02_02": (rel, "2026-02-02"),
        "drift_kappa_attempt2": (rel, "not a third retune family"),
        "fracs_25_25": (rel, "25/25 train AND holdout"),
        "no_oracle_regime": (rel, "no oracle regime assign"),
        "body_skipped": ("lumina_core/birth/awakening_occupancy_run.py", "body skipped when not world_ok"),
        "floor_150": ("lumina_core/birth/foundation_metrics.py", "POLICY_EDGE_MIN_TRADES = 150"),
        "both_leg_license": ("lumina_core/birth/awakening_occupancy_flags.py", "license both legs"),
        "genesis_eyes_ok_forced_false": ("lumina_core/birth/awakening_occupancy_flags.py", "GENESIS_EYES_OK forced false"),
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
