"""AWAKENING_MARK_EYES_POLISH protocol: continue a9ffa852 on a NEW tape.

One 10k PPO.learn() continue. Not Birth. Not Proof. Floor 150. REAL door locked.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lumina_core.birth.birth_exit_policy_export import file_sha256
from lumina_core.birth.data_source_honesty import host_real_data_pct, real_data_percentage
from lumina_core.birth.foundation_history import FOUNDATION_HISTORY_START_DAYS
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import GENESIS_ART, GENESIS_INSTRUMENT, GENESIS_START_PRICE, REPO_ROOT
from lumina_core.birth.genesis_cloud_workspace import overlay_sim_config
from lumina_core.birth.genesis_mark_eyes_eval import split_holdout_ab
from lumina_core.birth.synthetic_cloud_fixture import SOURCE_LABEL, CloudFixtureSpec, persist_cloud_fixture, write_fixture_sidecar
from lumina_core.birth.tick_cache_persist import load_cache_manifest, load_split_cache, load_ticks_cache

POLISH_FIXTURE_SEED = 20260906
POLISH_TRAIN_SEED = 20260906
POLISH_START_ET_ISO = "2026-08-03T18:00:00-04:00"
POLISH_HOLDOUT_PCT = 0.40
POLISH_TIMESTEPS = 10_000
MIN_HOLDOUT_TICKS = 80_000
MIN_TICKS_PER_LEG = 40_000
DELTA_MEAN_R_MIN = 0.05
HOLE_BLOW_MAX = 5
INIT_SHA256 = "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b"
ORIGIN_EYES_ZIP = GENESIS_ART / "genesis_mark_eyes_pi_star.zip"
INIT_ZIP_NAME = "init_mark_eyes_pi_star.zip"
CHILD_ZIP_NAME = "awakening_mark_eyes_polish_pi_star.zip"
CHILD_META_NAME = "awakening_mark_eyes_polish_pi_star.json"
FORBIDDEN_TAPE_HASHES = frozenset({"5726ae7e83ff3d48", "e963d1ce7d726ebf", "7e86c2bb1c71d514"})
FORBIDDEN_INIT_SHA16 = frozenset({"8cc435c6", "d313b107", "53df2d78"})
FORBIDDEN_INIT_NAMES = frozenset(
    {
        "birth_exit_pi_star.zip",
        "genesis_birth_exit_pi_star.zip",
        "awakening_mark_eyes_pi_star.zip",
    }
)
FORBIDDEN_BASELINE_NAMES = frozenset(
    {
        "path_early_A_close_ledger.jsonl",
        "path_early_B_close_ledger.jsonl",
        "budget_birth_A_close_ledger.jsonl",
        "budget_birth_B_close_ledger.jsonl",
        "budget_eyes_A_close_ledger.jsonl",
        "budget_eyes_B_close_ledger.jsonl",
        "genesis_mark_eyes_A_close_ledger.jsonl",
        "genesis_mark_eyes_B_close_ledger.jsonl",
    }
)
ORIGIN_GUARD_NAMES = (
    "genesis_mark_eyes_pi_star.zip",
    "genesis_birth_exit_pi_star.zip",
    "genesis_eyes_budget_flags.json",
    "budget_eyes_A_close_ledger.jsonl",
    "budget_eyes_B_close_ledger.jsonl",
)
POLISH_ROOT = REPO_ROOT / "reports" / "awakening_polish_run"
POLISH_WORK = POLISH_ROOT / "workspace"
POLISH_ART = POLISH_ROOT / "artifacts"
ET = ZoneInfo("America/New_York")
assert POLICY_EDGE_MIN_TRADES == 150
assert POLISH_TIMESTEPS == 10000
assert POLISH_FIXTURE_SEED == 20260906


class PolishProtocolError(RuntimeError):
    """AWAKENING_MARK_EYES_POLISH protocol crime (fail-closed)."""


def refuse_this_tape_hash(sha: str) -> str:
    text = str(sha or "").strip().lower()
    if not text:
        return text
    prefixes = ("5726ae7e", "e963d1ce", "7e86c2bb")
    if text.startswith(prefixes) or text in FORBIDDEN_TAPE_HASHES:
        raise PolishProtocolError(f"refused old tape hash {text[:16]} as THIS exam tape")
    return text


def refuse_forbidden_init(path: Path | str, sha: str = "") -> None:
    target = Path(path)
    name = target.name
    text = str(sha or "").strip().lower()
    posix = str(target).replace("\\", "/")
    if text[:8] in FORBIDDEN_INIT_SHA16:
        raise PolishProtocolError(f"refused forbidden init sha {text[:8]}")
    if name in FORBIDDEN_INIT_NAMES or "scratch" in name.lower() or "/lumina_agents/ppo/" in f"/{posix}":
        raise PolishProtocolError(f"refused forbidden init {name}")


def refuse_scratch_init(path: Path | str | None = None, *, init_policy: str | None = None) -> None:
    if str(init_policy or "").strip().lower() == "scratch":
        raise PolishProtocolError("refused scratch init_policy")
    if path is not None:
        refuse_forbidden_init(path, "")


def refuse_old_baseline(path: Path | str | None = None) -> None:
    if path is None:
        return
    name = Path(path).name
    if name in FORBIDDEN_BASELINE_NAMES or "path_early" in name or "budget_" in name:
        raise PolishProtocolError(f"refused old exam paper as baseline: {name}")


def assert_init_sha(path: Path | str, sha: str | None = None) -> str:
    target = Path(path)
    digest = str(sha or file_sha256(target)).strip().lower()
    refuse_forbidden_init(target, digest)
    refuse_scratch_init(target)
    if digest != INIT_SHA256:
        raise PolishProtocolError(f"init sha must be a9ffa852 pin, got {digest[:16]}")
    return digest


def write_bytes_sha(path: Path) -> str:
    digest = file_sha256(path)
    path.with_name(path.name + ".sha256").write_text(digest + "\n", encoding="utf-8")
    return digest


def copy_init_zip(art: Path) -> str:
    art.mkdir(parents=True, exist_ok=True)
    if not ORIGIN_EYES_ZIP.is_file():
        raise PolishProtocolError("frozen first-life MARK_EYES zip missing")
    dest = art / INIT_ZIP_NAME
    shutil.copy2(ORIGIN_EYES_ZIP, dest)
    digest = write_bytes_sha(dest)
    return assert_init_sha(dest, digest)


def origin_guard_paths(*, repo: Path | None = None) -> dict[str, Path]:
    root = repo or REPO_ROOT
    genesis = root / "reports" / "genesis_cloud_run" / "artifacts"
    budget = root / "reports" / "genesis_budget_run" / "artifacts"
    mapping = {
        "genesis_mark_eyes_pi_star.zip": genesis / "genesis_mark_eyes_pi_star.zip",
        "genesis_birth_exit_pi_star.zip": genesis / "genesis_birth_exit_pi_star.zip",
        "genesis_eyes_budget_flags.json": budget / "genesis_eyes_budget_flags.json",
        "budget_eyes_A_close_ledger.jsonl": budget / "budget_eyes_A_close_ledger.jsonl",
        "budget_eyes_B_close_ledger.jsonl": budget / "budget_eyes_B_close_ledger.jsonl",
    }
    return mapping


def snapshot_origin_artifacts(*, repo: Path | None = None) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, path in origin_guard_paths(repo=repo).items():
        out[name] = file_sha256(path) if path.is_file() else ""
    return out


def assert_origin_untouched(before: dict[str, str], *, repo: Path | None = None) -> None:
    after = snapshot_origin_artifacts(repo=repo)
    for name, sha in before.items():
        if sha and after.get(name) != sha:
            raise PolishProtocolError(f"origin artifact overwritten: {name}")


def polish_fixture_spec() -> CloudFixtureSpec:
    if int(POLISH_FIXTURE_SEED) != 20260906:
        raise PolishProtocolError("fixture seed must be 20260906")
    start_et = datetime(2026, 8, 3, 18, 0, tzinfo=ET)
    return CloudFixtureSpec(
        instrument=GENESIS_INSTRUMENT,
        calendar_days=int(FOUNDATION_HISTORY_START_DAYS),
        holdout_pct=float(POLISH_HOLDOUT_PCT),
        start_price=float(GENESIS_START_PRICE),
        seed=int(POLISH_FIXTURE_SEED),
        start_et=start_et,
        rth_bar_seconds=10,
        eth_bar_seconds=60,
    )


def persist_polish_fixture(work: Path, art: Path) -> dict[str, Any]:
    spec = polish_fixture_spec()
    result = persist_cloud_fixture(work, spec=spec)
    payload = dict(result.fixture_manifest)
    ticks = load_ticks_cache(work)
    payload["real_data_pct"] = float(real_data_percentage(ticks))
    payload["host_real_data_pct"] = float(host_real_data_pct(ticks, certified_cache=True))
    payload["fixture_seed"] = POLISH_FIXTURE_SEED
    payload["start_et"] = POLISH_START_ET_ISO
    payload["source"] = SOURCE_LABEL
    split = load_split_cache(work, holdout_pct=float(payload.get("holdout_pct") or POLISH_HOLDOUT_PCT))
    holdout = list(split.holdout) if split is not None else []
    train = list(split.train) if split is not None else []
    if not train:
        raise PolishProtocolError("train split missing")
    leg_a, leg_b = split_holdout_ab(holdout) if holdout else ([], [])
    payload["ticks_per_leg"] = [len(leg_a), len(leg_b)]
    sidecar = art / "01_polish_fixture_manifest.json"
    write_fixture_sidecar(sidecar, payload)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert_polish_fixture(work, payload)
    return payload


def assert_polish_fixture(work: Path, manifest: dict[str, Any]) -> None:
    if str(manifest.get("source") or "") != SOURCE_LABEL:
        raise PolishProtocolError("fixture source must be synthetic_cloud_fixture")
    ticks = load_ticks_cache(work)
    if real_data_percentage(ticks) != 0.0 or float(manifest.get("real_data_pct") or 0.0) != 0.0:
        raise PolishProtocolError("real_data_percentage must be 0.0")
    host = float(manifest.get("host_real_data_pct") or host_real_data_pct(ticks))
    if host == 100.0:
        raise PolishProtocolError("host_real_data_pct cannot be 100")
    refuse_this_tape_hash(str(manifest.get("hash") or ""))
    if int(manifest.get("holdout_tick_count") or 0) < MIN_HOLDOUT_TICKS:
        raise PolishProtocolError("holdout < 80k")
    if len(list(manifest.get("holdout_regimes") or [])) < 3:
        raise PolishProtocolError("holdout regimes < 3")
    legs = list(manifest.get("ticks_per_leg") or [])
    if len(legs) != 2 or int(legs[0]) < MIN_TICKS_PER_LEG or int(legs[1]) < MIN_TICKS_PER_LEG:
        raise PolishProtocolError("each chronological half must be >= 40000")


def prepare_polish_trees(*, repo: Path | None = None) -> tuple[Path, Path, Path]:
    root = (repo or REPO_ROOT) / "reports" / "awakening_polish_run"
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


def load_polish_train_split(work: Path) -> dict[str, Any]:
    split = load_split_cache(work, holdout_pct=POLISH_HOLDOUT_PCT)
    if split is None or not split.train:
        raise PolishProtocolError("polish train split missing")
    if not list(split.train):
        raise PolishProtocolError("refuse empty train")
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


def inspect_polish_protocol() -> dict[str, Any]:
    rel = "lumina_core/birth/awakening_mark_eyes_polish.py"
    flags = "lumina_core/birth/awakening_mark_eyes_polish_flags.py"
    train = "lumina_core/birth/awakening_mark_eyes_polish_train.py"
    honesty = "lumina_core/birth/data_source_honesty.py"
    metrics = "lumina_core/birth/foundation_metrics.py"
    exit_rel = "lumina_core/birth/awakening_path_exit_k3.py"
    shape_rel = "lumina_core/birth/awakening_path_shape_k3_dead.py"
    dump: dict[str, Any] = {
        "init_sha_a9ffa852": f"{rel}:{_line_of(rel, 'a9ffa852')}",
        "forbidden_init_8cc435c6": f"{rel}:{_line_of(rel, '8cc435c6')}",
        "forbidden_init_d313b107": f"{rel}:{_line_of(rel, 'd313b107')}",
        "forbidden_init_53df2d78": f"{rel}:{_line_of(rel, '53df2d78')}",
        "forbidden_init_scratch": f"{rel}:{_line_of(rel, 'scratch')}",
        "timesteps_10000": f"{rel}:{_line_of(rel, 'POLISH_TIMESTEPS = 10_000')}",
        "seed_20260906": f"{rel}:{_line_of(rel, 'POLISH_FIXTURE_SEED = 20260906')}",
        "start_et_2026_08_03": f"{rel}:{_line_of(rel, 'datetime(2026, 8, 3, 18, 0')}",
        "holdout_pct_0_40": f"{rel}:{_line_of(rel, 'POLISH_HOLDOUT_PCT = 0.40')}",
        "floor_150": f"{metrics}:{_line_of(metrics, 'POLICY_EDGE_MIN_TRADES = 150')}",
        "license_requires_both_legs": f"{flags}:{_line_of(flags, 'license requires both legs')}",
        "genesis_eyes_ok_forced_false": f"{flags}:{_line_of(flags, 'GENESIS_EYES_OK forced false')}",
        "hooks_default_false": (
            f"{exit_rel}:{_line_of(exit_rel, 'ContextVar(\"path_exit_k3_shadow\", default=False)')}"
        ),
        "hooks_shape_default_false": (
            f"{shape_rel}:{_line_of(shape_rel, 'ContextVar(\"path_shape_k3_shadow\", default=False)')}"
        ),
        "synthetic_pct_zero": f"{honesty}:{_line_of(honesty, 'synthetic_cloud_fixture')}",
        "reset_num_timesteps_false": f"{train}:{_line_of(train, 'reset_num_timesteps=False')}",
    }
    dump["missing_sites"] = [k for k, v in dump.items() if str(v).endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = [
    "CHILD_META_NAME",
    "CHILD_ZIP_NAME",
    "DELTA_MEAN_R_MIN",
    "FORBIDDEN_INIT_NAMES",
    "FORBIDDEN_INIT_SHA16",
    "FORBIDDEN_TAPE_HASHES",
    "HOLE_BLOW_MAX",
    "INIT_SHA256",
    "INIT_ZIP_NAME",
    "MIN_TICKS_PER_LEG",
    "POLISH_ART",
    "POLISH_FIXTURE_SEED",
    "POLISH_HOLDOUT_PCT",
    "POLISH_ROOT",
    "POLISH_START_ET_ISO",
    "POLISH_TIMESTEPS",
    "POLISH_TRAIN_SEED",
    "POLISH_WORK",
    "PolishProtocolError",
    "assert_init_sha",
    "assert_origin_untouched",
    "assert_polish_fixture",
    "copy_init_zip",
    "inspect_polish_protocol",
    "load_polish_train_split",
    "persist_polish_fixture",
    "prepare_polish_trees",
    "refuse_forbidden_init",
    "refuse_old_baseline",
    "refuse_scratch_init",
    "refuse_this_tape_hash",
    "snapshot_origin_artifacts",
    "write_bytes_sha",
]
