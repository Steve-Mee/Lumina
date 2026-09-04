"""PATH_SHAPE K3 DEAD runner: Gate 1 always. Gate 2 only after SHAPE_SPLIT."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_path_exit_k3 import INIT_SHA256, PathExitK3ProtocolError
from lumina_core.birth.awakening_path_shape_k3_dead import (
    OVERALL_INCONCLUSIVE,
    OVERALL_MEASURE,
    PATH_SHAPE_K3_SHADOW,
    PathShapeK3DeadProtocolError,
    T025_FLAGS_NAME,
    assert_parent_sha,
    isolated_workspace,
    load_close_jsonl,
    overall_path_shape_k3_dead_string,
    path_early_source_path,
    reports_dir,
    resolve_parent_path,
)
from lumina_core.birth.awakening_path_shape_k3_dead_eval import (
    replay_path_shape_k3_dead,
    write_measure_bundle,
)
from lumina_core.birth.awakening_path_shape_k3_dead_flags import (
    TAG_SHAPE_SPLIT,
    compute_shape_measure_flags,
    empty_measure,
    license_shape,
)
from lumina_core.birth.awakening_path_shape_k3_dead_path import inspect_path_shape_k3_dead_protocol
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.awakening_path_shape_k3_dead_run")


def _t025_tag(artifacts: Path) -> str:
    path = artifacts / T025_FLAGS_NAME
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(payload.get("tag") or "")


def _measure_leg(artifacts: Path, *, leg: str) -> dict[str, Any]:
    path = path_early_source_path(artifacts, leg=leg)
    if not path.is_file():
        return empty_measure(missing=True)
    return compute_shape_measure_flags(load_close_jsonl(path))


def run_path_shape_k3_dead(
    *,
    reports: Path | str | None = None,
    workspace_a: Path | str | None = None,
    workspace_b: Path | str | None = None,
    rollout_fn: Any | None = None,
    skip_replay: bool = False,
    fixture_compare: bool = False,
) -> dict[str, Any]:
    if TRAIN:
        raise RuntimeError("path shape k3 dead TRAIN must stay False")
    reports_path = Path(reports) if reports is not None else reports_dir()
    proto = inspect_path_shape_k3_dead_protocol()
    artifacts = reports_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    isolated_workspace(reports_path).mkdir(parents=True, exist_ok=True)
    ws_a = Path(workspace_a) if workspace_a is not None else reports_path / "workspace"
    ws_b = Path(workspace_b) if workspace_b is not None else reports_path / "workspace_grind_b"
    t025_tag = _t025_tag(artifacts)
    measure_a = _measure_leg(artifacts, leg="A")
    measure_b = _measure_leg(artifacts, leg="B")
    shape_lic = license_shape(measure_a, measure_b)
    gate1_tag = str(shape_lic.get("tag") or "S_MISSING")
    parent_loaded = False
    zip_sha = INIT_SHA256
    try:
        parent = resolve_parent_path(ws_a)
        zip_sha = assert_parent_sha(parent)
        parent_loaded = True
    except (PathExitK3ProtocolError, PathShapeK3DeadProtocolError):
        parent_loaded = False
    # TRANSFER_OK unreachable unless Gate 1 was SHAPE_SPLIT
    if gate1_tag != TAG_SHAPE_SPLIT:
        overall = overall_path_shape_k3_dead_string(
            parent_loaded=parent_loaded,
            skip_replay=False,
            optimizer_steps=0,
            replay_ran=False,
            gate2_attempted=False,
            gate1_complete=True,
        )
        return write_measure_bundle(
            reports_path=reports_path,
            proto=proto,
            zip_sha=zip_sha,
            parent_loaded=parent_loaded,
            skip_replay=False,
            replay_ran=False,
            overall=overall,
            measure_a=measure_a,
            measure_b=measure_b,
            skipped_because=f"gate1_tag={gate1_tag}",
            t025_tag=t025_tag,
        )
    if not proto.get("gate0_complete"):
        return write_measure_bundle(
            reports_path=reports_path,
            proto=proto,
            zip_sha=zip_sha,
            parent_loaded=parent_loaded,
            skip_replay=False,
            replay_ran=False,
            overall=OVERALL_MEASURE,
            measure_a=measure_a,
            measure_b=measure_b,
            skipped_because=f"gate0 incomplete: {proto.get('missing_sites')}",
            t025_tag=t025_tag,
        )
    if skip_replay:
        overall = overall_path_shape_k3_dead_string(
            parent_loaded=parent_loaded,
            skip_replay=True,
            optimizer_steps=0,
            replay_ran=False,
            fixture_compare=bool(fixture_compare),
            gate2_attempted=True,
            gate1_complete=True,
        )
        return write_measure_bundle(
            reports_path=reports_path,
            proto=proto,
            zip_sha=zip_sha,
            parent_loaded=parent_loaded,
            skip_replay=True,
            replay_ran=False,
            overall=OVERALL_INCONCLUSIVE if not fixture_compare else overall,
            measure_a=measure_a,
            measure_b=measure_b,
            skipped_because="skip_replay",
            t025_tag=t025_tag,
        )
    if not parent_loaded:
        return write_measure_bundle(
            reports_path=reports_path,
            proto=proto,
            zip_sha=zip_sha,
            parent_loaded=False,
            skip_replay=False,
            replay_ran=False,
            overall=OVERALL_INCONCLUSIVE,
            measure_a=measure_a,
            measure_b=measure_b,
            skipped_because="parent missing",
            t025_tag=t025_tag,
        )
    tok_shape = PATH_SHAPE_K3_SHADOW.set(True)
    try:
        return replay_path_shape_k3_dead(
            reports_path=reports_path,
            proto=proto,
            workspace_a=ws_a,
            workspace_b=ws_b,
            rollout_fn=rollout_fn,
            measure_a=measure_a,
            measure_b=measure_b,
            t025_tag=t025_tag,
        )
    finally:
        PATH_SHAPE_K3_SHADOW.reset(tok_shape)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Awakening PATH_SHAPE K3 DEAD shadow measure")
    parser.add_argument("--skip-replay", action="store_true", help="Refuse Gate 2 grind if licensed")
    args = parser.parse_args(argv)
    out = run_path_shape_k3_dead(skip_replay=bool(args.skip_replay))
    print(
        json.dumps(
            {
                "overall": out.get("overall"),
                "parent_loaded": out.get("parent_loaded"),
                "replay_ran": out.get("replay_ran"),
                "gate1_tag": out.get("gate1_tag"),
                "tag": out.get("tag"),
                "HOLE_MOVED_A": out.get("HOLE_MOVED_A"),
                "HOLE_MOVED_B": out.get("HOLE_MOVED_B"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "run_path_shape_k3_dead"]
