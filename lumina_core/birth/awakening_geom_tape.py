"""G1: SCALE physics, NEW seeds 20260923-25, start_et 2025-08-04T18:00 ET. DRIFT_RTH==8.0e-6."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lumina_core.birth.awakening_band_tape import decide_world_ok, tape_in_band
from lumina_core.birth.awakening_geom_reward import GeomProtocolError
from lumina_core.birth.awakening_mark_eyes import MARK_EYES_OBS_DIM
from lumina_core.birth.awakening_occupancy_tape import count_regimes_post_enrich, trend_fracs, world_ok_fracs
from lumina_core.birth.awakening_scale_enrich import PHYSICS_SLOPE_ABS, PROD_SLOPE_ABS, ScaleProtocolError, enrich_ticks_for_scale
from lumina_core.birth.awakening_scale_tape import (
    BASELINE_SHA256,
    DRIFT_RTH,
    FORBIDDEN_TAPE_PREFIXES,
    NQ_MAX,
    NQ_MIN,
    ORIGIN_EYES_ZIP,
    PHASE_BLOCKS,
    SCALE_DAYS,
    SCALE_ETH_SEC,
    SCALE_RTH_SEC,
    START,
    generate_scale_tape_ticks,
)
from lumina_core.birth.awakening_strat_split import SPLITTER_NAME, STRAT_HOLD_PCT, split_per_phase_60_40
from lumina_core.birth.birth_exit_policy_export import is_gitignored_ppo_zip
from lumina_core.birth.data_source_honesty import host_real_data_pct, real_data_percentage
from lumina_core.birth.foundation_history import FOUNDATION_HISTORY_START_DAYS
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import GENESIS_INSTRUMENT, REPO_ROOT
from lumina_core.birth.genesis_mark_eyes_eval import split_holdout_ab
from lumina_core.birth.history_loader import actual_calendar_days_from_ticks
from lumina_core.birth.purged_split import PurgedSplit
from lumina_core.birth.synthetic_cloud_fixture import SOURCE_LABEL, write_fixture_sidecar
from lumina_core.birth.tick_cache_persist import (
    compute_ticks_fingerprint,
    load_cache_manifest,
    load_split_cache,
    save_birth_data_cache,
)
from lumina_core.rl.trend_features import ENRICH_VERSION

ET = ZoneInfo("America/New_York")
GEOM_SEEDS = (20260923, 20260924, 20260925)
GEOM_START_ET = datetime(2025, 8, 4, 18, 0, tzinfo=ET)
GEOM_START_ET_ISO = GEOM_START_ET.isoformat()
GEOM_TIMESTEPS = 10_000
MIN_TREND_UP_FRAC = MIN_TREND_DOWN_FRAC = 0.25
MIN_HOLDOUT_TICKS, MIN_TICKS_PER_LEG = 80_000, 40_000
BASELINE_ZIP_NAME = "baseline_a9ffa852_pi_star.zip"
CHILD_ZIP_NAME = "awakening_geom_v1_pi_star.zip"
CHILD_META_NAME = "awakening_geom_v1_pi_star.json"
CHILD_SCHEMA = "awakening_geom_v1_pi_star_v1"
FLAGS_NAME = "awakening_geom_flags.json"
GEOM_ROOT = REPO_ROOT / "reports" / "awakening_geom_run"
GEOM_WORK, GEOM_ART = GEOM_ROOT / "workspace", GEOM_ROOT / "artifacts"
SCALE_TAPE_HASH = "c9188a030e38e4bc"
FORBIDDEN_INIT_SHA16 = frozenset(
    {"a9ffa852", "b83d2b67", "cf70ae5b", "a8a93d6e", "cebe1804", "1123282f", "8cc435c6"}
)
FORBIDDEN_INIT_NAMES = frozenset(
    {
        "genesis_mark_eyes_pi_star.zip",
        "baseline_a9ffa852_pi_star.zip",
        "awakening_scale_v1_pi_star.zip",
        "awakening_drift_v1_pi_star.zip",
        "awakening_band_v1_pi_star.zip",
        "awakening_obj_v1_pi_star.zip",
        "awakening_conv_v1_pi_star.zip",
        "awakening_strat_v1_pi_star.zip",
        "awakening_occupancy_v1_pi_star.zip",
        "awakening_mark_eyes_v2_pi_star.zip",
        "awakening_mark_eyes_polish_pi_star.zip",
        "awakening_mark_eyes_pi_star.zip",
        "birth_exit_pi_star.zip",
        "genesis_birth_exit_pi_star.zip",
    }
)
assert POLICY_EDGE_MIN_TRADES == 150 and MARK_EYES_OBS_DIM == 46
assert DRIFT_RTH == 8.0e-6 and PHASE_BLOCKS == 6 and len(GEOM_SEEDS) == 3
assert PHYSICS_SLOPE_ABS == 0.004 and PROD_SLOPE_ABS == 0.15
assert NQ_MIN == 12000.0 and NQ_MAX == 28000.0


def next_geom_seed(attempts: list[dict[str, Any]]) -> int | None:
    if len(attempts) >= 3:
        return None
    return int(GEOM_SEEDS[len(attempts)])


def refuse_this_tape_hash(sha: str) -> str:
    text = str(sha or "").strip().lower()
    extras = (SCALE_TAPE_HASH[:8],) + _prior_disk_hash_prefixes()
    if text.startswith(FORBIDDEN_TAPE_PREFIXES) or text.startswith(extras) or text.startswith(SCALE_TAPE_HASH):
        raise GeomProtocolError(f"refused old tape hash {text[:16]} as THIS exam tape")
    return text


def _prior_disk_hash_prefixes() -> tuple[str, ...]:
    extras: list[str] = []
    roots = (
        "reports/awakening_scale_run/artifacts/awakening_scale_flags.json",
        "reports/awakening_scale_run/artifacts/01_scale_fixture_manifest.json",
        "reports/awakening_drift_run/artifacts/awakening_drift_flags.json",
        "reports/awakening_band_run/artifacts/awakening_band_flags.json",
        "reports/awakening_obj_run/artifacts/awakening_obj_flags.json",
        "reports/awakening_conv_run/artifacts/awakening_conv_flags.json",
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
        raise GeomProtocolError(f"refused forbidden init sha {text[:8]}")
    if target.name in FORBIDDEN_INIT_NAMES or is_gitignored_ppo_zip(target) or "/lumina_agents/ppo/" in f"/{posix}":
        raise GeomProtocolError(f"refused forbidden init {target.name}")
    return target


def generate_geom_tape_ticks(*, seed: int) -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    try:
        return generate_scale_tape_ticks(seed=int(seed), start_price=START, drift_rth=DRIFT_RTH, start_et=GEOM_START_ET)
    except ScaleProtocolError as exc:
        raise GeomProtocolError(str(exc)) from exc


def try_geom_seeds() -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    for seed in GEOM_SEEDS:
        ticks, labels, gen_counts = generate_geom_tape_ticks(seed=int(seed))
        in_band, mn, mx = tape_in_band(ticks)
        attempts.append({"seed": int(seed), "min": float(mn), "max": float(mx), "in_band": bool(in_band)})
        if in_band:
            return {
                "ticks": ticks, "labels": labels, "gen_counts": gen_counts, "attempts": attempts,
                "seed_used": int(seed), "in_band": True, "price_min": float(mn), "price_max": float(mx),
            }
    last = attempts[-1]
    return {
        "ticks": [], "labels": [], "gen_counts": {}, "attempts": attempts, "seed_used": 0,
        "in_band": False, "price_min": float(last["min"]), "price_max": float(last["max"]),
    }


def persist_geom_fixture(work: Path, art: Path) -> dict[str, Any]:
    probe = try_geom_seeds()
    art.mkdir(parents=True, exist_ok=True)
    base = {
        "seed_used": int(probe.get("seed_used") or 0), "attempts": list(probe.get("attempts") or []),
        "price_min": float(probe.get("price_min") or 0.0), "price_max": float(probe.get("price_max") or 0.0),
        "in_band": bool(probe.get("in_band")), "world_ok": False,
        "train_up_frac": 0.0, "train_down_frac": 0.0, "hold_up_frac": 0.0, "hold_down_frac": 0.0,
        "hash": "", "source": SOURCE_LABEL, "real_data_pct": 0.0, "drift_rth": float(DRIFT_RTH),
        "slope_abs_used": float(PHYSICS_SLOPE_ABS), "prod_slope_abs": float(PROD_SLOPE_ABS),
        "phase_blocks": int(PHASE_BLOCKS), "splitter": SPLITTER_NAME, "start_et": GEOM_START_ET_ISO,
        "start_price": float(START), "nq_min": float(NQ_MIN), "nq_max": float(NQ_MAX), "clipped": False,
        "rth_bar_seconds": int(SCALE_RTH_SEC), "eth_bar_seconds": int(SCALE_ETH_SEC),
    }
    if not bool(probe.get("in_band")):
        sidecar = art / "01_geom_fixture_manifest.json"
        write_fixture_sidecar(sidecar, base)
        sidecar.write_text(json.dumps(base, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return base
    raw, phases, gen_counts = list(probe["ticks"]), list(probe["labels"]), dict(probe["gen_counts"])
    cache = work / "state" / "birth_enrichment_cache"
    if cache.is_dir():
        shutil.rmtree(cache)
    raw_hash = compute_ticks_fingerprint(raw)
    enriched = enrich_ticks_for_scale(
        [dict(t) for t in raw], workspace_root=work, raw_ticks_hash=raw_hash, enrich_version=ENRICH_VERSION
    )
    for row in enriched:
        row["source"] = SOURCE_LABEL
        row.pop("gen_phase", None)
    if any("gen_phase" in row for row in enriched):
        raise GeomProtocolError("generator phase side-channel must be stripped before persist")
    split = split_per_phase_60_40(enriched, phases)
    tr_c, ho_c = count_regimes_post_enrich(split.train), count_regimes_post_enrich(split.holdout)
    train_up, train_down = trend_fracs(tr_c)
    hold_up, hold_down = trend_fracs(ho_c)
    from lumina_core.birth.data_pipeline_types import train_hash as _train_hash

    t_hash = refuse_this_tape_hash(_train_hash(split.train))
    actual_days = actual_calendar_days_from_ticks(enriched)
    days = {str(row.get("timestamp") or "")[:10] for row in split.holdout}
    train_days = {str(row.get("timestamp") or "")[:10] for row in split.train}
    purged = PurgedSplit(train=list(split.train), holdout=list(split.holdout), holdout_days=len(days), train_days=len(train_days))
    paths = save_birth_data_cache(
        work, ticks=enriched, split=purged, holdout_pct=float(STRAT_HOLD_PCT), raw_ticks_hash=raw_hash,
        train_hash=t_hash, enrich_version=ENRICH_VERSION,
        requested_days=max(FOUNDATION_HISTORY_START_DAYS, SCALE_DAYS), actual_calendar_days=actual_days,
        instruments=[GENESIS_INSTRUMENT], stitched=False, stitched_from=[],
    )
    fracs_ok = world_ok_fracs(train_up=train_up, train_down=train_down, hold_up=hold_up, hold_down=hold_down)
    world_ok = decide_world_ok(in_band=True, fracs_ok=fracs_ok, clipped=False)
    legs = [len(x) for x in split_holdout_ab(split.holdout)]
    payload = {
        **base, "symbol": GENESIS_INSTRUMENT, "days": actual_days,
        "requested_days": max(FOUNDATION_HISTORY_START_DAYS, SCALE_DAYS),
        "tick_count": len(enriched), "train_tick_count": len(split.train), "holdout_tick_count": len(split.holdout),
        "gen_counts": dict(gen_counts), "train_regime_counts": tr_c, "holdout_regime_counts": ho_c,
        "train_up_frac": float(train_up), "train_down_frac": float(train_down),
        "hold_up_frac": float(hold_up), "hold_down_frac": float(hold_down),
        "hash": t_hash, "raw_ticks_hash": raw_hash, "real_data_pct": float(real_data_percentage(enriched)),
        "host_real_data_pct": float(host_real_data_pct(enriched, certified_cache=True)),
        "ticks_per_leg": legs, "path": paths["cache_manifest_path"],
        "ticks_path": paths["ticks_cache_path"], "split_path": paths["split_cache_path"],
        "world_ok": bool(world_ok), "in_band": True,
    }
    if float(payload["real_data_pct"]) != 0.0:
        raise GeomProtocolError("real_data_percentage must be 0.0")
    if int(payload["holdout_tick_count"]) < MIN_HOLDOUT_TICKS or len(legs) != 2 or min(legs) < MIN_TICKS_PER_LEG:
        raise GeomProtocolError("holdout/leg density failed")
    sidecar = art / "01_geom_fixture_manifest.json"
    write_fixture_sidecar(sidecar, payload)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def load_geom_train_split(work: Path) -> dict[str, Any]:
    split = load_split_cache(work, holdout_pct=STRAT_HOLD_PCT)
    if split is None or not split.train:
        raise GeomProtocolError("geom train split missing")
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


def inspect_geom_protocol() -> dict[str, Any]:
    sites = {
        "target_frac_min_010": ("lumina_core/birth/awakening_geom_touch.py", "TARGET_FRAC_MIN==0.10"),
        "geom_win_r_121": ("lumina_core/birth/awakening_geom_reward.py", "GEOM_WIN_R==1.21"),
        "geom_loss_r_104": ("lumina_core/birth/awakening_geom_reward.py", "GEOM_LOSS_R==-1.04"),
        "learn_skipped_unhittable": ("lumina_core/birth/awakening_geom_train.py", "learn skipped when unhittable"),
        "prod_slope_015": ("lumina_core/birth/awakening_scale_enrich.py", "prod default 0.15"),
        "drift_8e_6": ("lumina_core/birth/awakening_geom_tape.py", "DRIFT_RTH==8.0e-6"),
        "force_open_train_only": ("lumina_core/birth/awakening_mark_eyes_env.py", "FORCE_OPEN true only on train factory"),
        "floor_150": ("lumina_core/birth/foundation_metrics.py", "POLICY_EDGE_MIN_TRADES = 150"),
        "world_engineering_closed_true": ("lumina_core/birth/awakening_geom_flags.py", "world_engineering_closed true"),
        "genesis_eyes_ok_false": ("lumina_core/birth/awakening_geom_flags.py", "GENESIS_EYES_OK false"),
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
    "DRIFT_RTH",
    "FLAGS_NAME",
    "GEOM_ART",
    "GEOM_ROOT",
    "GEOM_SEEDS",
    "GEOM_START_ET",
    "GEOM_START_ET_ISO",
    "GEOM_TIMESTEPS",
    "GEOM_WORK",
    "ORIGIN_EYES_ZIP",
    "assert_forbidden_init",
    "inspect_geom_protocol",
    "load_geom_train_split",
    "next_geom_seed",
    "persist_geom_fixture",
    "refuse_this_tape_hash",
]
