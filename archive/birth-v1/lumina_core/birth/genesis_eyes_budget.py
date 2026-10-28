"""GENESIS_EYES_BUDGET protocol: frozen first-life zips, NEW thick holdout.

Evaluate-only. No Birth. No second learn(). Floor 150. REAL door locked.
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
from lumina_core.birth.tick_cache_persist import load_split_cache, load_ticks_cache

# learn() absent — evaluate-only
BUDGET_FIXTURE_SEED = 20260905
BUDGET_START_ET_ISO = "2026-07-06T18:00:00-04:00"
BUDGET_HOLDOUT_PCT = 0.40
BUDGET_HOLDOUT_PCT_RAISE = 0.45
MIN_HOLDOUT_TICKS = 80_000
MIN_TICKS_PER_LEG = 40_000
STUDENT_BIRTH_SHA256 = "d313b107e99e03a5ce856226ccc6b352ae5fb01f995eccb4c0a6888988fda2af"
STUDENT_EYES_SHA256 = "a9ffa8529e02f2d8f8a535be4dcce205a43abe20bdec492add78126a8181188b"
FORBIDDEN_TAPE_HASH_5726 = "5726ae7e83ff3d48"
FORBIDDEN_TAPE_HASH_7E86 = "7e86c2bb1c71d514"
FORBIDDEN_DEAD_SHA16 = frozenset({"8cc435c6", "53df2d78"})
FORBIDDEN_FIXTURE_SEEDS = frozenset({20260902, 20260904})
FORBIDDEN_EVAL_BOOKS = frozenset({20260902, 20260903})
ORIGIN_BIRTH_ZIP = GENESIS_ART / "genesis_birth_exit_pi_star.zip"
ORIGIN_EYES_ZIP = GENESIS_ART / "genesis_mark_eyes_pi_star.zip"
STUDENT_BIRTH_NAME = "student_birth_exit_pi_star.zip"
STUDENT_EYES_NAME = "student_mark_eyes_pi_star.zip"
G5_LEDGER_NAMES = (
    "genesis_birth_A_close_ledger.jsonl",
    "genesis_birth_B_close_ledger.jsonl",
    "genesis_mark_eyes_A_close_ledger.jsonl",
    "genesis_mark_eyes_B_close_ledger.jsonl",
)
FORBIDDEN_LOAD_NAMES = frozenset(
    {
        "birth_exit_pi_star.zip",
        "awakening_mark_eyes_pi_star.zip",
        "path_early_A_close_ledger.jsonl",
        "path_early_B_close_ledger.jsonl",
    }
)
BUDGET_ROOT = REPO_ROOT / "reports" / "genesis_budget_run"
BUDGET_WORK = BUDGET_ROOT / "workspace"
BUDGET_ART = BUDGET_ROOT / "artifacts"
ET = ZoneInfo("America/New_York")
assert POLICY_EDGE_MIN_TRADES == 150


class BudgetProtocolError(RuntimeError):
    """GENESIS_EYES_BUDGET protocol crime (fail-closed)."""


def refuse_this_tape_hash(sha: str) -> str:
    text = str(sha or "").strip().lower()
    if not text:
        return text
    if text.startswith("5726ae7e") or text.startswith("7e86c2bb"):
        raise BudgetProtocolError(f"refused old tape hash {text[:16]} as THIS exam tape")
    if text in {FORBIDDEN_TAPE_HASH_5726, FORBIDDEN_TAPE_HASH_7E86}:
        raise BudgetProtocolError(f"refused old tape hash {text} as THIS exam tape")
    return text


def refuse_path_early_baseline(path: Path | str | None = None, *, n_h_pin: int | None = None) -> None:
    if path is not None:
        name = Path(path).name
        if "path_early" in name or name in FORBIDDEN_LOAD_NAMES:
            raise BudgetProtocolError(f"refused path_early baseline: {name}")
        if name in G5_LEDGER_NAMES:
            raise BudgetProtocolError("refused G5 halves as exam paper")
    if n_h_pin in {78, 83}:
        raise BudgetProtocolError("refused path_early n_H pin as baseline")


def refuse_forbidden_zip(path: Path | str, sha: str) -> None:
    target = Path(path)
    if target.name in {"birth_exit_pi_star.zip", "awakening_mark_eyes_pi_star.zip"}:
        raise BudgetProtocolError(f"refused dead zip name {target.name}")
    text = str(sha or "").strip().lower()
    if text[:8] in FORBIDDEN_DEAD_SHA16:
        raise BudgetProtocolError(f"refused dead zip sha {text[:8]}")


def g5_ledger_fingerprints() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in G5_LEDGER_NAMES:
        path = GENESIS_ART / name
        out[name] = file_sha256(path) if path.is_file() else ""
    return out


def assert_g5_ledgers_untouched(before: dict[str, str]) -> None:
    after = g5_ledger_fingerprints()
    for name, sha in before.items():
        if sha and after.get(name) != sha:
            raise BudgetProtocolError(f"G5 ledger overwritten: {name}")


def write_bytes_sha(path: Path) -> str:
    digest = file_sha256(path)
    path.with_name(path.name + ".sha256").write_text(digest + "\n", encoding="utf-8")
    return digest


def copy_frozen_students(art: Path) -> dict[str, str]:
    art.mkdir(parents=True, exist_ok=True)
    if not ORIGIN_BIRTH_ZIP.is_file() or not ORIGIN_EYES_ZIP.is_file():
        raise BudgetProtocolError("frozen genesis student zip missing")
    dest_b = art / STUDENT_BIRTH_NAME
    dest_e = art / STUDENT_EYES_NAME
    shutil.copy2(ORIGIN_BIRTH_ZIP, dest_b)
    shutil.copy2(ORIGIN_EYES_ZIP, dest_e)
    sha_b = write_bytes_sha(dest_b)
    sha_e = write_bytes_sha(dest_e)
    if sha_b != STUDENT_BIRTH_SHA256 or sha_e != STUDENT_EYES_SHA256:
        raise BudgetProtocolError("student sha mismatch vs d313b107 / a9ffa852")
    refuse_forbidden_zip(dest_b, sha_b)
    refuse_forbidden_zip(dest_e, sha_e)
    return {"student_birth_sha256": sha_b, "student_eyes_sha256": sha_e}


def budget_fixture_spec(*, holdout_pct: float = BUDGET_HOLDOUT_PCT) -> CloudFixtureSpec:
    if int(BUDGET_FIXTURE_SEED) in FORBIDDEN_FIXTURE_SEEDS:
        raise BudgetProtocolError("forbidden fixture seed used as THIS exam tape")
    start_et = datetime(2026, 7, 6, 18, 0, tzinfo=ET)
    return CloudFixtureSpec(
        instrument=GENESIS_INSTRUMENT,
        calendar_days=int(FOUNDATION_HISTORY_START_DAYS),
        holdout_pct=float(holdout_pct),
        start_price=float(GENESIS_START_PRICE),
        seed=int(BUDGET_FIXTURE_SEED),
        start_et=start_et,
        rth_bar_seconds=10,
        eth_bar_seconds=60,
    )


def persist_budget_fixture(work: Path, art: Path) -> dict[str, Any]:
    spec = budget_fixture_spec(holdout_pct=BUDGET_HOLDOUT_PCT)
    result = persist_cloud_fixture(work, spec=spec)
    payload = dict(result.fixture_manifest)
    if int(payload.get("holdout_tick_count") or 0) < MIN_HOLDOUT_TICKS:
        spec = budget_fixture_spec(holdout_pct=BUDGET_HOLDOUT_PCT_RAISE)
        result = persist_cloud_fixture(work, spec=spec)
        payload = dict(result.fixture_manifest)
        payload["holdout_pct_raised_once"] = True
    ticks = load_ticks_cache(work)
    payload["real_data_pct"] = float(real_data_percentage(ticks))
    payload["host_real_data_pct"] = float(host_real_data_pct(ticks, certified_cache=True))
    payload["fixture_seed"] = BUDGET_FIXTURE_SEED
    payload["start_et"] = BUDGET_START_ET_ISO
    payload["source"] = SOURCE_LABEL
    split = load_split_cache(work, holdout_pct=float(payload.get("holdout_pct") or BUDGET_HOLDOUT_PCT))
    holdout = list(split.holdout) if split is not None else []
    leg_a, leg_b = split_holdout_ab(holdout) if holdout else ([], [])
    payload["ticks_per_leg"] = [len(leg_a), len(leg_b)]
    sidecar = art / "01_budget_fixture_manifest.json"
    write_fixture_sidecar(sidecar, payload)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    assert_budget_fixture(work, payload)
    return payload


def assert_budget_fixture(work: Path, manifest: dict[str, Any]) -> None:
    if str(manifest.get("source") or "") != SOURCE_LABEL:
        raise BudgetProtocolError("fixture source must be synthetic_cloud_fixture")
    ticks = load_ticks_cache(work)
    if real_data_percentage(ticks) != 0.0 or float(manifest.get("real_data_pct") or 0.0) != 0.0:
        raise BudgetProtocolError("real_data_percentage must be 0.0")
    host = float(manifest.get("host_real_data_pct") or host_real_data_pct(ticks))
    if host == 100.0:
        raise BudgetProtocolError("host_real_data_pct cannot be 100")
    refuse_this_tape_hash(str(manifest.get("hash") or ""))
    if int(manifest.get("holdout_tick_count") or 0) < MIN_HOLDOUT_TICKS:
        raise BudgetProtocolError("holdout < 80k after one holdout_pct raise")
    if len(list(manifest.get("holdout_regimes") or [])) < 3:
        raise BudgetProtocolError("holdout regimes < 3")
    legs = list(manifest.get("ticks_per_leg") or [])
    if len(legs) != 2 or int(legs[0]) < MIN_TICKS_PER_LEG or int(legs[1]) < MIN_TICKS_PER_LEG:
        raise BudgetProtocolError("each chronological half must be >= 40000")


def prepare_budget_trees(*, repo: Path | None = None) -> tuple[Path, Path, Path]:
    root = (repo or REPO_ROOT) / "reports" / "genesis_budget_run"
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


def _line_of(rel: str, needle: str) -> int:
    path = REPO_ROOT / rel
    if not path.is_file():
        return -1
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    return -1


def inspect_budget_protocol() -> dict[str, Any]:
    rel = "lumina_core/birth/genesis_eyes_budget.py"
    flags = "lumina_core/birth/genesis_eyes_budget_flags.py"
    honesty = "lumina_core/birth/data_source_honesty.py"
    metrics = "lumina_core/birth/foundation_metrics.py"
    exit_rel = "lumina_core/birth/awakening_path_exit_k3.py"
    shape_rel = "lumina_core/birth/awakening_path_shape_k3_dead.py"
    dump: dict[str, Any] = {
        "seed_20260905": f"{rel}:{_line_of(rel, 'BUDGET_FIXTURE_SEED = 20260905')}",
        "start_et_2026_07_06": f"{rel}:{_line_of(rel, 'datetime(2026, 7, 6, 18, 0')}",
        "holdout_pct_0_40": f"{rel}:{_line_of(rel, 'BUDGET_HOLDOUT_PCT = 0.40')}",
        "min_ticks_per_leg_40000": f"{rel}:{_line_of(rel, 'MIN_TICKS_PER_LEG = 40_000')}",
        "student_sha_d313b107": f"{rel}:{_line_of(rel, 'd313b107')}",
        "student_sha_a9ffa852": f"{rel}:{_line_of(rel, 'a9ffa852')}",
        "forbidden_hash_5726ae7e": f"{rel}:{_line_of(rel, 'FORBIDDEN_TAPE_HASH_5726')}",
        "forbidden_hash_7e86c2bb": f"{rel}:{_line_of(rel, 'FORBIDDEN_TAPE_HASH_7E86')}",
        "floor_150": f"{metrics}:{_line_of(metrics, 'POLICY_EDGE_MIN_TRADES = 150')}",
        "thin_refuses_budget_ok": f"{flags}:{_line_of(flags, 'license refuses BUDGET_OK when a leg is thin')}",
        "genesis_eyes_ok_forced_false": f"{flags}:{_line_of(flags, 'GENESIS_EYES_OK forced false')}",
        "learn_absent": f"{rel}:{_line_of(rel, 'learn() absent')}",
        "hooks_default_false": (
            f"{exit_rel}:{_line_of(exit_rel, 'ContextVar(\"path_exit_k3_shadow\", default=False)')}"
        ),
        "hooks_shape_default_false": (
            f"{shape_rel}:{_line_of(shape_rel, 'ContextVar(\"path_shape_k3_shadow\", default=False)')}"
        ),
        "synthetic_pct_zero": f"{honesty}:{_line_of(honesty, 'synthetic_cloud_fixture')}",
    }
    dump["missing_sites"] = [k for k, v in dump.items() if str(v).endswith(":-1")]
    dump["gate0_complete"] = len(dump["missing_sites"]) == 0
    return dump


__all__ = [
    "BUDGET_ART",
    "BUDGET_FIXTURE_SEED",
    "BUDGET_HOLDOUT_PCT",
    "BUDGET_ROOT",
    "BUDGET_START_ET_ISO",
    "BUDGET_WORK",
    "FORBIDDEN_EVAL_BOOKS",
    "FORBIDDEN_TAPE_HASH_5726",
    "FORBIDDEN_TAPE_HASH_7E86",
    "BudgetProtocolError",
    "MIN_TICKS_PER_LEG",
    "STUDENT_BIRTH_SHA256",
    "STUDENT_EYES_SHA256",
    "assert_budget_fixture",
    "assert_g5_ledgers_untouched",
    "copy_frozen_students",
    "g5_ledger_fingerprints",
    "inspect_budget_protocol",
    "persist_budget_fixture",
    "prepare_budget_trees",
    "refuse_forbidden_zip",
    "refuse_path_early_baseline",
    "refuse_this_tape_hash",
]
