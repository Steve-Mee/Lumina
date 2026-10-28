"""Evaluate-only Awakening OPEN_POLICY_SIGNAL autopsy: parent π* on A then B.

Zero PPO steps. No learn(). Writes new JSONL / audit / verdict / flags only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_grind_run import run_evaluate_only
from lumina_core.birth.awakening_edge import policy_only_rows
from lumina_core.birth.awakening_open_policy_signal import (
    EVAL_A_SEED,
    EVAL_B_SEED,
    INIT_SHA256,
    OVERALL_INCONCLUSIVE,
    SOURCE,
    OpenPolicySignalProtocolError,
    assert_eval_seed,
    assert_isolated_write,
    assert_parent_sha,
    assert_wire_vs_autopsy_a,
    compute_open_policy_signal_flags,
    isolated_workspace,
    load_close_jsonl,
    overall_policy_signal_string,
    policy_signal_ledger_path,
    reports_dir,
    resolve_parent_path,
)
from lumina_core.birth.awakening_open_policy_signal_path import inspect_open_policy_signal_protocol
from lumina_core.birth.awakening_open_policy_signal_report import (
    leg_payload,
    write_open_policy_signal_reports,
)
from lumina_core.birth.awakening_open_policy_signal_tables import (
    table_t0,
    table_t1,
    table_t1b,
    table_t2,
    table_t3,
    table_t4,
    table_t5,
)
from lumina_core.birth.awakening_select import price_sha16
from lumina_core.birth.awakening_select_env import select_runtime
from lumina_core.birth.birth_exit_policy_export import load_frozen_policy
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.awakening_open_policy_signal_run")

GATE0_SHA = "a9c5e32b10ed517c78091806b9f58c8e65a3f621"


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


def run_policy_signal_eval_leg(
    *,
    seed: int,
    holdout: list[dict[str, Any]],
    workspace_root: Path | str,
    reports: Path,
    policy_path: Path,
    rollout_fn: Any | None = None,
) -> Any:
    if TRAIN:
        raise RuntimeError("open policy signal TRAIN must stay False")
    assert_eval_seed(int(seed))
    ledger = assert_isolated_write(
        policy_signal_ledger_path(reports, leg="A" if seed == EVAL_A_SEED else "B")
    )
    loaded = load_frozen_policy(policy_path)
    if loaded is None:
        raise OpenPolicySignalProtocolError(f"parent policy unloadable: {policy_path}")
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


def capture_ok_share(rows: list[dict[str, Any]]) -> float:
    """Share of policy opens with at least one of value/entropy/margin present."""
    policy = policy_only_rows(rows)
    if not policy:
        return 0.0
    keys = ("open_policy_value", "open_policy_entropy", "open_policy_action_margin")
    ok = sum(1 for row in policy if any(k in row and row.get(k) is not None for k in keys))
    return float(ok) / float(len(policy))


def _apply_capture_floor(payload: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    share = capture_ok_share(rows)
    flags = payload.get("flags") or {}
    flags["capture_ok_share"] = float(share)
    if share < 0.80:
        flags["S_MISSING_SIGNAL"] = True
        flags["tag"] = "S_MISSING"
        flags["winning_P"] = "none"
    payload["flags"] = flags


def _empty_leg(zip_sha: str) -> dict[str, Any]:
    return {
        "t0": table_t0(
            [],
            zip_sha256=zip_sha or INIT_SHA256,
            ticks_sha16="",
            price_sha16_value="",
            optimizer_steps=0,
        ),
        "t1": table_t1([]),
        "t1b": table_t1b([]),
        "t2": table_t2([]),
        "t3": table_t3([]),
        "t5": table_t5([]),
        "flags": compute_open_policy_signal_flags([]),
        "rows_n": 0,
    }


def run_open_policy_signal(
    *,
    reports: Path | str | None = None,
    workspace_a: Path | str | None = None,
    workspace_b: Path | str | None = None,
    rollout_fn: Any | None = None,
    skip_replay: bool = False,
) -> dict[str, Any]:
    """One evaluate-only parent grind A then B. Never calls learn()."""
    if TRAIN:
        raise RuntimeError("open policy signal TRAIN must stay False")
    reports_path = Path(reports) if reports is not None else reports_dir()
    proto = inspect_open_policy_signal_protocol()
    if not proto.get("gate0_complete"):
        raise OpenPolicySignalProtocolError(f"Gate 0 incomplete: {proto.get('missing_sites')}")
    iso = isolated_workspace(reports_path)
    iso.mkdir(parents=True, exist_ok=True)
    (iso / "state").mkdir(parents=True, exist_ok=True)
    ws_a = Path(workspace_a) if workspace_a is not None else reports_path / "workspace"
    ws_b = Path(workspace_b) if workspace_b is not None else reports_path / "workspace_grind_b"
    parent = resolve_parent_path(ws_a)
    try:
        zip_sha = assert_parent_sha(parent)
        parent_loaded = True
    except OpenPolicySignalProtocolError:
        zip_sha = ""
        parent_loaded = False
    overall = overall_policy_signal_string(
        parent_loaded=parent_loaded,
        skip_replay=bool(skip_replay),
        n_u_a=0,
        s_missing_signal=True,
        optimizer_steps=0,
    )
    empty_leg = _empty_leg(zip_sha)
    if not parent_loaded or skip_replay:
        t4 = table_t4(reports_path / "artifacts")
        write_open_policy_signal_reports(
            reports=reports_path,
            overall=OVERALL_INCONCLUSIVE if skip_replay or not parent_loaded else overall,
            zip_sha=zip_sha or INIT_SHA256,
            payload_a=empty_leg,
            payload_b=empty_leg,
            t4=t4,
            proto=proto,
            parent_loaded=parent_loaded,
            gate0_sha=GATE0_SHA,
            skip_replay=bool(skip_replay),
        )
        return {
            "overall": OVERALL_INCONCLUSIVE if skip_replay or not parent_loaded else overall,
            "parent_loaded": parent_loaded,
            "family": "H_NONE",
            "skip_replay": bool(skip_replay),
        }

    fixture_a = _load_or_build_fixture(ws_a, seed=EVAL_A_SEED)
    metrics_a = run_policy_signal_eval_leg(
        seed=EVAL_A_SEED,
        holdout=list(fixture_a["holdout"]),
        workspace_root=ws_a,
        reports=reports_path,
        policy_path=parent,
        rollout_fn=rollout_fn,
    )
    if int(getattr(metrics_a, "optimizer_steps", 0) or 0) != 0:
        raise OpenPolicySignalProtocolError("optimizer_steps must stay 0")
    path_a = assert_isolated_write(policy_signal_ledger_path(reports_path, leg="A"))
    write_jsonl_sha256(path_a)
    rows_a = load_close_jsonl(path_a)
    payload_a = leg_payload(
        rows=rows_a,
        zip_sha=zip_sha,
        ticks_sha16=str(fixture_a["ticks_sha16"]),
        price_sha16_value=str(fixture_a["price_sha16"]),
        optimizer_steps=0,
    )
    _apply_capture_floor(payload_a, rows_a)
    assert_wire_vs_autopsy_a(
        wr_policy=float(payload_a["t0"]["wr_policy"]),
        n_policy=int(payload_a["t0"]["n_policy"]),
    )

    fixture_b = _load_or_build_fixture(ws_b, seed=EVAL_B_SEED)
    metrics_b = run_policy_signal_eval_leg(
        seed=EVAL_B_SEED,
        holdout=list(fixture_b["holdout"]),
        workspace_root=ws_b,
        reports=reports_path,
        policy_path=parent,
        rollout_fn=rollout_fn,
    )
    if int(getattr(metrics_b, "optimizer_steps", 0) or 0) != 0:
        raise OpenPolicySignalProtocolError("optimizer_steps must stay 0")
    path_b = assert_isolated_write(policy_signal_ledger_path(reports_path, leg="B"))
    write_jsonl_sha256(path_b)
    rows_b = load_close_jsonl(path_b)
    payload_b = leg_payload(
        rows=rows_b,
        zip_sha=zip_sha,
        ticks_sha16=str(fixture_b["ticks_sha16"]),
        price_sha16_value=str(fixture_b["price_sha16"]),
        optimizer_steps=0,
    )
    _apply_capture_floor(payload_b, rows_b)
    t4 = table_t4(reports_path / "artifacts")
    flags_a = payload_a.get("flags") or {}
    overall = overall_policy_signal_string(
        parent_loaded=True,
        skip_replay=False,
        n_u_a=int(flags_a.get("n_U") or 0),
        s_missing_signal=bool(flags_a.get("S_MISSING_SIGNAL")),
        optimizer_steps=0,
    )
    write_open_policy_signal_reports(
        reports=reports_path,
        overall=overall,
        zip_sha=zip_sha,
        payload_a=payload_a,
        payload_b=payload_b,
        t4=t4,
        proto=proto,
        parent_loaded=True,
        gate0_sha=GATE0_SHA,
        fixture_a=fixture_a,
        fixture_b=fixture_b,
        skip_replay=False,
    )
    logger.info(
        "awakening.open_policy_signal.done overall=%s tag=%s n_a=%s n_b=%s",
        overall,
        (payload_a.get("flags") or {}).get("tag"),
        payload_a["t0"]["n_all"],
        payload_b["t0"]["n_all"],
    )
    return {
        "overall": overall,
        "parent_loaded": True,
        "A": payload_a,
        "B": payload_b,
        "t4": t4,
        "ledger_a": str(path_a),
        "ledger_b": str(path_b),
    }


def main() -> int:
    out = run_open_policy_signal()
    print(
        json.dumps(
            {"overall": out.get("overall"), "parent_loaded": out.get("parent_loaded")},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "capture_ok_share",
    "run_open_policy_signal",
    "run_policy_signal_eval_leg",
    "write_jsonl_sha256",
]
