"""Evaluate-only Awakening ENTRY hole autopsy: parent π* on A then B.

Zero PPO steps. No learn(). Writes new JSONL / audit / verdict / flags only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_entry_autopsy import (
    EVAL_A_SEED,
    EVAL_B_SEED,
    FAMILY_H_AB_DISAGREE,
    INIT_SHA256,
    SOURCE,
    EntryAutopsyProtocolError,
    assert_eval_seed,
    assert_isolated_write,
    assert_parent_sha,
    assert_wire_vs_grind_a,
    compute_entry_flags,
    entry_ledger_path,
    isolated_workspace,
    load_close_jsonl,
    overall_entry_string,
    reports_dir,
    resolve_parent_path,
    table_t0,
    table_t1,
    table_t2,
    table_t3,
    table_t4,
)
from lumina_core.birth.awakening_entry_autopsy_path import inspect_entry_autopsy_protocol
from lumina_core.birth.awakening_entry_autopsy_report import (
    leg_payload,
    write_entry_autopsy_reports,
)
from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_grind_run import run_evaluate_only
from lumina_core.birth.awakening_select import price_sha16
from lumina_core.birth.awakening_select_env import select_runtime
from lumina_core.birth.birth_exit_policy_export import load_frozen_policy
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.awakening_entry_autopsy_run")


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
                "reused_manifest": True,
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
        "reused_manifest": False,
        "ticks_sha16": str(man.get("hash") or man.get("train_hash") or ""),
        "bars_sha16": str(man.get("raw_ticks_hash") or ""),
        "price_sha16": price_sha16(holdout),
    }


def run_entry_eval_leg(
    *,
    seed: int,
    holdout: list[dict[str, Any]],
    workspace_root: Path | str,
    reports: Path,
    policy_path: Path,
    rollout_fn: Any | None = None,
) -> Any:
    if TRAIN:
        raise RuntimeError("entry autopsy TRAIN must stay False")
    assert_eval_seed(int(seed))
    ledger = assert_isolated_write(entry_ledger_path(reports, leg="A" if seed == EVAL_A_SEED else "B"))
    loaded = load_frozen_policy(policy_path)
    if loaded is None:
        raise EntryAutopsyProtocolError(f"parent policy unloadable: {policy_path}")
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
    )


def run_entry_autopsy(
    *,
    reports: Path | str | None = None,
    workspace_a: Path | str | None = None,
    workspace_b: Path | str | None = None,
    rollout_fn: Any | None = None,
    skip_replay: bool = False,
) -> dict[str, Any]:
    """One evaluate-only parent grind A then B. Never calls learn()."""
    if TRAIN:
        raise RuntimeError("entry autopsy TRAIN must stay False")
    reports_path = Path(reports) if reports is not None else reports_dir()
    proto = inspect_entry_autopsy_protocol()
    if not proto.get("gate0_complete"):
        raise EntryAutopsyProtocolError(f"Gate 0 incomplete: {proto.get('missing_sites')}")
    iso = isolated_workspace(reports_path)
    iso.mkdir(parents=True, exist_ok=True)
    (iso / "state").mkdir(parents=True, exist_ok=True)
    ws_a = Path(workspace_a) if workspace_a is not None else reports_path / "workspace"
    ws_b = Path(workspace_b) if workspace_b is not None else reports_path / "workspace_grind_b"
    parent = resolve_parent_path(ws_a)
    try:
        zip_sha = assert_parent_sha(parent)
        parent_loaded = True
    except EntryAutopsyProtocolError:
        zip_sha = ""
        parent_loaded = False
    overall = overall_entry_string(parent_loaded=parent_loaded)
    empty_leg: dict[str, Any] = {
        "t0": table_t0([], zip_sha256=zip_sha or INIT_SHA256, ticks_sha16="", price_sha16_value="", optimizer_steps=0),
        "t1": table_t1([]),
        "t2": table_t2([]),
        "t3": table_t3([]),
        "flags": compute_entry_flags([]),
        "rows_n": 0,
    }
    if not parent_loaded or skip_replay:
        t4 = table_t4(reports_path / "artifacts")
        family = str(empty_leg["flags"]["licensed_family"])
        write_entry_autopsy_reports(
            reports=reports_path,
            overall=overall,
            family=str(family),
            zip_sha=zip_sha or INIT_SHA256,
            payload_a=empty_leg,
            payload_b=empty_leg,
            t4=t4,
            proto=proto,
            parent_loaded=parent_loaded,
        )
        return {"overall": overall, "parent_loaded": parent_loaded, "family": family}

    fixture_a = _load_or_build_fixture(ws_a, seed=EVAL_A_SEED)
    metrics_a = run_entry_eval_leg(
        seed=EVAL_A_SEED,
        holdout=list(fixture_a["holdout"]),
        workspace_root=ws_a,
        reports=reports_path,
        policy_path=parent,
        rollout_fn=rollout_fn,
    )
    if int(getattr(metrics_a, "optimizer_steps", 0) or 0) != 0:
        raise EntryAutopsyProtocolError("optimizer_steps must stay 0")
    path_a = assert_isolated_write(entry_ledger_path(reports_path, leg="A"))
    write_jsonl_sha256(path_a)
    rows_a = load_close_jsonl(path_a)
    payload_a = leg_payload(
        rows=rows_a,
        zip_sha=zip_sha,
        ticks_sha16=str(fixture_a["ticks_sha16"]),
        price_sha16_value=str(fixture_a["price_sha16"]),
        optimizer_steps=0,
    )
    assert_wire_vs_grind_a(
        wr_policy=float(payload_a["t0"]["wr_policy"]),
        n_policy=int(payload_a["t0"]["n_policy"]),
    )

    fixture_b = _load_or_build_fixture(ws_b, seed=EVAL_B_SEED)
    metrics_b = run_entry_eval_leg(
        seed=EVAL_B_SEED,
        holdout=list(fixture_b["holdout"]),
        workspace_root=ws_b,
        reports=reports_path,
        policy_path=parent,
        rollout_fn=rollout_fn,
    )
    if int(getattr(metrics_b, "optimizer_steps", 0) or 0) != 0:
        raise EntryAutopsyProtocolError("optimizer_steps must stay 0")
    path_b = assert_isolated_write(entry_ledger_path(reports_path, leg="B"))
    write_jsonl_sha256(path_b)
    rows_b = load_close_jsonl(path_b)
    payload_b = leg_payload(
        rows=rows_b,
        zip_sha=zip_sha,
        ticks_sha16=str(fixture_b["ticks_sha16"]),
        price_sha16_value=str(fixture_b["price_sha16"]),
        optimizer_steps=0,
    )
    family_a = str(payload_a["flags"]["licensed_family"])
    family_b = str(payload_b["flags"]["licensed_family"])
    family = family_a if family_a == family_b else FAMILY_H_AB_DISAGREE
    t4 = table_t4(reports_path / "artifacts")
    overall = overall_entry_string(parent_loaded=True)
    write_entry_autopsy_reports(
        reports=reports_path,
        overall=overall,
        family=family,
        zip_sha=zip_sha,
        payload_a=payload_a,
        payload_b=payload_b,
        t4=t4,
        proto=proto,
        parent_loaded=True,
    )
    logger.info(
        "awakening.entry_autopsy.done overall=%s family=%s n_a=%s n_b=%s",
        overall,
        family,
        payload_a["t0"]["n_all"],
        payload_b["t0"]["n_all"],
    )
    return {
        "overall": overall,
        "family": family,
        "parent_loaded": True,
        "A": payload_a,
        "B": payload_b,
        "t4": t4,
        "ledger_a": str(path_a),
        "ledger_b": str(path_b),
    }


def main() -> int:
    out = run_entry_autopsy()
    print(json.dumps({"overall": out.get("overall"), "family": out.get("family")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "run_entry_autopsy",
    "run_entry_eval_leg",
    "write_jsonl_sha256",
]
