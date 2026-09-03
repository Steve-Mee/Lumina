"""PATH_EXIT K3 runner: one evaluate-only parent replay A then B with hook ON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_path_exit_k3 import (
    INIT_SHA256,
    OVERALL_INCONCLUSIVE,
    PathExitK3ProtocolError,
    assert_parent_sha,
    overall_path_exit_k3_string,
    reports_dir,
    resolve_parent_path,
)
from lumina_core.birth.awakening_path_exit_k3_eval import (
    replay_path_exit_k3,
    write_inconclusive,
)
from lumina_core.birth.awakening_path_exit_k3_path import inspect_path_exit_k3_protocol
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.awakening_path_exit_k3_run")


def run_path_exit_k3(
    *,
    reports: Path | str | None = None,
    workspace_a: Path | str | None = None,
    workspace_b: Path | str | None = None,
    rollout_fn: Any | None = None,
    skip_replay: bool = False,
) -> dict[str, Any]:
    """Default = real replay with hook ON. Tests may skip_replay."""
    if TRAIN:
        raise RuntimeError("path exit k3 TRAIN must stay False")
    reports_path = Path(reports) if reports is not None else reports_dir()
    proto = inspect_path_exit_k3_protocol()
    if not proto.get("gate0_complete"):
        raise PathExitK3ProtocolError(f"Gate 0 incomplete: {proto.get('missing_sites')}")
    artifacts = reports_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    ws_a = Path(workspace_a) if workspace_a is not None else reports_path / "workspace"
    ws_b = Path(workspace_b) if workspace_b is not None else reports_path / "workspace_grind_b"
    parent_loaded = False
    zip_sha = INIT_SHA256
    try:
        parent = resolve_parent_path(ws_a)
        zip_sha = assert_parent_sha(parent)
        parent_loaded = True
    except PathExitK3ProtocolError:
        parent_loaded = False
    if skip_replay:
        overall = overall_path_exit_k3_string(
            parent_loaded=parent_loaded,
            skip_replay=True,
            optimizer_steps=0,
            replay_ran=False,
        )
        return write_inconclusive(
            reports_path=reports_path,
            proto=proto,
            zip_sha=zip_sha,
            parent_loaded=parent_loaded,
            skip_replay=True,
            replay_ran=False,
            overall=OVERALL_INCONCLUSIVE if overall == OVERALL_INCONCLUSIVE else overall,
        )
    if not parent_loaded:
        return write_inconclusive(
            reports_path=reports_path,
            proto=proto,
            zip_sha=zip_sha,
            parent_loaded=False,
            skip_replay=False,
            replay_ran=False,
            overall=OVERALL_INCONCLUSIVE,
        )
    return replay_path_exit_k3(
        reports_path=reports_path,
        proto=proto,
        workspace_a=ws_a,
        workspace_b=ws_b,
        rollout_fn=rollout_fn,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Awakening PATH_EXIT K3 shadow flatten-at-3")
    parser.add_argument("--skip-replay", action="store_true", help="Refuse grind; write INCONCLUSIVE")
    args = parser.parse_args(argv)
    out = run_path_exit_k3(skip_replay=bool(args.skip_replay))
    print(
        json.dumps(
            {
                "overall": out.get("overall"),
                "parent_loaded": out.get("parent_loaded"),
                "replay_ran": out.get("replay_ran"),
                "tag": out.get("tag"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "run_path_exit_k3"]
