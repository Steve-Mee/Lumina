"""AWAKENING_PHYSICS_TAPE: PRICE process so enricher recovers TREND_*. Not oracle stamp."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
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
# Pinned a priori BEFORE looking at holdout counts.
PHYSICS_SEED = 20260908
PHYSICS_START_ET = datetime(2026, 4, 6, 18, 0, tzinfo=ET)
PHYSICS_START_ET_ISO = "2026-04-06T18:00:00-04:00"
PHYSICS_HOLD_PCT = 0.40
PHYSICS_DAYS = 90
PHYSICS_RTH_SEC = 10
PHYSICS_ETH_SEC = 60
PHYSICS_DRIFT_RTH = 0.00012
PHYSICS_DRIFT_ETH = 0.00003
PHYSICS_RANGE_KAPPA = 0.04
PHYSICS_PHASE_BLOCKS = 6
MIN_TREND_UP_FRAC = 0.25
MIN_TREND_DOWN_FRAC = 0.25
PHYSICS_TIMESTEPS = 10_000
TRAIN_SEED = 20260908
DELTA_MEAN_R_MIN = 0.05
HOLE_BLOW_MAX = 5
MAX_ATTEMPTS = 3
MIN_HOLDOUT_TICKS = 80_000
MIN_TICKS_PER_LEG = 40_000
FAMILY = "AWAKENING_MARK_EYES"
BASELINE_SHA256 = "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b"
ORIGIN_EYES_ZIP = GENESIS_ART / "genesis_mark_eyes_pi_star.zip"
BASELINE_ZIP_NAME = "baseline_a9ffa852_pi_star.zip"
CHILD_ZIP_NAME = "awakening_physics_v1_pi_star.zip"
CHILD_META_NAME = "awakening_physics_v1_pi_star.json"
CHILD_SCHEMA = "awakening_physics_v1_pi_star_v1"
SOURCE = "awakening_physics_tape"
FLAGS_NAME = "awakening_physics_flags.json"
PHYSICS_ROOT = REPO_ROOT / "reports" / "awakening_physics_run"
PHYSICS_WORK = PHYSICS_ROOT / "workspace"
PHYSICS_ART = PHYSICS_ROOT / "artifacts"
FORBIDDEN_TAPE_PREFIXES = ("5726ae7e", "e963d1ce", "afcea4fa", "5e7eae98", "7e86c2bb")
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
# Six longer blocks vs 18%3 flicker. Holdout (last 40%) still sees both trends + RANGE.
_BLOCK_ORDER = ("TREND_UP", "TREND_DOWN", "TREND_UP", "NEUTRAL", "TREND_UP", "TREND_DOWN")
assert POLICY_EDGE_MIN_TRADES == 150
assert MARK_EYES_OBS_DIM == 46
assert PHYSICS_DRIFT_RTH == 0.00012
assert MIN_TREND_UP_FRAC == 0.25
assert MIN_TREND_DOWN_FRAC == 0.25


class PhysicsProtocolError(RuntimeError):
    """AWAKENING_PHYSICS_TAPE protocol crime (fail-closed)."""


@dataclass(frozen=True, slots=True)
class PhysicsTapeSpec:
    seed: int = PHYSICS_SEED
    hold_pct: float = PHYSICS_HOLD_PCT
    days: int = PHYSICS_DAYS
    rth_sec: int = PHYSICS_RTH_SEC
    eth_sec: int = PHYSICS_ETH_SEC
    drift_rth: float = PHYSICS_DRIFT_RTH
    drift_eth: float = PHYSICS_DRIFT_ETH
    range_kappa: float = PHYSICS_RANGE_KAPPA
    phase_blocks: int = PHYSICS_PHASE_BLOCKS
    shock: float = 0.00022


def a_priori_spec() -> PhysicsTapeSpec:
    return PhysicsTapeSpec()


def attempt_specs() -> tuple[PhysicsTapeSpec, ...]:
    base = a_priori_spec()
    return (
        base,
        replace(base, drift_rth=0.00018, drift_eth=0.000045, range_kappa=0.02),
        replace(base, drift_rth=0.00024, drift_eth=0.00006, range_kappa=0.01, shock=0.00030),
    )


def intended_for_price(i: int, n: int, n_blocks: int) -> str:
    """Price-process phase only. Never written to tick['regime']."""
    blocks = max(1, int(n_blocks))
    idx = min(blocks - 1, int((i / max(1, n)) * blocks))
    return _BLOCK_ORDER[idx % len(_BLOCK_ORDER)]


def generate_physics_tape_ticks(spec: PhysicsTapeSpec | None = None) -> list[dict[str, Any]]:
    spec = spec or a_priori_spec()
    stamps = _iter_session_times(
        start_et=PHYSICS_START_ET,
        calendar_days=spec.days,
        rth_bar_seconds=spec.rth_sec,
        eth_bar_seconds=spec.eth_sec,
    )
    if len(stamps) < 1_000:
        raise PhysicsProtocolError(f"physics fixture too thin: {len(stamps)}")
    rng = np.random.default_rng(spec.seed)
    n = len(stamps)
    price = float(GENESIS_START_PRICE)
    ewma_var = (0.00018) ** 2
    session_anchor = price
    last_et_date = stamps[0].date()
    ticks: list[dict[str, Any]] = []
    prev_ts_utc: datetime | None = None
    # No oracle regime stamp. Price must earn TREND_* via enrich_ticks_for_sim.
    # This generator does not write tick["regime"].
    for i, ts_et in enumerate(stamps):
        if ts_et.date() != last_et_date:
            price = max(1_000.0, price * (1.0 + float(rng.standard_t(5) * 0.003)))
            session_anchor = price
            last_et_date = ts_et.date()
            ewma_var = min(ewma_var * 1.4, 4e-7)
        rth = _is_rth(ts_et)
        minutes = ts_et.hour * 60 + ts_et.minute
        near_open = rth and (9 * 60 + 30) <= minutes < (9 * 60 + 40)
        near_close = rth and (15 * 60 + 50) <= minutes < (16 * 60)
        intended = intended_for_price(i, n, spec.phase_blocks)
        shock = float(rng.standard_t(5))
        ewma_var = 0.94 * ewma_var + 0.06 * (shock * spec.shock) ** 2
        sigma = math.sqrt(max(ewma_var, 1e-10))
        if not rth:
            sigma *= 0.55
        if near_open:
            sigma *= 1.8
        if intended == "TREND_UP":
            ret = (spec.drift_rth if rth else spec.drift_eth) + sigma * shock
        elif intended == "TREND_DOWN":
            ret = -(spec.drift_rth if rth else spec.drift_eth) + sigma * shock
        else:
            ret = -spec.range_kappa * math.log(max(price, 1.0) / max(session_anchor, 1.0)) + sigma * shock
        price = max(1_000.0, _round_tick(price * (1.0 + ret)))
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
    return ticks


def count_regimes_post_enrich(ticks: list[dict[str, Any]]) -> dict[str, int]:
    """counts use post-enrich regime — never intended pre-enrich labels."""
    counts: dict[str, int] = {}
    for row in ticks:
        key = str(row.get("regime") or "NEUTRAL").upper()
        counts[key] = counts.get(key, 0) + 1
    return counts


def trend_fracs(counts: dict[str, int]) -> tuple[float, float]:
    n = max(1, sum(int(v) for v in counts.values()))
    return counts.get("TREND_UP", 0) / n, counts.get("TREND_DOWN", 0) / n


def world_ok_fracs(*, train_up: float, train_down: float, hold_up: float, hold_down: float) -> bool:
    return (
        train_up >= MIN_TREND_UP_FRAC
        and train_down >= MIN_TREND_DOWN_FRAC
        and hold_up >= MIN_TREND_UP_FRAC
        and hold_down >= MIN_TREND_DOWN_FRAC
    )


def refuse_this_tape_hash(sha: str) -> str:
    text = str(sha or "").strip().lower()
    if text.startswith(FORBIDDEN_TAPE_PREFIXES):
        raise PhysicsProtocolError(f"refused old tape hash {text[:16]} as THIS exam tape")
    return text


def assert_forbidden_init(path: Path | str, sha: str = "") -> Path:
    target = Path(path)
    text = str(sha or "").strip().lower()
    posix = str(target).replace("\\", "/")
    if text[:8] in FORBIDDEN_INIT_SHA16:
        raise PhysicsProtocolError(f"refused forbidden init sha {text[:8]}")
    if target.name in FORBIDDEN_INIT_NAMES or is_gitignored_ppo_zip(target) or "/lumina_agents/ppo/" in f"/{posix}":
        raise PhysicsProtocolError(f"refused forbidden init {target.name}")
    return target


def write_bytes_sha(path: Path) -> str:
    digest = file_sha256(path)
    path.with_name(path.name + ".sha256").write_text(digest + "\n", encoding="utf-8")
    return digest


def _cloud_spec(spec: PhysicsTapeSpec) -> CloudFixtureSpec:
    return CloudFixtureSpec(
        instrument=GENESIS_INSTRUMENT,
        calendar_days=int(spec.days),
        holdout_pct=float(spec.hold_pct),
        start_price=float(GENESIS_START_PRICE),
        seed=int(spec.seed),
        start_et=PHYSICS_START_ET,
        rth_bar_seconds=int(spec.rth_sec),
        eth_bar_seconds=int(spec.eth_sec),
    )


def _attempt_row(spec: PhysicsTapeSpec, train_up: float, train_down: float, hold_up: float, hold_down: float) -> dict[str, Any]:
    return {
        "seed": int(spec.seed),
        "drift_rth": float(spec.drift_rth),
        "drift_eth": float(spec.drift_eth),
        "range_kappa": float(spec.range_kappa),
        "phase_blocks": int(spec.phase_blocks),
        "shock": float(spec.shock),
        "train_trend_up_frac": float(train_up),
        "train_trend_down_frac": float(train_down),
        "holdout_trend_up_frac": float(hold_up),
        "holdout_trend_down_frac": float(hold_down),
    }


def persist_physics_fixture(work: Path, art: Path) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    payload: dict[str, Any] = {}
    world_ok = False
    for spec in attempt_specs()[:MAX_ATTEMPTS]:
        raw = generate_physics_tape_ticks(spec)
        if any("regime" in row for row in raw):
            raise PhysicsProtocolError("generator must not write tick['regime']")
        result = persist_cloud_fixture(work, spec=_cloud_spec(spec), ticks=raw)
        train = list(result.split.train)
        holdout = list(result.split.holdout)
        tr_c, ho_c = count_regimes_post_enrich(train), count_regimes_post_enrich(holdout)
        train_up, train_down = trend_fracs(tr_c)
        hold_up, hold_down = trend_fracs(ho_c)
        attempts.append(_attempt_row(spec, train_up, train_down, hold_up, hold_down))
        payload = dict(result.fixture_manifest)
        payload.update(
            {
                "real_data_pct": float(real_data_percentage(result.ticks)),
                "host_real_data_pct": float(host_real_data_pct(result.ticks, certified_cache=True)),
                "fixture_seed": PHYSICS_SEED,
                "start_et": PHYSICS_START_ET_ISO,
                "source": SOURCE_LABEL,
                "train_regime_counts": tr_c,
                "holdout_regime_counts": ho_c,
                "trend_up_frac": float(hold_up),
                "trend_down_frac": float(hold_down),
                "trend_up_frac_train": float(train_up),
                "trend_down_frac_train": float(train_down),
                "trend_up_frac_holdout": float(hold_up),
                "trend_down_frac_holdout": float(hold_down),
                "attempts": list(attempts),
                "ticks_per_leg": [len(x) for x in split_holdout_ab(holdout)],
                "world_ok": False,
            }
        )
        world_ok = world_ok_fracs(train_up=train_up, train_down=train_down, hold_up=hold_up, hold_down=hold_down)
        payload["world_ok"] = bool(world_ok)
        if world_ok:
            break
    refuse_this_tape_hash(str(payload.get("hash") or ""))
    if float(payload.get("real_data_pct") or 0.0) != 0.0:
        raise PhysicsProtocolError("real_data_percentage must be 0.0")
    if int(payload.get("holdout_tick_count") or 0) < MIN_HOLDOUT_TICKS:
        raise PhysicsProtocolError("holdout < 80k")
    legs = list(payload.get("ticks_per_leg") or [])
    if len(legs) != 2 or int(legs[0]) < MIN_TICKS_PER_LEG or int(legs[1]) < MIN_TICKS_PER_LEG:
        raise PhysicsProtocolError("each chronological half must be >= 40000")
    sidecar = art / "01_physics_fixture_manifest.json"
    write_fixture_sidecar(sidecar, payload)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def load_physics_train_split(work: Path) -> dict[str, Any]:
    split = load_split_cache(work, holdout_pct=PHYSICS_HOLD_PCT)
    if split is None or not split.train:
        raise PhysicsProtocolError("physics train split missing")
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


def inspect_physics_protocol() -> dict[str, Any]:
    rel = "lumina_core/birth/awakening_physics_tape.py"
    sites = {
        "physics_drift_rth": (rel, "PHYSICS_DRIFT_RTH = 0.00012"),
        "min_trend_up_frac": (rel, "MIN_TREND_UP_FRAC = 0.25"),
        "min_trend_down_frac": (rel, "MIN_TREND_DOWN_FRAC = 0.25"),
        "counts_post_enrich": (rel, "counts use post-enrich regime"),
        "no_oracle_stamp": (rel, "No oracle regime stamp"),
        "scratch_init": ("lumina_core/birth/awakening_physics_train.py", "init_policy must be scratch"),
        "forbidden_hashes": (rel, "5e7eae98"),
        "floor_150": ("lumina_core/birth/foundation_metrics.py", "POLICY_EDGE_MIN_TRADES = 150"),
        "license_both_legs": ("lumina_core/birth/awakening_physics_flags.py", "license both legs"),
        "genesis_eyes_ok_forced_false": (
            "lumina_core/birth/awakening_physics_flags.py",
            "GENESIS_EYES_OK forced false",
        ),
        "hooks_default_false": (
            "lumina_core/birth/awakening_path_exit_k3.py",
            'ContextVar("path_exit_k3_shadow", default=False)',
        ),
        "hooks_shape_default_false": (
            "lumina_core/birth/awakening_path_shape_k3_dead.py",
            'ContextVar("path_shape_k3_shadow", default=False)',
        ),
        "honesty_synthetic_0": ("lumina_core/birth/data_source_honesty.py", "synthetic_cloud_fixture"),
    }
    dump: dict[str, Any] = {k: f"{p}:{_line_of(p, n)}" for k, (p, n) in sites.items()}
    dump["missing_sites"] = [k for k, v in dump.items() if str(v).endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump
