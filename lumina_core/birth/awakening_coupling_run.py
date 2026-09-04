"""CLI: diagnose DOWN-death, one fix, then scratch 46-dim V1 10k iff world_ok."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_coupling_diagnose import (
    BASELINE_SHA256,
    BASELINE_ZIP_NAME,
    CHILD_ZIP_NAME,
    COUPLING_ROOT,
    FLAGS_NAME,
    CouplingProtocolError,
    inspect_coupling_protocol,
    run_g1_diagnose,
)
from lumina_core.birth.awakening_coupling_eval import run_coupling_eval
from lumina_core.birth.awakening_coupling_fix import persist_coupling_exam
from lumina_core.birth.awakening_coupling_flags import (
    TAG_COUPLING_FAIL,
    TAG_COUPLING_UNKNOWN,
    TAG_S_MISSING,
    compose_coupling_flags,
    compute_coupling_leg,
    empty_leg,
    license_coupling,
)
from lumina_core.birth.awakening_coupling_report import render_audit, render_verdict
from lumina_core.birth.awakening_coupling_tables import (
    HONESTY_PARAGRAPH,
    table_t0_identity,
    table_t1_honesty,
    table_t2_leg,
    table_t3_license,
)
from lumina_core.birth.awakening_coupling_train import run_coupling_v1_train
from lumina_core.birth.awakening_physics_tape import ORIGIN_EYES_ZIP, write_bytes_sha
from lumina_core.birth.birth_exit_policy_export import file_sha256
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import REPO_ROOT
from lumina_core.birth.genesis_cloud_workspace import overlay_sim_config
from lumina_core.birth.genesis_real_door import audit_real_door
from lumina_core.rl.observation_builder import OBSERVATION_DIM

POINTER = (
    "\n---\n\n"
    "## Pointer — AWAKENING_ENRICHER_COUPLING\n\n"
    "Diagnose post-enrich TREND_DOWN death + one fix, then scratch 46-dim V1 10k "
    "iff world_ok, lives under `reports/awakening_coupling_run`. Floor 150 stays. "
    "GENESIS_EYES_OK is false. REAL=no.\n"
)


def origin_guard_paths(*, repo: Path | None = None) -> dict[str, Path]:
    root = repo or REPO_ROOT
    g = root / "reports" / "genesis_cloud_run" / "artifacts"
    b = root / "reports" / "genesis_budget_run" / "artifacts"
    p = root / "reports" / "awakening_polish_run" / "artifacts"
    v = root / "reports" / "awakening_eyes_v2_run" / "artifacts"
    ph = root / "reports" / "awakening_physics_run" / "artifacts"
    return {
        "genesis_mark_eyes_pi_star.zip": g / "genesis_mark_eyes_pi_star.zip",
        "genesis_birth_exit_pi_star.zip": g / "genesis_birth_exit_pi_star.zip",
        "genesis_eyes_budget_flags.json": b / "genesis_eyes_budget_flags.json",
        "awakening_mark_eyes_polish_flags.json": p / "awakening_mark_eyes_polish_flags.json",
        "awakening_mark_eyes_polish_pi_star.zip": p / "awakening_mark_eyes_polish_pi_star.zip",
        "awakening_mark_eyes_v2_flags.json": v / "awakening_mark_eyes_v2_flags.json",
        "awakening_mark_eyes_v2_pi_star.zip": v / "awakening_mark_eyes_v2_pi_star.zip",
        "awakening_physics_flags.json": ph / "awakening_physics_flags.json",
        "baseline_a9ffa852_pi_star.zip": ph / "baseline_a9ffa852_pi_star.zip",
    }


def snapshot_origin_artifacts(*, repo: Path | None = None) -> dict[str, str]:
    return {name: file_sha256(path) if path.is_file() else "" for name, path in origin_guard_paths(repo=repo).items()}


def assert_origin_untouched(before: dict[str, str], *, repo: Path | None = None) -> None:
    after = snapshot_origin_artifacts(repo=repo)
    for name, sha in before.items():
        if sha and after.get(name) != sha:
            raise CouplingProtocolError(f"origin artifact overwritten: {name}")


def copy_baseline_zip(art: Path) -> str:
    art.mkdir(parents=True, exist_ok=True)
    if not ORIGIN_EYES_ZIP.is_file():
        raise CouplingProtocolError("frozen living MARK_EYES zip missing")
    dest = art / BASELINE_ZIP_NAME
    shutil.copy2(ORIGIN_EYES_ZIP, dest)
    digest = write_bytes_sha(dest)
    if digest != BASELINE_SHA256:
        raise CouplingProtocolError(f"baseline sha must be a9ffa852 pin, got {digest[:16]}")
    return digest


def prepare_coupling_trees(*, repo: Path | None = None) -> tuple[Path, Path, Path]:
    root = (repo or REPO_ROOT) / "reports" / "awakening_coupling_run"
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


def body_exam_enabled(world_ok: bool, cause: str) -> bool:
    # body skipped when not world_ok
    return bool(world_ok) and str(cause) != "OTHER"


def _git(sha_ref: str) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", sha_ref], cwd=str(REPO_ROOT), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def run_awakening_coupling(*, repo: Path | None = None) -> dict[str, Any]:
    os.environ["LUMINA_FABRIC_SUPERVISOR"] = "0"
    os.environ["VOICE_ENABLED"] = "false"
    origin_before = snapshot_origin_artifacts(repo=repo)
    reports, work, art = prepare_coupling_trees(repo=repo)
    os.environ["LUMINA_CONFIG"] = str((work / "config.yaml").resolve())
    proto = inspect_coupling_protocol()
    gate0 = {
        "origin_main": _git("origin/main"),
        "POLICY_EDGE_MIN_TRADES": int(POLICY_EDGE_MIN_TRADES),
        "OBSERVATION_DIM": int(OBSERVATION_DIM),
        "pct_synthetic": real_data_percentage([{"source": "synthetic_cloud_fixture"}]),
        "inspect_complete": bool(proto.get("gate0_complete")),
    }
    _write_json(art / "g0_recon.json", {**gate0, "protocol": proto})
    missing = False
    reason = ""
    fixture: dict[str, Any] = {}
    baseline_sha = BASELINE_SHA256
    train_out: dict[str, Any] = {}
    base_eval: dict[str, Any] = {}
    child_eval: dict[str, Any] = {}
    world_ok = False
    g1 = run_g1_diagnose(art=art)
    cause = str(g1.get("cause") or "OTHER")
    try:
        baseline_sha = copy_baseline_zip(art)
        if cause != "OTHER":
            fixture = persist_coupling_exam(work, art, cause=cause, g1_numbers=dict(g1.get("numbers") or {}))
            world_ok = bool(fixture.get("world_ok"))
            if float(fixture.get("real_data_pct") or 0.0) == 100.0:
                raise CouplingProtocolError("Gate 1 regression: real_data_pct printed 100")
    except CouplingProtocolError as exc:
        missing = True
        reason = str(exc)
    if body_exam_enabled(world_ok, cause) and not missing:
        try:
            base_eval = run_coupling_eval(work=work, art=art, zip_path=art / BASELINE_ZIP_NAME, kind="base")
            if bool(base_eval.get("S_MISSING")) or not bool(base_eval.get("both_loaded")):
                missing = True
                reason = str(base_eval.get("reason") or "G4 load failed")
        except CouplingProtocolError as exc:
            missing = True
            reason = str(exc)
    if body_exam_enabled(world_ok, cause) and not missing:
        try:
            train_out = run_coupling_v1_train(work=work, art=art, init_zip=None)
            if str(train_out.get("status") or "") != "ok":
                missing = True
                reason = str(train_out.get("error") or "G5 S_MISSING")
        except CouplingProtocolError as exc:
            missing = True
            reason = str(exc)
    if body_exam_enabled(world_ok, cause) and not missing:
        try:
            child_eval = run_coupling_eval(work=work, art=art, zip_path=art / CHILD_ZIP_NAME, kind="child")
            if bool(child_eval.get("S_MISSING")):
                missing = True
                reason = str(child_eval.get("reason") or "G6 load failed")
        except CouplingProtocolError as exc:
            missing = True
            reason = str(exc)
    g6 = audit_real_door(
        work=work,
        art=art,
        fixture=fixture or {"real_data_pct": 0.0, "source": "synthetic_cloud_fixture"},
        container_start_called=False,
        nt_called=False,
    )
    have_books = bool(base_eval or child_eval)
    if (not world_ok) or (not have_books):
        leg_a = {**empty_leg(), "S_MISSING": True}
        leg_b = {**empty_leg(), "S_MISSING": True}
    else:
        leg_a = compute_coupling_leg(dict((base_eval.get("A") or {})), dict((child_eval.get("A") or {})), missing=missing)
        leg_b = compute_coupling_leg(dict((base_eval.get("B") or {})), dict((child_eval.get("B") or {})), missing=missing)
    licensed = license_coupling(leg_a, leg_b, missing=missing, world_ok=world_ok, cause=cause)
    flags = compose_coupling_flags(
        {
            "cause": cause,
            "cause_detail": str(g1.get("cause_detail") or ""),
            "fix_kind": str(fixture.get("fix_kind") or ("" if cause == "OTHER" else cause)),
            "exam_hash": str(fixture.get("hash") or ""),
            "train_up_frac": float(fixture.get("trend_up_frac_train") or 0.0),
            "train_down_frac": float(fixture.get("trend_down_frac_train") or 0.0),
            "hold_up_frac": float(fixture.get("trend_up_frac_holdout") or 0.0),
            "hold_down_frac": float(fixture.get("trend_down_frac_holdout") or 0.0),
            "world_ok": bool(world_ok),
            "baseline_sha256": baseline_sha,
            "child_sha256": str(train_out.get("child_sha256") or ""),
            "learn_called": bool(train_out.get("learn_called")),
            "actual_timesteps": int(train_out.get("actual_timesteps") or 0),
            "A": leg_a,
            "B": leg_b,
            **licensed,
            "real_data_pct": float(fixture.get("real_data_pct") or 0.0),
            "enr_threshold_pos": float(fixture.get("enr_threshold_pos") or 0.15),
            "enr_threshold_neg": float(fixture.get("enr_threshold_neg") or -0.15),
            "missing_reason": reason,
        }
    )
    if missing and world_ok:
        flags["tag"] = TAG_S_MISSING
        flags["law"] = "NONE"
        flags["licensed_next_family"] = "H_NONE"
    if cause == "OTHER":
        flags["tag"] = TAG_COUPLING_UNKNOWN
    elif not world_ok:
        flags["tag"] = TAG_COUPLING_FAIL
    t0 = table_t0_identity(
        origin_main=str(gate0["origin_main"]),
        exam_hash=str(flags.get("exam_hash") or ""),
        baseline_sha=str(flags.get("baseline_sha256") or ""),
        child_sha=str(flags.get("child_sha256") or ""),
        cause=cause,
        fix_kind=str(flags.get("fix_kind") or ""),
    )
    t1 = table_t1_honesty()
    t2_a = table_t2_leg("A", leg_a)
    t2_b = table_t2_leg("B", leg_b)
    t3 = table_t3_license(licensed)
    _write_json(art / FLAGS_NAME, flags)
    (reports / "AWAKENING_COUPLING_AUDIT.md").write_text(
        render_audit(gate0=gate0, proto=proto, t0=t0, t1=t1, t2_a=t2_a, t2_b=t2_b, t3=t3, flags=flags, g6=g6),
        encoding="utf-8",
    )
    (reports / "AWAKENING_COUPLING_VERDICT.md").write_text(
        render_verdict(flags=flags, t2_a=t2_a, t2_b=t2_b), encoding="utf-8"
    )
    _append_logs(flags, g1, fixture)
    assert_origin_untouched(origin_before, repo=repo)
    flags["g0"] = gate0
    return flags


def _append_logs(flags: dict[str, Any], g1: dict[str, Any], fixture: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    nums = dict(g1.get("numbers") or {})
    block = [
        f"## {now} — AWAKENING_ENRICHER_COUPLING",
        "",
        "LAW: #40 WORLD_FAIL stood. This window diagnoses DOWN-death then one fix.",
        f"cause=`{flags.get('cause')}` {g1.get('cause_detail')}",
        f"numbers drift_up={nums.get('drift_up_used')} drift_down={nums.get('drift_down_used')} "
        f"slope_up={nums.get('mean_slope_emitted_up')} slope_down={nums.get('mean_slope_emitted_down')} "
        f"down_floor={nums.get('down_near_floor_n')} up_cap={nums.get('up_near_cap_n')}",
        f"fix_kind=`{flags.get('fix_kind')}`",
        f"new fracs train_up={flags.get('train_up_frac')} train_down={flags.get('train_down_frac')} "
        f"hold_up={flags.get('hold_up_frac')} hold_down={flags.get('hold_down_frac')}",
        f"tag=`{flags.get('tag')}`",
        "",
        f"- tag=`{flags.get('tag')}` law=`{flags.get('law')}` "
        f"licensed_next_family=`{flags.get('licensed_next_family')}` world_ok=`{flags.get('world_ok')}`",
        f"- hash=`{flags.get('exam_hash')}` baseline=`{str(flags.get('baseline_sha256') or '')[:16]}` "
        f"child=`{str(flags.get('child_sha256') or '')[:16]}`",
        f"- learn_called=`{flags.get('learn_called')}` actual_timesteps=`{flags.get('actual_timesteps')}` "
        f"floor=150 GENESIS_EYES_OK=false oracle_regime=false REAL=no G6=`{flags.get('G6_tag')}`",
        "",
        HONESTY_PARAGRAPH,
        "",
    ]
    log_path = COUPLING_ROOT / "LUMINA_COUPLING_EXPERIMENT_LOG.md"
    existing = (
        log_path.read_text(encoding="utf-8")
        if log_path.is_file()
        else "# LUMINA Awakening ENRICHER_COUPLING experiment log\n\n"
    )
    log_path.write_text(existing.rstrip() + "\n\n" + "\n".join(block), encoding="utf-8")
    birth_log = REPO_ROOT / "reports" / "birth_cloud_run" / "LUMINA_BIRTH_EXPERIMENT_LOG.md"
    if birth_log.is_file():
        text = birth_log.read_text(encoding="utf-8")
        if "Pointer — AWAKENING_ENRICHER_COUPLING" not in text:
            birth_log.write_text(text.rstrip() + POINTER, encoding="utf-8")


def main() -> int:
    flags = run_awakening_coupling()
    print(json.dumps(flags, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
