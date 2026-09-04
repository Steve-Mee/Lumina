"""AWAKENING_MARK_EYES_V2 protocol: new 48-dim eyes, scratch body, NEW tape.

One 10k PPO.learn() from scratch. Not polish. Not PPO.load(a9ffa852). Floor 150.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lumina_core.birth.awakening_mark_eyes import HOLD_NORM, MARK_EYES_OBS_DIM
from lumina_core.birth.birth_exit_policy_export import file_sha256, is_gitignored_ppo_zip
from lumina_core.birth.data_source_honesty import host_real_data_pct, real_data_percentage
from lumina_core.birth.foundation_history import FOUNDATION_HISTORY_START_DAYS
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import GENESIS_ART, GENESIS_INSTRUMENT, GENESIS_START_PRICE, REPO_ROOT
from lumina_core.birth.genesis_cloud_workspace import overlay_sim_config
from lumina_core.birth.genesis_mark_eyes_eval import split_holdout_ab
from lumina_core.birth.synthetic_cloud_fixture import SOURCE_LABEL, CloudFixtureSpec, persist_cloud_fixture, write_fixture_sidecar
from lumina_core.birth.tick_cache_persist import load_cache_manifest, load_split_cache, load_ticks_cache

FAMILY = "AWAKENING_MARK_EYES_V2"
MARK_EYES_V2_OBS_DIM = 48
MARK_EYES_V2_EXTRA = 5
V2_TIMESTEPS = 10_000
TRAIN_SEED = 20260907
FIXTURE_SEED = 20260907
V2_START_ET_ISO = "2026-05-04T18:00:00-04:00"
V2_HOLDOUT_PCT = 0.40
MIN_HOLDOUT_TICKS = 80_000
MIN_TICKS_PER_LEG = 40_000
DELTA_MEAN_R_MIN = 0.05
HOLE_BLOW_MAX = 5
BASELINE_SHA256 = "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b"
ORIGIN_EYES_ZIP = GENESIS_ART / "genesis_mark_eyes_pi_star.zip"
BASELINE_ZIP_NAME = "baseline_mark_eyes_v1_pi_star.zip"
CHILD_ZIP_NAME = "awakening_mark_eyes_v2_pi_star.zip"
CHILD_META_NAME = "awakening_mark_eyes_v2_pi_star.json"
CHILD_SCHEMA = "awakening_mark_eyes_v2_pi_star_v1"
SOURCE = "awakening_mark_eyes_v2"
FLAGS_NAME = "awakening_mark_eyes_v2_flags.json"
EXTRA_SLOT_NAMES = (
    "mark_unreal_r",
    "mark_mae_r",
    "bars_held_norm",
    "mark_mfe_r",
    "mark_d_unreal",
)
FORBIDDEN_TAPE_HASHES = frozenset(
    {"5726ae7e83ff3d48", "e963d1ce7d726ebf", "afcea4fa72734337", "7e86c2bb1c71d514"}
)
FORBIDDEN_TAPE_PREFIXES = ("5726ae7e", "e963d1ce", "afcea4fa", "7e86c2bb")
FORBIDDEN_INIT_SHA16 = frozenset({"a9ffa852", "cebe1804", "8cc435c6", "d313b107", "53df2d78"})
FORBIDDEN_INIT_NAMES = frozenset(
    {
        "genesis_mark_eyes_pi_star.zip",
        "baseline_mark_eyes_v1_pi_star.zip",
        "awakening_mark_eyes_polish_pi_star.zip",
        "init_mark_eyes_pi_star.zip",
        "birth_exit_pi_star.zip",
        "genesis_birth_exit_pi_star.zip",
        "awakening_mark_eyes_pi_star.zip",
    }
)
FORBIDDEN_BASELINE_NAMES = frozenset(
    {
        "path_early_A_close_ledger.jsonl",
        "path_early_B_close_ledger.jsonl",
        "budget_eyes_A_close_ledger.jsonl",
        "budget_eyes_B_close_ledger.jsonl",
        "genesis_mark_eyes_A_close_ledger.jsonl",
        "genesis_mark_eyes_B_close_ledger.jsonl",
        "polish_base_A_close_ledger.jsonl",
        "polish_base_B_close_ledger.jsonl",
        "polish_child_A_close_ledger.jsonl",
        "polish_child_B_close_ledger.jsonl",
    }
)
V2_ROOT = REPO_ROOT / "reports" / "awakening_eyes_v2_run"
V2_WORK = V2_ROOT / "workspace"
V2_ART = V2_ROOT / "artifacts"
ET = ZoneInfo("America/New_York")
assert POLICY_EDGE_MIN_TRADES == 150
assert MARK_EYES_V2_OBS_DIM == 48
assert MARK_EYES_V2_EXTRA == 5
assert MARK_EYES_OBS_DIM == 46
assert HOLD_NORM == 120.0


class MarkEyesV2ProtocolError(RuntimeError):
    """AWAKENING_MARK_EYES_V2 protocol crime (fail-closed)."""


def refuse_this_tape_hash(sha: str) -> str:
    text = str(sha or "").strip().lower()
    if not text:
        return text
    if text.startswith(FORBIDDEN_TAPE_PREFIXES) or text in FORBIDDEN_TAPE_HASHES:
        raise MarkEyesV2ProtocolError(f"refused old tape hash {text[:16]} as THIS exam tape")
    return text


def assert_forbidden_init(path: Path | str, sha: str = "") -> Path:
    """Refuse every named zip / sha in §1 as train init. Scratch only."""
    target = Path(path)
    name = target.name
    text = str(sha or "").strip().lower()
    posix = str(target).replace("\\", "/")
    if text[:8] in FORBIDDEN_INIT_SHA16:
        raise MarkEyesV2ProtocolError(f"refused forbidden init sha {text[:8]}")
    if name in FORBIDDEN_INIT_NAMES or is_gitignored_ppo_zip(target) or "/lumina_agents/ppo/" in f"/{posix}":
        raise MarkEyesV2ProtocolError(f"refused forbidden init {name}")
    return target


def refuse_old_baseline(path: Path | str | None = None) -> None:
    if path is None:
        return
    name = Path(path).name
    if name in FORBIDDEN_BASELINE_NAMES or "path_early" in name or "budget_" in name or "polish_" in name:
        raise MarkEyesV2ProtocolError(f"refused old exam paper as baseline: {name}")


def write_bytes_sha(path: Path) -> str:
    digest = file_sha256(path)
    path.with_name(path.name + ".sha256").write_text(digest + "\n", encoding="utf-8")
    return digest


def copy_baseline_zip(art: Path) -> str:
    """Read-only copy of a9ffa852. NEVER a PPO.learn init."""
    art.mkdir(parents=True, exist_ok=True)
    if not ORIGIN_EYES_ZIP.is_file():
        raise MarkEyesV2ProtocolError("frozen living MARK_EYES zip missing")
    dest = art / BASELINE_ZIP_NAME
    shutil.copy2(ORIGIN_EYES_ZIP, dest)
    digest = write_bytes_sha(dest)
    if digest != BASELINE_SHA256:
        raise MarkEyesV2ProtocolError(f"baseline sha must be a9ffa852 pin, got {digest[:16]}")
    return digest


def origin_guard_paths(*, repo: Path | None = None) -> dict[str, Path]:
    root = repo or REPO_ROOT
    genesis = root / "reports" / "genesis_cloud_run" / "artifacts"
    budget = root / "reports" / "genesis_budget_run" / "artifacts"
    polish = root / "reports" / "awakening_polish_run" / "artifacts"
    return {
        "genesis_mark_eyes_pi_star.zip": genesis / "genesis_mark_eyes_pi_star.zip",
        "genesis_birth_exit_pi_star.zip": genesis / "genesis_birth_exit_pi_star.zip",
        "genesis_eyes_budget_flags.json": budget / "genesis_eyes_budget_flags.json",
        "awakening_mark_eyes_polish_flags.json": polish / "awakening_mark_eyes_polish_flags.json",
        "awakening_mark_eyes_polish_pi_star.zip": polish / "awakening_mark_eyes_polish_pi_star.zip",
    }


def snapshot_origin_artifacts(*, repo: Path | None = None) -> dict[str, str]:
    return {name: file_sha256(path) if path.is_file() else "" for name, path in origin_guard_paths(repo=repo).items()}


def assert_origin_untouched(before: dict[str, str], *, repo: Path | None = None) -> None:
    after = snapshot_origin_artifacts(repo=repo)
    for name, sha in before.items():
        if sha and after.get(name) != sha:
            raise MarkEyesV2ProtocolError(f"origin artifact overwritten: {name}")


def v2_fixture_spec() -> CloudFixtureSpec:
    start_et = datetime(2026, 5, 4, 18, 0, tzinfo=ET)
    return CloudFixtureSpec(
        instrument=GENESIS_INSTRUMENT,
        calendar_days=int(FOUNDATION_HISTORY_START_DAYS),
        holdout_pct=float(V2_HOLDOUT_PCT),
        start_price=float(GENESIS_START_PRICE),
        seed=int(FIXTURE_SEED),
        start_et=start_et,
        rth_bar_seconds=10,
        eth_bar_seconds=60,
    )


def persist_v2_fixture(work: Path, art: Path) -> dict[str, Any]:
    spec = v2_fixture_spec()
    result = persist_cloud_fixture(work, spec=spec)
    payload = dict(result.fixture_manifest)
    ticks = load_ticks_cache(work)
    payload["real_data_pct"] = float(real_data_percentage(ticks))
    payload["host_real_data_pct"] = float(host_real_data_pct(ticks, certified_cache=True))
    payload["fixture_seed"] = FIXTURE_SEED
    payload["start_et"] = V2_START_ET_ISO
    payload["source"] = SOURCE_LABEL
    split = load_split_cache(work, holdout_pct=float(payload.get("holdout_pct") or V2_HOLDOUT_PCT))
    holdout = list(split.holdout) if split is not None else []
    train = list(split.train) if split is not None else []
    if not train:
        raise MarkEyesV2ProtocolError("train split missing")
    leg_a, leg_b = split_holdout_ab(holdout) if holdout else ([], [])
    payload["ticks_per_leg"] = [len(leg_a), len(leg_b)]
    sidecar = art / "01_v2_fixture_manifest.json"
    write_fixture_sidecar(sidecar, payload)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert_v2_fixture(work, payload)
    return payload


def assert_v2_fixture(work: Path, manifest: dict[str, Any]) -> None:
    if str(manifest.get("source") or "") != SOURCE_LABEL:
        raise MarkEyesV2ProtocolError("fixture source must be synthetic_cloud_fixture")
    ticks = load_ticks_cache(work)
    if real_data_percentage(ticks) != 0.0 or float(manifest.get("real_data_pct") or 0.0) != 0.0:
        raise MarkEyesV2ProtocolError("real_data_percentage must be 0.0")
    host = float(manifest.get("host_real_data_pct") or host_real_data_pct(ticks))
    if host == 100.0:
        raise MarkEyesV2ProtocolError("host_real_data_pct cannot be 100")
    refuse_this_tape_hash(str(manifest.get("hash") or ""))
    if int(manifest.get("holdout_tick_count") or 0) < MIN_HOLDOUT_TICKS:
        raise MarkEyesV2ProtocolError("holdout < 80k")
    if len(list(manifest.get("holdout_regimes") or [])) < 3:
        raise MarkEyesV2ProtocolError("holdout regimes < 3")
    legs = list(manifest.get("ticks_per_leg") or [])
    if len(legs) != 2 or int(legs[0]) < MIN_TICKS_PER_LEG or int(legs[1]) < MIN_TICKS_PER_LEG:
        raise MarkEyesV2ProtocolError("each chronological half must be >= 40000")


def prepare_v2_trees(*, repo: Path | None = None) -> tuple[Path, Path, Path]:
    root = (repo or REPO_ROOT) / "reports" / "awakening_eyes_v2_run"
    work, art, reports = root / "workspace", root / "artifacts", root
    work.mkdir(parents=True, exist_ok=True)
    (work / "state").mkdir(parents=True, exist_ok=True)
    art.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)
    dest = work / "config.yaml"
    shutil.copy2((repo or REPO_ROOT) / "config.yaml", dest)
    overlay_sim_config(dest)
    catalog = (repo or REPO_ROOT) / "lumina_model_catalog.json"
    if catalog.is_file():
        shutil.copy2(catalog, work / "lumina_model_catalog.json")
    return reports, work, art


def load_v2_train_split(work: Path) -> dict[str, Any]:
    split = load_split_cache(work, holdout_pct=V2_HOLDOUT_PCT)
    if split is None or not split.train:
        raise MarkEyesV2ProtocolError("v2 train split missing")
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


def inspect_v2_protocol() -> dict[str, Any]:
    rel = "lumina_core/birth/awakening_mark_eyes_v2.py"
    obs = "lumina_core/birth/awakening_mark_eyes_v2_obs.py"
    train = "lumina_core/birth/awakening_mark_eyes_v2_train.py"
    flags = "lumina_core/birth/awakening_mark_eyes_v2_flags.py"
    honesty = "lumina_core/birth/data_source_honesty.py"
    metrics = "lumina_core/birth/foundation_metrics.py"
    exit_rel = "lumina_core/birth/awakening_path_exit_k3.py"
    shape_rel = "lumina_core/birth/awakening_path_shape_k3_dead.py"
    dump: dict[str, Any] = {
        "mark_eyes_v2_obs_dim_48": f"{rel}:{_line_of(rel, 'MARK_EYES_V2_OBS_DIM = 48')}",
        "extra_length_5": f"{rel}:{_line_of(rel, 'MARK_EYES_V2_EXTRA = 5')}",
        "mfe_is_max_unreal_not_wick": f"{obs}:{_line_of(obs, 'mfe is max unreal, not wick')}",
        "d_unreal_first_bar_0": f"{obs}:{_line_of(obs, 'first in-position bar')}",
        "scratch_init_only": f"{train}:{_line_of(train, 'init_policy must be scratch')}",
        "forbidden_load_a9ffa852": f"{rel}:{_line_of(rel, 'a9ffa852')}",
        "forbidden_load_cebe1804": f"{rel}:{_line_of(rel, 'cebe1804')}",
        "forbidden_load_8cc435c6": f"{rel}:{_line_of(rel, '8cc435c6')}",
        "seed_20260907": f"{rel}:{_line_of(rel, 'TRAIN_SEED = 20260907')}",
        "start_et_2026_05_04": f"{rel}:{_line_of(rel, 'datetime(2026, 5, 4, 18, 0')}",
        "floor_150": f"{metrics}:{_line_of(metrics, 'POLICY_EDGE_MIN_TRADES = 150')}",
        "license_both_legs": f"{flags}:{_line_of(flags, 'license both legs')}",
        "genesis_eyes_ok_forced_false": f"{flags}:{_line_of(flags, 'GENESIS_EYES_OK forced false')}",
        "hooks_default_false": (
            f"{exit_rel}:{_line_of(exit_rel, 'ContextVar(\"path_exit_k3_shadow\", default=False)')}"
        ),
        "hooks_shape_default_false": (
            f"{shape_rel}:{_line_of(shape_rel, 'ContextVar(\"path_shape_k3_shadow\", default=False)')}"
        ),
        "honesty_synthetic_0": f"{honesty}:{_line_of(honesty, 'synthetic_cloud_fixture')}",
    }
    dump["missing_sites"] = [k for k, v in dump.items() if str(v).endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = [
    "BASELINE_SHA256",
    "BASELINE_ZIP_NAME",
    "CHILD_META_NAME",
    "CHILD_SCHEMA",
    "CHILD_ZIP_NAME",
    "DELTA_MEAN_R_MIN",
    "EXTRA_SLOT_NAMES",
    "FAMILY",
    "FIXTURE_SEED",
    "FLAGS_NAME",
    "FORBIDDEN_INIT_NAMES",
    "FORBIDDEN_INIT_SHA16",
    "FORBIDDEN_TAPE_HASHES",
    "HOLE_BLOW_MAX",
    "MARK_EYES_V2_EXTRA",
    "MARK_EYES_V2_OBS_DIM",
    "SOURCE",
    "TRAIN_SEED",
    "V2_ART",
    "V2_HOLDOUT_PCT",
    "V2_ROOT",
    "V2_START_ET_ISO",
    "V2_TIMESTEPS",
    "V2_WORK",
    "MarkEyesV2ProtocolError",
    "assert_forbidden_init",
    "assert_origin_untouched",
    "assert_v2_fixture",
    "copy_baseline_zip",
    "inspect_v2_protocol",
    "load_v2_train_split",
    "persist_v2_fixture",
    "prepare_v2_trees",
    "refuse_old_baseline",
    "refuse_this_tape_hash",
    "snapshot_origin_artifacts",
    "write_bytes_sha",
]
