"""PATH_EXIT K3 evaluate-only replay helpers. Hook ON only here. No learn()."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_grind_run import run_evaluate_only
from lumina_core.birth.awakening_path_exit_k3 import (
    EVAL_A_SEED,
    EVAL_B_SEED,
    GATE0_MAIN_SHA,
    INIT_SHA256,
    OVERALL_INCONCLUSIVE,
    SOURCE,
    PathExitK3ProtocolError,
    assert_eval_seed,
    assert_isolated_write,
    assert_parent_sha,
    assert_wire_vs_path_early_a,
    isolated_workspace,
    load_close_jsonl,
    overall_path_exit_k3_string,
    path_early_source_path,
    path_exit_k3_ledger_path,
    reports_dir,
    resolve_parent_path,
)
from lumina_core.birth.awakening_path_exit_k3_flags import baseline_from_rows, empty_baseline
from lumina_core.birth.awakening_path_exit_k3_report import (
    leg_payload,
    write_path_exit_k3_reports,
)
from lumina_core.birth.awakening_path_exit_k3_tables import table_t4
from lumina_core.birth.awakening_select import price_sha16
from lumina_core.birth.awakening_select_env import select_runtime
from lumina_core.birth.birth_exit_policy_export import file_sha256, load_frozen_policy
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.awakening_path_exit_k3_eval")


def write_jsonl_sha256(path: Path) -> Path:
    digest = hashlib.sha256()
    if path.is_file():
        digest.update(path.read_bytes())
    sidecar = path.with_suffix(".sha256")
    sidecar.write_text(digest.hexdigest() + "\n", encoding="utf-8")
    return sidecar


def _load_or_build_fixture(workspace: Path, *, seed: int) -> dict[str, Any]:
    from lumina_core.birth.synthetic_cloud_fixture import (
        CloudFixtureSpec,
        persist_cloud_fixture,
    )
    from lumina_core.birth.tick_cache_persist import certified_tick_cache_present, load_split_cache

    assert_eval_seed(int(seed))
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "state").mkdir(parents=True, exist_ok=True)
    reports = reports_dir()
    sidecar = reports / ("01_fixture_manifest.json" if seed == EVAL_A_SEED else "01_fixture_manifest_B.json")
    if seed == EVAL_A_SEED and certified_tick_cache_present(workspace) and sidecar.is_file():
        manifest = json.loads(sidecar.read_text(encoding="utf-8"))
        split = load_split_cache(workspace, holdout_pct=0.20)
        if split is not None and str(manifest.get("hash") or "") == "7e86c2bb1c71d514":
            holdout = list(split.holdout)
            return {
                "holdout": holdout,
                "ticks_sha16": str(manifest.get("hash") or ""),
                "bars_sha16": str(manifest.get("raw_ticks_hash") or ""),
                "price_sha16": price_sha16(holdout),
            }
    spec = CloudFixtureSpec(seed=int(seed))
    result = persist_cloud_fixture(workspace, spec=spec)
    man = dict(result.fixture_manifest)
    holdout = list(result.split.holdout)
    return {
        "holdout": holdout,
        "ticks_sha16": str(man.get("hash") or man.get("train_hash") or ""),
        "bars_sha16": str(man.get("raw_ticks_hash") or ""),
        "price_sha16": price_sha16(holdout),
    }


def run_path_exit_k3_eval_leg(
    *,
    seed: int,
    holdout: list[dict[str, Any]],
    workspace_root: Path | str,
    reports: Path,
    policy_path: Path,
    rollout_fn: Any | None = None,
) -> Any:
    if TRAIN:
        raise RuntimeError("path exit k3 TRAIN must stay False")
    assert_eval_seed(int(seed))
    ledger = assert_isolated_write(
        path_exit_k3_ledger_path(reports, leg="A" if seed == EVAL_A_SEED else "B")
    )
    loaded = load_frozen_policy(policy_path)
    if loaded is None:
        raise PathExitK3ProtocolError(f"parent policy unloadable: {policy_path}")
    return run_evaluate_only(
        runtime=select_runtime(),
        holdout=list(holdout),
        workspace_root=workspace_root,
        reports_dir=reports,
        ledger_path=ledger,
        policy=loaded,
        policy_path=policy_path,
        rollout_fn=rollout_fn,
        ledger_source=SOURCE,
        path_exit_k3_shadow=True,
    )


def empty_leg(
    zip_sha: str,
    *,
    skip_replay: bool,
    replay_ran: bool,
    baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "t0": {
            "n_all": 0,
            "n_policy": 0,
            "n_plant": 0,
            "wr_policy": 0.0,
            "mean_r_policy": 0.0,
            "zip_sha256": zip_sha or INIT_SHA256,
            "ticks_sha16": "",
            "price_sha16": "",
            "optimizer_steps": 0,
            "hook_enabled": False,
            "n_exit": 0,
            "skip_replay": bool(skip_replay),
            "replay_ran": bool(replay_ran),
            "source": SOURCE,
        },
        "t1": {"n_U": 0, "n_H": 0, "n_W": 0, "n_exit": 0, "mean_r_exit": 0.0, "wr_exit": 0.0},
        "t2": {},
        "t3": {"n_exit_live": 0, "scale_fail": True},
        "t5": {"join_absent": True},
        "flags": {
            "n_exit": 0,
            "S_MISSING_HOOK": True,
            "S_HARM": False,
            "HOLE_MOVED": False,
            "tag": "S_MISSING",
            "law": "NONE",
            "baseline": baseline or empty_baseline(),
        },
        "rows_n": 0,
    }


def write_inconclusive(
    *,
    reports_path: Path,
    proto: dict[str, Any],
    zip_sha: str,
    parent_loaded: bool,
    skip_replay: bool,
    replay_ran: bool,
    overall: str,
) -> dict[str, Any]:
    from lumina_core.birth.awakening_path_exit_k3_tables import table_t2

    empty = empty_leg(zip_sha, skip_replay=skip_replay, replay_ran=replay_ran)
    empty["t2"] = table_t2([], baseline=empty_baseline())
    t4 = table_t4(reports_path / "artifacts")
    write_path_exit_k3_reports(
        reports=reports_path,
        overall=overall,
        zip_sha=zip_sha or INIT_SHA256,
        payload_a=empty,
        payload_b=empty,
        t4=t4,
        proto=proto,
        parent_loaded=parent_loaded,
        skip_replay=skip_replay,
        replay_ran=replay_ran,
        gate0_sha=GATE0_MAIN_SHA,
    )
    return {
        "overall": overall,
        "parent_loaded": parent_loaded,
        "family": "PATH_EXIT:P_K3_UNREAL_RED",
        "skip_replay": skip_replay,
        "replay_ran": replay_ran,
        "tag": "S_MISSING",
    }


def _load_baseline(artifacts: Path, *, leg: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = path_early_source_path(artifacts, leg=leg)
    if not path.is_file():
        return empty_baseline(), []
    rows = load_close_jsonl(path)
    return baseline_from_rows(rows), rows


def replay_path_exit_k3(
    *,
    reports_path: Path,
    proto: dict[str, Any],
    workspace_a: Path,
    workspace_b: Path,
    rollout_fn: Any | None,
) -> dict[str, Any]:
    if TRAIN:
        raise RuntimeError("path exit k3 TRAIN must stay False")
    iso = isolated_workspace(reports_path)
    iso.mkdir(parents=True, exist_ok=True)
    (iso / "state").mkdir(parents=True, exist_ok=True)
    parent = resolve_parent_path(workspace_a)
    zip_sha = assert_parent_sha(parent)
    artifacts = reports_path / "artifacts"
    base_a, rows_base_a = _load_baseline(artifacts, leg="A")
    base_b, rows_base_b = _load_baseline(artifacts, leg="B")
    if not base_a.get("present"):
        return write_inconclusive(
            reports_path=reports_path,
            proto=proto,
            zip_sha=zip_sha,
            parent_loaded=True,
            skip_replay=False,
            replay_ran=False,
            overall=OVERALL_INCONCLUSIVE,
        )
    fixture_a = _load_or_build_fixture(workspace_a, seed=EVAL_A_SEED)
    metrics_a = run_path_exit_k3_eval_leg(
        seed=EVAL_A_SEED,
        holdout=list(fixture_a["holdout"]),
        workspace_root=workspace_a,
        reports=reports_path,
        policy_path=parent,
        rollout_fn=rollout_fn,
    )
    if int(getattr(metrics_a, "optimizer_steps", 0) or 0) != 0:
        raise PathExitK3ProtocolError("optimizer_steps must stay 0")
    path_a = assert_isolated_write(path_exit_k3_ledger_path(reports_path, leg="A"))
    write_jsonl_sha256(path_a)
    rows_a = load_close_jsonl(path_a)
    payload_a = leg_payload(
        rows=rows_a,
        zip_sha=zip_sha,
        ticks_sha16=str(fixture_a["ticks_sha16"]),
        price_sha16_value=str(fixture_a["price_sha16"]),
        optimizer_steps=0,
        hook_enabled=True,
        baseline=base_a,
        baseline_rows=rows_base_a,
        skip_replay=False,
        replay_ran=True,
    )
    assert_wire_vs_path_early_a(
        wr_policy=float(payload_a["t0"]["wr_policy"]),
        n_policy=int(payload_a["t0"]["n_policy"]),
    )
    fixture_b = _load_or_build_fixture(workspace_b, seed=EVAL_B_SEED)
    metrics_b = run_path_exit_k3_eval_leg(
        seed=EVAL_B_SEED,
        holdout=list(fixture_b["holdout"]),
        workspace_root=workspace_b,
        reports=reports_path,
        policy_path=parent,
        rollout_fn=rollout_fn,
    )
    if int(getattr(metrics_b, "optimizer_steps", 0) or 0) != 0:
        raise PathExitK3ProtocolError("optimizer_steps must stay 0")
    path_b = assert_isolated_write(path_exit_k3_ledger_path(reports_path, leg="B"))
    write_jsonl_sha256(path_b)
    rows_b = load_close_jsonl(path_b)
    payload_b = leg_payload(
        rows=rows_b,
        zip_sha=zip_sha,
        ticks_sha16=str(fixture_b["ticks_sha16"]),
        price_sha16_value=str(fixture_b["price_sha16"]),
        optimizer_steps=0,
        hook_enabled=True,
        baseline=base_b,
        baseline_rows=rows_base_b,
        skip_replay=False,
        replay_ran=True,
    )
    flags_a = payload_a.get("flags") or {}
    overall = overall_path_exit_k3_string(
        parent_loaded=True,
        skip_replay=False,
        optimizer_steps=0,
        replay_ran=True,
        s_missing_hook=bool(flags_a.get("S_MISSING_HOOK")),
    )
    t4 = table_t4(artifacts)
    write_path_exit_k3_reports(
        reports=reports_path,
        overall=overall,
        zip_sha=zip_sha,
        payload_a=payload_a,
        payload_b=payload_b,
        t4=t4,
        proto=proto,
        parent_loaded=True,
        skip_replay=False,
        replay_ran=True,
        gate0_sha=GATE0_MAIN_SHA,
        flatten_sites={
            "force_flatten": "lumina_core/birth/sim_runner.py:_path_exit_k3_request",
            "plan_birth_exit_fill": "lumina_core/rl/gym_stop_fill.py:38",
            "close_reason": "force_exit + path_exit_k3 sidecar",
        },
    )
    logger.info(
        "awakening.path_exit_k3.replay overall=%s tag=%s n_exit_a=%s n_exit_b=%s",
        overall,
        flags_a.get("tag"),
        payload_a["t0"]["n_exit"],
        payload_b["t0"]["n_exit"],
    )
    return {
        "overall": overall,
        "parent_loaded": True,
        "A": payload_a,
        "B": payload_b,
        "t4": t4,
        "ledger_a": str(path_a),
        "ledger_b": str(path_b),
        "skip_replay": False,
        "replay_ran": True,
        "tag": flags_a.get("tag"),
    }


__all__ = [
    "empty_leg",
    "replay_path_exit_k3",
    "run_path_exit_k3_eval_leg",
    "write_inconclusive",
    "write_jsonl_sha256",
]
