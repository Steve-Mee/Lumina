"""SELECT_OBJ P_BOUNCE_WEAK runner: Gate 1 measure + license. No replay."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_path_exit_k3 import PathExitK3ProtocolError
from lumina_core.birth.awakening_select_obj_bounce import (
    GATE0_MAIN_SHA,
    INIT_SHA256,
    PATH_EXIT_K3_SHADOW,
    PATH_SHAPE_K3_SHADOW,
    SelectObjBounceProtocolError,
    assert_parent_sha,
    load_close_jsonl,
    overall_select_obj_bounce_string,
    path_early_source_path,
    policy_only_rows,
    reports_dir,
    resolve_parent_path,
)
from lumina_core.birth.awakening_select_obj_bounce_flags import compute_obj_bounce_flags, empty_measure, license_obj
from lumina_core.birth.awakening_select_obj_bounce_path import inspect_select_obj_bounce_protocol
from lumina_core.birth.awakening_select_obj_bounce_report import write_select_obj_bounce_reports
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.awakening_select_obj_bounce_run")


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        return ""
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _measure_leg(artifacts: Path, *, leg: str) -> tuple[dict[str, Any], str, bool, int]:
    path = path_early_source_path(artifacts, leg=leg)
    if not path.is_file():
        return empty_measure(missing=True), "", False, 0
    rows = load_close_jsonl(path)
    return compute_obj_bounce_flags(rows), _file_sha256(path), True, int(len(policy_only_rows(rows)))


def run_select_obj_bounce(
    *,
    reports: Path | str | None = None,
    workspace_a: Path | str | None = None,
) -> dict[str, Any]:
    if TRAIN:
        raise RuntimeError("select obj bounce TRAIN must stay False")
    reports_path = Path(reports) if reports is not None else reports_dir()
    proto = inspect_select_obj_bounce_protocol()
    artifacts = reports_path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    hook_true = bool(PATH_EXIT_K3_SHADOW.get()) or bool(PATH_SHAPE_K3_SHADOW.get())
    measure_a, sha_a, present_a, n_policy_a = _measure_leg(artifacts, leg="A")
    measure_b, sha_b, present_b, n_policy_b = _measure_leg(artifacts, leg="B")
    path_early_present = bool(present_a and present_b)
    if not proto.get("gate0_complete"):
        measure_a = {**measure_a, "S_MISSING": True}
        measure_b = {**measure_b, "S_MISSING": True}
    parent_loaded = False
    zip_sha = INIT_SHA256
    ws_a = Path(workspace_a) if workspace_a is not None else reports_path / "workspace"
    try:
        parent = resolve_parent_path(ws_a)
        zip_sha = assert_parent_sha(parent)
        parent_loaded = True
    except (PathExitK3ProtocolError, SelectObjBounceProtocolError):
        parent_loaded = False
    overall = overall_select_obj_bounce_string(
        path_early_present=path_early_present,
        optimizer_steps=0,
        hook_true=hook_true,
        forbidden_write=False,
        gate1_complete=True,
    )
    flags = write_select_obj_bounce_reports(
        reports=reports_path,
        overall=overall,
        zip_sha=zip_sha,
        measure_a=measure_a,
        measure_b=measure_b,
        proto=proto,
        sha_a=sha_a,
        sha_b=sha_b,
        path_early_present=path_early_present,
        hooks_false=not hook_true,
        gate0_sha=GATE0_MAIN_SHA,
        n_policy=n_policy_a or n_policy_b,
    )
    licensed = license_obj(measure_a, measure_b)
    logger.info(
        "awakening.select_obj_bounce overall=%s tag=%s family=%s",
        overall,
        licensed.get("tag"),
        licensed.get("licensed_next_family"),
    )
    return {
        "overall": overall,
        "parent_loaded": parent_loaded,
        "replay_ran": False,
        "learn_called": False,
        "gate1_tag": flags.get("gate1_tag"),
        "tag": flags.get("tag"),
        "law": flags.get("law"),
        "licensed_next_family": flags.get("licensed_next_family"),
        "A_measure": measure_a,
        "B_measure": measure_b,
        "proto": proto,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Awakening SELECT_OBJ P_BOUNCE_WEAK score measure")
    parser.parse_args(argv)
    out = run_select_obj_bounce()
    print(
        json.dumps(
            {
                "overall": out.get("overall"),
                "parent_loaded": out.get("parent_loaded"),
                "replay_ran": out.get("replay_ran"),
                "learn_called": out.get("learn_called"),
                "gate1_tag": out.get("gate1_tag"),
                "tag": out.get("tag"),
                "law": out.get("law"),
                "licensed_next_family": out.get("licensed_next_family"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "run_select_obj_bounce"]
