"""PATH_SHAPE K3 DEAD evaluate-only replay. Shape shadow ON here only. No learn()."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_grind_run import run_evaluate_only
from lumina_core.birth.awakening_path_exit_k3 import EVAL_A_SEED, EVAL_B_SEED, INIT_SHA256
from lumina_core.birth.awakening_path_exit_k3_flags import (
    baseline_from_rows,
    empty_baseline,
    path_exit_k3_rows,
)
from lumina_core.birth.awakening_path_exit_k3_t025_eval import (
    _load_or_build_fixture,
    write_jsonl_sha256,
)
from lumina_core.birth.awakening_path_shape_k3_dead import (
    GATE0_MAIN_SHA,
    OVERALL_INCONCLUSIVE,
    PATH_SHAPE_K3_SHADOW,
    SOURCE,
    PathShapeK3DeadProtocolError,
    assert_eval_seed,
    assert_isolated_write,
    assert_parent_sha,
    assert_wire_vs_path_early_a,
    isolated_workspace,
    load_close_jsonl,
    overall_path_shape_k3_dead_string,
    path_early_source_path,
    path_shape_k3_dead_ledger_path,
    policy_only_rows,
    resolve_parent_path,
)
from lumina_core.birth.awakening_path_shape_k3_dead_flags import (
    assert_n_exit_not_tfamily_clone,
    empty_measure,
    license_transfer,
)
from lumina_core.birth.awakening_path_shape_k3_dead_report import (
    leg_payload,
    write_path_shape_k3_dead_reports,
)
from lumina_core.birth.awakening_path_shape_k3_dead_tables import table_t2, table_t4
from lumina_core.birth.awakening_select_env import select_runtime
from lumina_core.birth.birth_exit_policy_export import load_frozen_policy


def run_path_shape_k3_dead_eval_leg(
    *,
    seed: int,
    holdout: list[dict[str, Any]],
    workspace_root: Path | str,
    reports: Path,
    policy_path: Path,
    rollout_fn: Any | None = None,
) -> Any:
    if TRAIN:
        raise RuntimeError("path shape k3 dead TRAIN must stay False")
    assert_eval_seed(int(seed))
    ledger = assert_isolated_write(path_shape_k3_dead_ledger_path(reports, leg="A" if seed == EVAL_A_SEED else "B"))
    loaded = load_frozen_policy(policy_path)
    if loaded is None:
        raise PathShapeK3DeadProtocolError(f"parent policy unloadable: {policy_path}")
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
        path_exit_k3_shadow=False,
    )


def empty_leg(
    zip_sha: str, *, skip_replay: bool, replay_ran: bool, baseline: dict[str, Any] | None = None
) -> dict[str, Any]:
    t0 = {
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
        "shape_enabled": False,
        "T_family_enabled": False,
        "mean_stamped_shape": None,
        "n_exit": 0,
        "skip_replay": bool(skip_replay),
        "replay_ran": bool(replay_ran),
        "source": SOURCE,
    }
    flags = {
        "n_exit": 0,
        "S_MISSING_HOOK": True,
        "S_HARM": False,
        "HOLE_MOVED": False,
        "tag": "S_MISSING",
        "law": "NONE",
        "baseline": baseline or empty_baseline(),
    }
    return {
        "t0": t0,
        "t1": {
            "n_U": 0,
            "n_H": 0,
            "n_W": 0,
            "n_exit": 0,
            "mean_r_exit": 0.0,
            "wr_exit": 0.0,
            "wr_policy": 0.0,
            "mean_r_policy": 0.0,
        },
        "t2": {},
        "t3": {"n_exit_k27": 0, "n_exit_t025": 0, "n_exit_shape": 0},
        "flags": flags,
        "rows_n": 0,
        "mean_stamped_threshold": None,
        "mean_stamped_shape": None,
        "exits": [],
    }


def write_measure_bundle(
    *,
    reports_path: Path,
    proto: dict[str, Any],
    zip_sha: str,
    parent_loaded: bool,
    skip_replay: bool,
    replay_ran: bool,
    overall: str,
    measure_a: dict[str, Any],
    measure_b: dict[str, Any],
    payload_a: dict[str, Any] | None = None,
    payload_b: dict[str, Any] | None = None,
    skipped_because: str = "",
    t025_tag: str = "",
) -> dict[str, Any]:
    empty = empty_leg(zip_sha, skip_replay=skip_replay, replay_ran=replay_ran)
    empty["t2"] = table_t2([], baseline=empty_baseline())
    a = payload_a or empty
    b = payload_b or empty
    t4 = table_t4(reports_path / "artifacts")
    flags = write_path_shape_k3_dead_reports(
        reports=reports_path,
        overall=overall,
        zip_sha=zip_sha or INIT_SHA256,
        payload_a=a,
        payload_b=b,
        measure_a=measure_a or empty_measure(),
        measure_b=measure_b or empty_measure(),
        t4=t4,
        proto=proto,
        parent_loaded=parent_loaded,
        skip_replay=skip_replay,
        replay_ran=replay_ran,
        gate0_sha=GATE0_MAIN_SHA,
        contextvar_try_finally=True,
        skipped_because=skipped_because,
        t025_tag=t025_tag,
    )
    return {
        "overall": overall,
        "parent_loaded": parent_loaded,
        "family": flags.get("licensed_next_family"),
        "skip_replay": skip_replay,
        "replay_ran": replay_ran,
        "tag": flags.get("tag"),
        "gate1_tag": flags.get("gate1_tag"),
        "HOLE_MOVED_A": flags.get("HOLE_MOVED_A"),
        "HOLE_MOVED_B": flags.get("HOLE_MOVED_B"),
    }


def _load_baseline(artifacts: Path, *, leg: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = path_early_source_path(artifacts, leg=leg)
    if not path.is_file():
        return empty_baseline(), []
    rows = load_close_jsonl(path)
    return baseline_from_rows(rows), rows


def _replay_path_shape_k3_dead_armed(
    *,
    reports_path: Path,
    proto: dict[str, Any],
    workspace_a: Path,
    workspace_b: Path,
    rollout_fn: Any | None,
    measure_a: dict[str, Any],
    measure_b: dict[str, Any],
    t025_tag: str,
) -> dict[str, Any]:
    if TRAIN:
        raise RuntimeError("path shape k3 dead TRAIN must stay False")
    iso = isolated_workspace(reports_path)
    iso.mkdir(parents=True, exist_ok=True)
    (iso / "state").mkdir(parents=True, exist_ok=True)
    parent = resolve_parent_path(workspace_a)
    zip_sha = assert_parent_sha(parent)
    artifacts = reports_path / "artifacts"
    base_a, _ = _load_baseline(artifacts, leg="A")
    base_b, _ = _load_baseline(artifacts, leg="B")
    if not base_a.get("present") or not base_b.get("present"):
        return write_measure_bundle(
            reports_path=reports_path,
            proto=proto,
            zip_sha=zip_sha,
            parent_loaded=True,
            skip_replay=False,
            replay_ran=False,
            overall=OVERALL_INCONCLUSIVE,
            measure_a=measure_a,
            measure_b=measure_b,
            skipped_because="path_early baseline missing",
            t025_tag=t025_tag,
        )
    fixture_a = _load_or_build_fixture(workspace_a, seed=EVAL_A_SEED)
    metrics_a = run_path_shape_k3_dead_eval_leg(
        seed=EVAL_A_SEED,
        holdout=list(fixture_a["holdout"]),
        workspace_root=workspace_a,
        reports=reports_path,
        policy_path=parent,
        rollout_fn=rollout_fn,
    )
    if int(getattr(metrics_a, "optimizer_steps", 0) or 0) != 0:
        raise PathShapeK3DeadProtocolError("optimizer_steps must stay 0")
    path_a = assert_isolated_write(path_shape_k3_dead_ledger_path(reports_path, leg="A"))
    write_jsonl_sha256(path_a)
    rows_a = load_close_jsonl(path_a)
    payload_a = leg_payload(
        rows=rows_a,
        zip_sha=zip_sha,
        ticks_sha16=str(fixture_a["ticks_sha16"]),
        price_sha16_value=str(fixture_a["price_sha16"]),
        optimizer_steps=0,
        hook_enabled=True,
        shape_enabled=True,
        t_family_enabled=False,
        baseline=base_a,
        skip_replay=False,
        replay_ran=True,
        artifacts=artifacts,
        leg="A",
    )
    assert_n_exit_not_tfamily_clone(
        n_exit_a=int(payload_a["t0"]["n_exit"]),
        exits_a=path_exit_k3_rows(policy_only_rows(rows_a)),
        mean_stamped_threshold_a=payload_a.get("mean_stamped_threshold"),
    )
    assert_wire_vs_path_early_a(
        wr_policy=float(payload_a["t0"]["wr_policy"]), n_policy=int(payload_a["t0"]["n_policy"])
    )
    fixture_b = _load_or_build_fixture(workspace_b, seed=EVAL_B_SEED)
    metrics_b = run_path_shape_k3_dead_eval_leg(
        seed=EVAL_B_SEED,
        holdout=list(fixture_b["holdout"]),
        workspace_root=workspace_b,
        reports=reports_path,
        policy_path=parent,
        rollout_fn=rollout_fn,
    )
    if int(getattr(metrics_b, "optimizer_steps", 0) or 0) != 0:
        raise PathShapeK3DeadProtocolError("optimizer_steps must stay 0")
    path_b = assert_isolated_write(path_shape_k3_dead_ledger_path(reports_path, leg="B"))
    write_jsonl_sha256(path_b)
    rows_b = load_close_jsonl(path_b)
    payload_b = leg_payload(
        rows=rows_b,
        zip_sha=zip_sha,
        ticks_sha16=str(fixture_b["ticks_sha16"]),
        price_sha16_value=str(fixture_b["price_sha16"]),
        optimizer_steps=0,
        hook_enabled=True,
        shape_enabled=True,
        t_family_enabled=False,
        baseline=base_b,
        skip_replay=False,
        replay_ran=True,
        artifacts=artifacts,
        leg="B",
    )
    flags_a = payload_a.get("flags") or {}
    flags_b = payload_b.get("flags") or {}
    licensed = license_transfer(flags_a, flags_b)
    overall = overall_path_shape_k3_dead_string(
        parent_loaded=True,
        skip_replay=False,
        optimizer_steps=0,
        replay_ran=True,
        s_missing_hook=bool(flags_a.get("S_MISSING_HOOK")),
        gate2_attempted=True,
        gate1_complete=True,
    )
    write_path_shape_k3_dead_reports(
        reports=reports_path,
        overall=overall,
        zip_sha=zip_sha,
        payload_a=payload_a,
        payload_b=payload_b,
        measure_a=measure_a,
        measure_b=measure_b,
        t4=table_t4(artifacts),
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
        contextvar_try_finally=True,
        skipped_because="replay_ran",
        t025_tag=t025_tag,
    )
    return {
        "overall": overall,
        "parent_loaded": True,
        "A": payload_a,
        "B": payload_b,
        "skip_replay": False,
        "replay_ran": True,
        "tag": licensed.get("tag"),
        "gate1_tag": "SHAPE_SPLIT",
        "HOLE_MOVED_A": licensed.get("HOLE_MOVED_A"),
        "HOLE_MOVED_B": licensed.get("HOLE_MOVED_B"),
    }


def replay_path_shape_k3_dead(
    *,
    reports_path: Path,
    proto: dict[str, Any],
    workspace_a: Path,
    workspace_b: Path,
    rollout_fn: Any | None,
    measure_a: dict[str, Any],
    measure_b: dict[str, Any],
    t025_tag: str = "",
) -> dict[str, Any]:
    tok_shape = PATH_SHAPE_K3_SHADOW.set(True)
    try:
        return _replay_path_shape_k3_dead_armed(
            reports_path=reports_path,
            proto=proto,
            workspace_a=workspace_a,
            workspace_b=workspace_b,
            rollout_fn=rollout_fn,
            measure_a=measure_a,
            measure_b=measure_b,
            t025_tag=t025_tag,
        )
    finally:
        PATH_SHAPE_K3_SHADOW.reset(tok_shape)


__all__ = [
    "empty_leg",
    "replay_path_shape_k3_dead",
    "run_path_shape_k3_dead_eval_leg",
    "write_jsonl_sha256",
    "write_measure_bundle",
]
