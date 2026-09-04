"""CLI: payable-world tape, then scratch 46-dim V1 10k. License vs G2 a9ffa852 books."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_physics_eval import run_physics_eval
from lumina_core.birth.awakening_physics_flags import (
    TAG_PHYSICS_WORLD_FAIL,
    TAG_S_MISSING,
    compose_physics_flags,
    compute_physics_leg,
    empty_leg,
    license_physics,
)
from lumina_core.birth.awakening_physics_report import render_audit, render_verdict
from lumina_core.birth.awakening_physics_tables import (
    HONESTY_PARAGRAPH,
    table_t0_identity,
    table_t1_honesty,
    table_t2_leg,
    table_t3_license,
)
from lumina_core.birth.awakening_physics_tape import (
    BASELINE_SHA256,
    BASELINE_ZIP_NAME,
    CHILD_ZIP_NAME,
    FLAGS_NAME,
    ORIGIN_EYES_ZIP,
    PHYSICS_ROOT,
    PHYSICS_SEED,
    PhysicsProtocolError,
    inspect_physics_protocol,
    persist_physics_fixture,
    write_bytes_sha,
)
from lumina_core.birth.awakening_physics_train import run_physics_v1_train
from lumina_core.birth.birth_exit_policy_export import file_sha256
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import REPO_ROOT
from lumina_core.birth.genesis_cloud_workspace import overlay_sim_config
from lumina_core.birth.genesis_real_door import audit_real_door
from lumina_core.rl.observation_builder import OBSERVATION_DIM

POINTER = (
    "\n---\n\n"
    "## Pointer — AWAKENING_PHYSICS_TAPE\n\n"
    "Payable-world tape + scratch 46-dim V1 10k, license vs frozen a9ffa852 lives under "
    "`reports/awakening_physics_run`. Floor 150 stays. GENESIS_EYES_OK is false. REAL=no.\n"
)


def origin_guard_paths(*, repo: Path | None = None) -> dict[str, Path]:
    root = repo or REPO_ROOT
    g = root / "reports" / "genesis_cloud_run" / "artifacts"
    b = root / "reports" / "genesis_budget_run" / "artifacts"
    p = root / "reports" / "awakening_polish_run" / "artifacts"
    v = root / "reports" / "awakening_eyes_v2_run" / "artifacts"
    return {
        "genesis_mark_eyes_pi_star.zip": g / "genesis_mark_eyes_pi_star.zip",
        "genesis_birth_exit_pi_star.zip": g / "genesis_birth_exit_pi_star.zip",
        "genesis_eyes_budget_flags.json": b / "genesis_eyes_budget_flags.json",
        "awakening_mark_eyes_polish_flags.json": p / "awakening_mark_eyes_polish_flags.json",
        "awakening_mark_eyes_polish_pi_star.zip": p / "awakening_mark_eyes_polish_pi_star.zip",
        "awakening_mark_eyes_v2_flags.json": v / "awakening_mark_eyes_v2_flags.json",
        "awakening_mark_eyes_v2_pi_star.zip": v / "awakening_mark_eyes_v2_pi_star.zip",
    }


def snapshot_origin_artifacts(*, repo: Path | None = None) -> dict[str, str]:
    return {name: file_sha256(path) if path.is_file() else "" for name, path in origin_guard_paths(repo=repo).items()}


def assert_origin_untouched(before: dict[str, str], *, repo: Path | None = None) -> None:
    after = snapshot_origin_artifacts(repo=repo)
    for name, sha in before.items():
        if sha and after.get(name) != sha:
            raise PhysicsProtocolError(f"origin artifact overwritten: {name}")


def copy_baseline_zip(art: Path) -> str:
    art.mkdir(parents=True, exist_ok=True)
    if not ORIGIN_EYES_ZIP.is_file():
        raise PhysicsProtocolError("frozen living MARK_EYES zip missing")
    dest = art / BASELINE_ZIP_NAME
    shutil.copy2(ORIGIN_EYES_ZIP, dest)
    digest = write_bytes_sha(dest)
    if digest != BASELINE_SHA256:
        raise PhysicsProtocolError(f"baseline sha must be a9ffa852 pin, got {digest[:16]}")
    return digest


def prepare_physics_trees(*, repo: Path | None = None) -> tuple[Path, Path, Path]:
    root = (repo or REPO_ROOT) / "reports" / "awakening_physics_run"
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


def _git(sha_ref: str) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", sha_ref], cwd=str(REPO_ROOT), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def run_awakening_physics(*, repo: Path | None = None) -> dict[str, Any]:
    os.environ["LUMINA_FABRIC_SUPERVISOR"] = "0"
    os.environ["VOICE_ENABLED"] = "false"
    origin_before = snapshot_origin_artifacts(repo=repo)
    reports, work, art = prepare_physics_trees(repo=repo)
    os.environ["LUMINA_CONFIG"] = str((work / "config.yaml").resolve())
    proto = inspect_physics_protocol()
    gate0 = {
        "origin_main": _git("origin/main"),
        "POLICY_EDGE_MIN_TRADES": int(POLICY_EDGE_MIN_TRADES),
        "OBSERVATION_DIM": int(OBSERVATION_DIM),
        "pct_synthetic": real_data_percentage([{"source": "synthetic_cloud_fixture"}]),
        "pct_real_historical": real_data_percentage([{"source": "real_historical"}]),
        "pct_real": real_data_percentage([{"source": "real"}]),
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
    try:
        baseline_sha = copy_baseline_zip(art)
        fixture = persist_physics_fixture(work, art)
        world_ok = bool(fixture.get("world_ok"))
        if float(fixture.get("real_data_pct") or 0.0) == 100.0:
            raise PhysicsProtocolError("Gate 1 regression: real_data_pct printed 100")
    except PhysicsProtocolError as exc:
        missing = True
        reason = str(exc)
    if world_ok and not missing:
        try:
            base_eval = run_physics_eval(work=work, art=art, zip_path=art / BASELINE_ZIP_NAME, kind="base")
            if bool(base_eval.get("S_MISSING")) or not bool(base_eval.get("both_loaded")):
                missing = True
                reason = str(base_eval.get("reason") or "G2 load failed")
        except PhysicsProtocolError as exc:
            missing = True
            reason = str(exc)
    if world_ok and not missing:
        try:
            train_out = run_physics_v1_train(work=work, art=art, init_zip=None)
            if str(train_out.get("status") or "") != "ok":
                missing = True
                reason = str(train_out.get("error") or "G3 S_MISSING")
        except PhysicsProtocolError as exc:
            missing = True
            reason = str(exc)
    if world_ok and not missing:
        try:
            child_eval = run_physics_eval(work=work, art=art, zip_path=art / CHILD_ZIP_NAME, kind="child")
            if bool(child_eval.get("S_MISSING")):
                missing = True
                reason = str(child_eval.get("reason") or "G4 load failed")
        except PhysicsProtocolError as exc:
            missing = True
            reason = str(exc)
    g6 = audit_real_door(
        work=work,
        art=art,
        fixture=fixture or {"real_data_pct": 0.0, "source": "synthetic_cloud_fixture"},
        container_start_called=False,
        nt_called=False,
    )
    if float(g6.get("real_data_pct") or 0.0) == 100.0:
        missing = True
        reason = "Gate 1 regression: G6 real_data_pct printed 100"
    base_a = dict((base_eval.get("A") if base_eval else None) or {})
    base_b = dict((base_eval.get("B") if base_eval else None) or {})
    child_a = dict((child_eval.get("A") if child_eval else None) or {})
    child_b = dict((child_eval.get("B") if child_eval else None) or {})
    have_books = bool(base_eval or child_eval)
    if (not world_ok) or (not have_books):
        leg_a = {**empty_leg(), "S_MISSING": True}
        leg_b = {**empty_leg(), "S_MISSING": True}
    else:
        leg_a = compute_physics_leg(base_a, child_a, missing=missing)
        leg_b = compute_physics_leg(base_b, child_b, missing=missing)
    licensed = license_physics(leg_a, leg_b, missing=missing, world_ok=world_ok)
    flags = compose_physics_flags(
        {
            "fixture_train_hash": str(fixture.get("hash") or ""),
            "trend_up_frac_holdout": float(fixture.get("trend_up_frac_holdout") or 0.0),
            "trend_down_frac_holdout": float(fixture.get("trend_down_frac_holdout") or 0.0),
            "world_ok": bool(world_ok),
            "attempts": len(list(fixture.get("attempts") or [])),
            "baseline_sha256": baseline_sha,
            "child_sha256": str(train_out.get("child_sha256") or ""),
            "learn_called": bool(train_out.get("learn_called")),
            "actual_timesteps": int(train_out.get("actual_timesteps") or 0),
            "A": leg_a,
            "B": leg_b,
            **licensed,
            "real_data_pct": float(fixture.get("real_data_pct") or 0.0),
            "missing_reason": reason,
        }
    )
    if missing and world_ok:
        flags["tag"] = TAG_S_MISSING
        flags["law"] = "NONE"
        flags["licensed_next_family"] = "H_NONE"
    if not world_ok:
        flags["tag"] = TAG_PHYSICS_WORLD_FAIL
        flags["law"] = "NONE"
        flags["licensed_next_family"] = "H_NONE"
    t0 = table_t0_identity(
        origin_main=str(gate0["origin_main"]),
        train_hash=str(flags.get("fixture_train_hash") or ""),
        baseline_sha=str(flags.get("baseline_sha256") or ""),
        child_sha=str(flags.get("child_sha256") or ""),
    )
    t1 = table_t1_honesty()
    t2_a = table_t2_leg("A", leg_a)
    t2_b = table_t2_leg("B", leg_b)
    t3 = table_t3_license(licensed)
    _write_json(art / FLAGS_NAME, flags)
    (reports / "AWAKENING_PHYSICS_TAPE_AUDIT.md").write_text(
        render_audit(gate0=gate0, proto=proto, t0=t0, t1=t1, t2_a=t2_a, t2_b=t2_b, t3=t3, flags=flags, g6=g6),
        encoding="utf-8",
    )
    (reports / "AWAKENING_PHYSICS_TAPE_VERDICT.md").write_text(
        render_verdict(flags=flags, t2_a=t2_a, t2_b=t2_b), encoding="utf-8"
    )
    _append_logs(flags, fixture)
    assert_origin_untouched(origin_before, repo=repo)
    flags["g0"] = gate0
    return flags


def _append_logs(flags: dict[str, Any], fixture: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    attempts = list(fixture.get("attempts") or [])
    attempt_lines = []
    for i, row in enumerate(attempts):
        attempt_lines.append(
            f"  - attempt {i}: seed={row.get('seed')} drift_rth={row.get('drift_rth')} "
            f"kappa={row.get('range_kappa')} blocks={row.get('phase_blocks')} "
            f"train_up={row.get('train_trend_up_frac')} train_down={row.get('train_trend_down_frac')} "
            f"hold_up={row.get('holdout_trend_up_frac')} hold_down={row.get('holdout_trend_down_frac')}"
        )
    block = [
        f"## {now} — AWAKENING_PHYSICS_TAPE",
        "",
        "LAW: mark-slot inflation and V1-polish are closed.",
        "This window changes PRICE physics so enricher recovers trend.",
        "a9ffa852 is baseline, not clay.",
        f"Attempts: {len(attempts)}",
        *attempt_lines,
        f"Tag: {flags.get('tag')}",
        "",
        f"- tag=`{flags.get('tag')}` law=`{flags.get('law')}` "
        f"licensed_next_family=`{flags.get('licensed_next_family')}` world_ok=`{flags.get('world_ok')}`",
        f"- hash=`{flags.get('fixture_train_hash')}` seed=`{PHYSICS_SEED}` "
        f"baseline=`{str(flags.get('baseline_sha256') or '')[:16]}` "
        f"child=`{str(flags.get('child_sha256') or '')[:16]}`",
        f"- init_policy=scratch learn_called=`{flags.get('learn_called')}` "
        f"actual_timesteps=`{flags.get('actual_timesteps')}` "
        f"floor=150 GENESIS_EYES_OK=false used_v2_child=false REAL=no G6=`{flags.get('G6_tag')}`",
        "",
        HONESTY_PARAGRAPH,
        "",
    ]
    log_path = PHYSICS_ROOT / "LUMINA_PHYSICS_EXPERIMENT_LOG.md"
    existing = (
        log_path.read_text(encoding="utf-8")
        if log_path.is_file()
        else "# LUMINA Awakening PHYSICS_TAPE experiment log\n\n"
    )
    log_path.write_text(existing.rstrip() + "\n\n" + "\n".join(block), encoding="utf-8")
    birth_log = REPO_ROOT / "reports" / "birth_cloud_run" / "LUMINA_BIRTH_EXPERIMENT_LOG.md"
    if birth_log.is_file():
        text = birth_log.read_text(encoding="utf-8")
        if "Pointer — AWAKENING_PHYSICS_TAPE" not in text:
            birth_log.write_text(text.rstrip() + POINTER, encoding="utf-8")


def main() -> int:
    flags = run_awakening_physics()
    print(json.dumps(flags, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
