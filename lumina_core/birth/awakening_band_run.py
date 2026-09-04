"""CLI: band-gated #44-physics tape, FORCE_OPEN train-only 10k, license vs a9ffa852."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_band_eval import run_band_eval
from lumina_core.birth.awakening_band_flags import (
    TAG_S_MISSING,
    compose_band_flags,
    compute_band_leg,
    empty_leg,
    license_band,
)
from lumina_core.birth.awakening_band_report import render_audit, render_verdict
from lumina_core.birth.awakening_band_tables import (
    HONESTY_PARAGRAPH,
    table_t0_identity,
    table_t1_honesty,
    table_t2_leg,
    table_t3_license,
)
from lumina_core.birth.awakening_band_tape import (
    BAND_ROOT,
    BAND_SEEDS,
    BASELINE_SHA256,
    BASELINE_ZIP_NAME,
    CHILD_ZIP_NAME,
    FLAGS_NAME,
    ORIGIN_EYES_ZIP,
    BandProtocolError,
    inspect_band_protocol,
    persist_band_fixture,
)
from lumina_core.birth.awakening_band_train import run_band_v1_train
from lumina_core.birth.awakening_conv_enrich import PHYSICS_SLOPE_ABS, PROD_SLOPE_ABS
from lumina_core.birth.awakening_obj_run import origin_guard_paths as obj_origin_guard_paths
from lumina_core.birth.awakening_occupancy_tape import write_bytes_sha
from lumina_core.birth.awakening_strat_split import SPLITTER_NAME
from lumina_core.birth.birth_exit_policy_export import file_sha256
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import REPO_ROOT
from lumina_core.birth.genesis_cloud_workspace import overlay_sim_config
from lumina_core.birth.genesis_real_door import audit_real_door
from lumina_core.rl.observation_builder import OBSERVATION_DIM

POINTER = (
    "\n---\n\n"
    "## Pointer — AWAKENING_PRICE_BAND\n\n"
    "Tradeable NQ band [12000, 28000] on a NEW #44-physics tape + scratch 46-dim V1 10k "
    "lives under `reports/awakening_band_run`. Floor 150 stays. 1% guard intact. "
    "GENESIS_EYES_OK is false. REAL=no. Production ±0.15 unchanged.\n"
)
OBJ_FLAGS = REPO_ROOT / "reports" / "awakening_obj_run" / "artifacts" / "awakening_obj_flags.json"


def origin_guard_paths(*, repo: Path | None = None) -> dict[str, Path]:
    paths = dict(obj_origin_guard_paths(repo=repo))
    root = repo or REPO_ROOT
    oj = root / "reports" / "awakening_obj_run" / "artifacts"
    ol = root / "reports" / "awakening_obj_run"
    paths.update(
        {
            "awakening_obj_flags.json": oj / "awakening_obj_flags.json",
            "01_obj_fixture_manifest.json": oj / "01_obj_fixture_manifest.json",
            "awakening_obj_v1_pi_star.zip": oj / "awakening_obj_v1_pi_star.zip",
            "AWAKENING_OBJ_VERDICT.md": ol / "AWAKENING_OBJ_VERDICT.md",
            "LUMINA_OBJ_EXPERIMENT_LOG.md": ol / "LUMINA_OBJ_EXPERIMENT_LOG.md",
        }
    )
    return paths


def snapshot_origin_artifacts(*, repo: Path | None = None) -> dict[str, str]:
    return {name: file_sha256(path) if path.is_file() else "" for name, path in origin_guard_paths(repo=repo).items()}


def assert_origin_untouched(before: dict[str, str], *, repo: Path | None = None) -> None:
    after = snapshot_origin_artifacts(repo=repo)
    for name, sha in before.items():
        if sha and after.get(name) != sha:
            raise BandProtocolError(f"origin artifact overwritten: {name}")


def copy_baseline_zip(art: Path) -> str:
    art.mkdir(parents=True, exist_ok=True)
    if not ORIGIN_EYES_ZIP.is_file():
        raise BandProtocolError("frozen living MARK_EYES zip missing")
    dest = art / BASELINE_ZIP_NAME
    shutil.copy2(ORIGIN_EYES_ZIP, dest)
    digest = write_bytes_sha(dest)
    if digest != BASELINE_SHA256:
        raise BandProtocolError(f"baseline sha must be a9ffa852 pin, got {digest[:16]}")
    return digest


def prepare_band_trees(*, repo: Path | None = None) -> tuple[Path, Path, Path]:
    root = (repo or REPO_ROOT) / "reports" / "awakening_band_run"
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


def body_exam_enabled(world_ok: bool) -> bool:
    return bool(world_ok)


def _git(sha_ref: str) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", sha_ref], cwd=str(REPO_ROOT), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def live_check_g0() -> dict[str, Any]:
    if int(POLICY_EDGE_MIN_TRADES) != 150:
        raise BandProtocolError("G0: POLICY_EDGE_MIN_TRADES must be 150")
    if not OBJ_FLAGS.is_file():
        raise BandProtocolError("G0: origin obj flags missing")
    booked = json.loads(OBJ_FLAGS.read_text(encoding="utf-8"))
    if str(booked.get("tag") or "") != "OBJ_THIN":
        raise BandProtocolError(f"G0: #45 tag must be OBJ_THIN, got {booked.get('tag')}")
    n_a = int((booked.get("A") or {}).get("n_policy_child") or 0)
    n_b = int((booked.get("B") or {}).get("n_policy_child") or 0)
    if n_a != 0 or n_b != 0:
        raise BandProtocolError(f"G0: booked n_policy must be 0/0, got {n_a}/{n_b}")
    return {"tag": "OBJ_THIN", "n_policy_child_A": n_a, "n_policy_child_B": n_b, "floor": 150}


def run_awakening_band(*, repo: Path | None = None) -> dict[str, Any]:
    os.environ["LUMINA_FABRIC_SUPERVISOR"] = "0"
    os.environ["VOICE_ENABLED"] = "false"
    origin_before = snapshot_origin_artifacts(repo=repo)
    reports, work, art = prepare_band_trees(repo=repo)
    os.environ["LUMINA_CONFIG"] = str((work / "config.yaml").resolve())
    proto = inspect_band_protocol()
    g0_booked = live_check_g0()
    gate0 = {
        "origin_main": _git("origin/main"),
        "POLICY_EDGE_MIN_TRADES": int(POLICY_EDGE_MIN_TRADES),
        "OBSERVATION_DIM": int(OBSERVATION_DIM),
        "pct_synthetic": real_data_percentage([{"source": "synthetic_cloud_fixture"}]),
        "PHYSICS_SLOPE_ABS": float(PHYSICS_SLOPE_ABS),
        "PROD_SLOPE_ABS": float(PROD_SLOPE_ABS),
        "inspect_complete": bool(proto.get("gate0_complete")),
        "obj_live": g0_booked,
        "seeds": list(BAND_SEEDS),
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
    world_fail = False
    try:
        baseline_sha = copy_baseline_zip(art)
        fixture = persist_band_fixture(work, art)
        world_ok = bool(fixture.get("world_ok"))
        world_fail = bool(fixture.get("world_fail"))
        if float(fixture.get("real_data_pct") or 0.0) == 100.0:
            raise BandProtocolError("Gate 1 regression: real_data_pct printed 100")
    except BandProtocolError as exc:
        missing = True
        reason = str(exc)
    if body_exam_enabled(world_ok) and not missing:
        try:
            base_eval = run_band_eval(work=work, art=art, zip_path=art / BASELINE_ZIP_NAME, kind="base")
            if bool(base_eval.get("S_MISSING")) or not bool(base_eval.get("both_loaded")):
                missing = True
                reason = str(base_eval.get("reason") or "G4 load failed")
        except BandProtocolError as exc:
            missing = True
            reason = str(exc)
    if body_exam_enabled(world_ok) and not missing:
        try:
            train_out = run_band_v1_train(work=work, art=art, train_seed=int(fixture.get("seed_used") or 0), init_zip=None)
            if str(train_out.get("status") or "") != "ok":
                missing = True
                reason = str(train_out.get("error") or "G5 S_MISSING")
        except BandProtocolError as exc:
            missing = True
            reason = str(exc)
    if body_exam_enabled(world_ok) and not missing:
        try:
            child_eval = run_band_eval(work=work, art=art, zip_path=art / CHILD_ZIP_NAME, kind="child")
            if bool(child_eval.get("S_MISSING")):
                missing = True
                reason = str(child_eval.get("reason") or "G6 load failed")
        except BandProtocolError as exc:
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
    if world_fail:
        leg_a, leg_b = empty_leg(), empty_leg()
        licensed = license_band(leg_a, leg_b, world_fail=True)
    elif (not world_ok) or (not have_books):
        leg_a = {**empty_leg(), "S_MISSING": True}
        leg_b = {**empty_leg(), "S_MISSING": True}
        licensed = license_band(leg_a, leg_b, missing=True)
    else:
        leg_a = compute_band_leg(base_a, child_a, missing=missing)
        leg_b = compute_band_leg(base_b, child_b, missing=missing)
        licensed = license_band(leg_a, leg_b, missing=missing)
    flags = compose_band_flags(
        {
            "phase_blocks": int(fixture.get("phase_blocks") or 6),
            "splitter": SPLITTER_NAME,
            "seed_used": int(fixture.get("seed_used") or 0),
            "attempts": list(fixture.get("attempts") or []),
            "price_min": float(fixture.get("price_min") or 0.0),
            "price_max": float(fixture.get("price_max") or 0.0),
            "in_band": bool(fixture.get("in_band")),
            "world_ok": bool(world_ok),
            "fixture_train_hash": str(fixture.get("hash") or ""),
            "baseline_sha256": baseline_sha,
            "child_sha256": str(train_out.get("child_sha256") or ""),
            "learn_called": bool(train_out.get("learn_called")),
            "actual_timesteps": int(train_out.get("actual_timesteps") or 0),
            "train_force_open": bool(train_out.get("train_force_open")),
            "eval_force_open": False,
            "A": leg_a,
            "B": leg_b,
            **licensed,
            "real_data_pct": float(fixture.get("real_data_pct") or 0.0),
            "missing_reason": reason,
        }
    )
    if missing and not world_fail:
        flags["tag"] = TAG_S_MISSING
        flags["law"] = "NONE"
        flags["licensed_next_family"] = "H_NONE"
    t0 = table_t0_identity(
        origin_main=str(gate0["origin_main"]),
        train_hash=str(flags.get("fixture_train_hash") or ""),
        baseline_sha=str(flags.get("baseline_sha256") or ""),
        child_sha=str(flags.get("child_sha256") or ""),
        seed_used=int(flags.get("seed_used") or 0),
    )
    t1 = table_t1_honesty()
    t2_a = table_t2_leg("A", leg_a)
    t2_b = table_t2_leg("B", leg_b)
    t3 = table_t3_license(licensed)
    _write_json(art / FLAGS_NAME, flags)
    (reports / "AWAKENING_BAND_AUDIT.md").write_text(
        render_audit(gate0=gate0, proto=proto, t0=t0, t1=t1, t2_a=t2_a, t2_b=t2_b, t3=t3, flags=flags, g6=g6),
        encoding="utf-8",
    )
    (reports / "AWAKENING_BAND_VERDICT.md").write_text(render_verdict(flags=flags, t2_a=t2_a, t2_b=t2_b), encoding="utf-8")
    _append_logs(flags)
    assert_origin_untouched(origin_before, repo=repo)
    flags["g0"] = gate0
    return flags


def _append_logs(flags: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    a, b = flags.get("A") or {}, flags.get("B") or {}
    block = [
        f"## {now} — AWAKENING_PRICE_BAND",
        "",
        "LAW: #45 1.46e7 path made 1% guard refuse every plant.",
        "This window refuses out-of-band seeds. Does not disable the guard.",
        f"attempts={json.dumps(flags.get('attempts') or [], default=str)}",
        f"tag=`{flags.get('tag')}`",
        "",
        f"- tag=`{flags.get('tag')}` law=`{flags.get('law')}` "
        f"licensed_next_family=`{flags.get('licensed_next_family')}` "
        f"in_band=`{flags.get('in_band')}` world_ok=`{flags.get('world_ok')}`",
        f"- seed_used=`{flags.get('seed_used')}` price_min=`{flags.get('price_min')}` "
        f"price_max=`{flags.get('price_max')}` hash=`{flags.get('fixture_train_hash')}` "
        f"slope_abs_used=`{flags.get('slope_abs_used')}` prod_slope_abs=`{flags.get('prod_slope_abs')}` "
        f"train_force_open=`{flags.get('train_force_open')}` eval_force_open=`{flags.get('eval_force_open')}` "
        f"baseline=`{str(flags.get('baseline_sha256') or '')[:16]}` "
        f"child=`{str(flags.get('child_sha256') or '')[:16]}`",
        f"- n_policy G4 base A/B={a.get('n_policy_base')}/{b.get('n_policy_base')} "
        f"G6 child A/B={a.get('n_policy_child')}/{b.get('n_policy_child')}",
        f"- init_policy=scratch learn_called=`{flags.get('learn_called')}` "
        f"actual_timesteps=`{flags.get('actual_timesteps')}` "
        f"floor=150 floor_waived=false guard_bypassed=false GENESIS_EYES_OK=false "
        f"oracle_regime=false REAL=no G6=`{flags.get('G6_tag')}`",
        "",
        HONESTY_PARAGRAPH,
        "",
    ]
    log_path = BAND_ROOT / "LUMINA_BAND_EXPERIMENT_LOG.md"
    existing = log_path.read_text(encoding="utf-8") if log_path.is_file() else "# LUMINA Awakening PRICE_BAND experiment log\n\n"
    log_path.write_text(existing.rstrip() + "\n\n" + "\n".join(block), encoding="utf-8")
    birth_log = REPO_ROOT / "reports" / "birth_cloud_run" / "LUMINA_BIRTH_EXPERIMENT_LOG.md"
    if birth_log.is_file():
        text = birth_log.read_text(encoding="utf-8")
        if "Pointer — AWAKENING_PRICE_BAND" not in text:
            birth_log.write_text(text.rstrip() + POINTER, encoding="utf-8")


def main() -> int:
    flags = run_awakening_band()
    print(json.dumps(flags, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
