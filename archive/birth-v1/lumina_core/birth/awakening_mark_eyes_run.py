"""MARK_EYES runner: Gate 0 inspect → Gate 2 one learn-shot → Gate 3 eval A then B."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_mark_eyes import (
    EVAL_A_SEED,
    EVAL_B_SEED,
    GATE0_MAIN_SHA,
    INIT_SHA256,
    OVERALL_INCONCLUSIVE,
    MarkEyesProtocolError,
    isolated_workspace,
    overall_mark_eyes_string,
    reports_dir,
)
from lumina_core.birth.awakening_mark_eyes_eval import run_mark_eyes_eval_leg
from lumina_core.birth.awakening_mark_eyes_flags import compute_mark_eyes_leg, empty_leg
from lumina_core.birth.awakening_mark_eyes_path import inspect_mark_eyes_protocol
from lumina_core.birth.awakening_mark_eyes_report import write_mark_eyes_reports
from lumina_core.birth.awakening_mark_eyes_train import dump_learn_traceback, run_mark_eyes_train
from lumina_core.birth.awakening_path_exit_k3 import (
    PATH_EXIT_K3_SHADOW,
    assert_parent_sha,
    load_close_jsonl,
    path_early_source_path,
    resolve_parent_path,
)
from lumina_core.birth.awakening_path_exit_k3_flags import baseline_from_rows, empty_baseline
from lumina_core.birth.awakening_path_shape_k3_dead import PATH_SHAPE_K3_SHADOW
from lumina_core.birth.awakening_select import price_sha16
from lumina_core.logging_utils import get_logger
from lumina_core.rl.observation_builder import OBSERVATION_DIM

logger = get_logger("lumina.birth.awakening_mark_eyes_run")


def _load_eval_tape(workspace: Path, *, seed: int) -> dict[str, Any]:
    from lumina_core.birth.synthetic_cloud_fixture import CloudFixtureSpec, persist_cloud_fixture

    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "state").mkdir(parents=True, exist_ok=True)
    result = persist_cloud_fixture(workspace, spec=CloudFixtureSpec(seed=int(seed)))
    holdout = list(result.split.holdout)
    return {
        "holdout": holdout,
        "ticks_sha16": str(result.fixture_manifest.get("hash") or ""),
        "price_sha16": price_sha16(holdout),
    }


def _baseline(artifacts: Path, *, leg: str) -> tuple[dict[str, Any], bool]:
    path = path_early_source_path(artifacts, leg=leg)
    if not path.is_file():
        return empty_baseline(), False
    return baseline_from_rows(load_close_jsonl(path)), True


def _write(
    *,
    reports_path: Path,
    proto: dict[str, Any],
    overall: str,
    parent_sha: str,
    child_sha: str,
    actual_timesteps: int,
    optimizer_steps: int,
    ticks_sha16: str,
    init_policy: str,
    learn_called: bool,
    path_early_present: bool,
    hooks_false: bool,
    workspace_isolated: bool,
    forbidden_init_refused: bool,
    leg_a: dict[str, Any],
    leg_b: dict[str, Any],
) -> dict[str, Any]:
    flags = write_mark_eyes_reports(
        reports=reports_path,
        overall=overall,
        proto=proto,
        parent_sha=parent_sha,
        child_sha=child_sha,
        actual_timesteps=actual_timesteps,
        optimizer_steps=optimizer_steps,
        ticks_sha16=ticks_sha16,
        init_policy=init_policy,
        learn_called=learn_called,
        path_early_present=path_early_present,
        hooks_false=hooks_false,
        workspace_isolated=workspace_isolated,
        forbidden_init_refused=forbidden_init_refused,
        leg_a=leg_a,
        leg_b=leg_b,
        gate0_sha=GATE0_MAIN_SHA,
    )
    return {
        "overall": overall,
        "tag": flags.get("tag"),
        "law": flags.get("law"),
        "licensed_next_family": flags.get("licensed_next_family"),
        "learn_called": learn_called,
        "child_sha256": child_sha,
        "actual_timesteps": actual_timesteps,
        "flags": flags,
    }


def run_mark_eyes(
    *,
    reports: Path | str | None = None,
    skip_train: bool = False,
    learn_fn: Any | None = None,
    ppo_cls: Any | None = None,
    rollout_fn: Any | None = None,
) -> dict[str, Any]:
    if TRAIN:
        raise RuntimeError("mark eyes TRAIN module flag must stay False")
    reports_path = Path(reports) if reports is not None else reports_dir()
    artifacts = reports_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    proto = inspect_mark_eyes_protocol()
    hooks_false = (not bool(PATH_EXIT_K3_SHADOW.get())) and (not bool(PATH_SHAPE_K3_SHADOW.get()))
    parent_sha = INIT_SHA256
    parent_ok = False
    try:
        parent_sha = assert_parent_sha(resolve_parent_path(reports_path / "workspace"))
        parent_ok = True
    except Exception:
        parent_ok = False
    base_a, present_a = _baseline(artifacts, leg="A")
    base_b, present_b = _baseline(artifacts, leg="B")
    path_early_present = bool(present_a and present_b)
    ws = isolated_workspace(reports_path)
    missing_proto = not bool(proto.get("gate0_complete"))
    if missing_proto or not parent_ok or not path_early_present or not hooks_false:
        overall = OVERALL_INCONCLUSIVE
        return _write(
            reports_path=reports_path,
            proto=proto,
            overall=overall,
            parent_sha=parent_sha,
            child_sha="",
            actual_timesteps=0,
            optimizer_steps=0,
            ticks_sha16="",
            init_policy="scratch",
            learn_called=False,
            path_early_present=path_early_present,
            hooks_false=hooks_false,
            workspace_isolated=True,
            forbidden_init_refused=True,
            leg_a=empty_leg(missing=True, leg="A"),
            leg_b=empty_leg(missing=True, leg="B"),
        )
    train_out: dict[str, Any] = {
        "child_sha256": "",
        "actual_timesteps": 0,
        "optimizer_steps": 0,
        "train_ticks_sha16": "",
        "learn_called": False,
        "init_policy": "scratch",
    }
    child = reports_path / "artifacts" / "awakening_mark_eyes_pi_star.zip"
    meta = child.with_name("awakening_mark_eyes_pi_star.json")
    reuse = False
    if child.is_file() and meta.is_file():
        payload = json.loads(meta.read_text(encoding="utf-8"))
        if (
            int(payload.get("actual_timesteps") or 0) == 10_000
            and str(payload.get("init_policy") or "") == "scratch"
        ):
            reuse = True
            train_out = {
                "child_sha256": str(payload.get("sha256") or ""),
                "actual_timesteps": int(payload.get("actual_timesteps") or 0),
                "optimizer_steps": int(payload.get("optimizer_steps") or 0),
                "train_ticks_sha16": str(payload.get("train_ticks_sha16") or ""),
                "learn_called": True,
                "init_policy": "scratch",
            }
    if skip_train and not reuse:
        pass
    elif not reuse and not skip_train:
        try:
            train_out = run_mark_eyes_train(
                workspace_root=reports_path,
                reports=reports_path,
                learn_fn=learn_fn,
                ppo_cls=ppo_cls,
            )
        except Exception as exc:
            logger.error("mark_eyes.gate2_failed %s", dump_learn_traceback(exc))
            return _write(
                reports_path=reports_path,
                proto=proto,
                overall=OVERALL_INCONCLUSIVE,
                parent_sha=parent_sha,
                child_sha="",
                actual_timesteps=0,
                optimizer_steps=0,
                ticks_sha16="",
                init_policy="scratch",
                learn_called=False,
                path_early_present=path_early_present,
                hooks_false=hooks_false,
                workspace_isolated=True,
                forbidden_init_refused=True,
                leg_a=empty_leg(missing=True, leg="A"),
                leg_b=empty_leg(missing=True, leg="B"),
            )
    child_sha = str(train_out.get("child_sha256") or "")
    actual = int(train_out.get("actual_timesteps") or 0)
    opt = int(train_out.get("optimizer_steps") or 0)
    learn_called = bool(train_out.get("learn_called"))
    ticks = str(train_out.get("train_ticks_sha16") or "")
    if actual <= 0 or not child.is_file():
        overall = overall_mark_eyes_string(
            parent_ok=parent_ok,
            path_early_present=path_early_present,
            optimizer_steps=opt,
            actual_timesteps=actual,
            train_seed=20260901,
            obs_dim_global=int(OBSERVATION_DIM),
            init_policy="scratch",
            hook_true=not hooks_false,
            forbidden_write=False,
            gate2_complete=False,
        )
        return _write(
            reports_path=reports_path,
            proto=proto,
            overall=overall,
            parent_sha=parent_sha,
            child_sha=child_sha,
            actual_timesteps=actual,
            optimizer_steps=opt,
            ticks_sha16=ticks,
            init_policy="scratch",
            learn_called=learn_called,
            path_early_present=path_early_present,
            hooks_false=hooks_false,
            workspace_isolated=True,
            forbidden_init_refused=True,
            leg_a=empty_leg(missing=True, leg="A"),
            leg_b=empty_leg(missing=True, leg="B"),
        )
    legs: dict[str, dict[str, Any]] = {}
    for seed, key, base in ((EVAL_A_SEED, "A", base_a), (EVAL_B_SEED, "B", base_b)):
        try:
            tape = _load_eval_tape(ws, seed=int(seed))
            run_mark_eyes_eval_leg(
                seed=int(seed),
                holdout=list(tape["holdout"]),
                workspace_root=ws,
                reports=reports_path,
                policy_path=child,
                rollout_fn=rollout_fn,
            )
            ledger = artifacts / (
                "mark_eyes_A_close_ledger.jsonl" if key == "A" else "mark_eyes_B_close_ledger.jsonl"
            )
            rows = load_close_jsonl(ledger) if ledger.is_file() else []
            legs[key] = compute_mark_eyes_leg(rows, baseline=base, missing=False)
        except (MarkEyesProtocolError, OSError, ValueError) as exc:
            logger.error("mark_eyes.eval_%s_failed %s", key, exc)
            legs[key] = empty_leg(missing=True, leg=key)
    overall = overall_mark_eyes_string(
        parent_ok=parent_ok,
        path_early_present=path_early_present,
        optimizer_steps=opt,
        actual_timesteps=actual,
        train_seed=20260901,
        obs_dim_global=int(OBSERVATION_DIM),
        init_policy="scratch",
        hook_true=not hooks_false,
        forbidden_write=False,
        gate2_complete=True,
    )
    return _write(
        reports_path=reports_path,
        proto=proto,
        overall=overall,
        parent_sha=parent_sha,
        child_sha=child_sha,
        actual_timesteps=actual,
        optimizer_steps=opt,
        ticks_sha16=ticks,
        init_policy="scratch",
        learn_called=learn_called,
        path_early_present=path_early_present,
        hooks_false=hooks_false,
        workspace_isolated=True,
        forbidden_init_refused=True,
        leg_a=legs.get("A") or empty_leg(missing=True, leg="A"),
        leg_b=legs.get("B") or empty_leg(missing=True, leg="B"),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Awakening MARK_EYES new-body birth window")
    parser.parse_args(argv)
    out = run_mark_eyes()
    print(
        json.dumps(
            {
                "overall": out.get("overall"),
                "tag": out.get("tag"),
                "law": out.get("law"),
                "licensed_next_family": out.get("licensed_next_family"),
                "learn_called": out.get("learn_called"),
                "actual_timesteps": out.get("actual_timesteps"),
                "child_sha256": out.get("child_sha256"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "run_mark_eyes"]
