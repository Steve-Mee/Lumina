"""CLI: first-touch gate, then train-only +1.21/−1.04 vs a9ffa852. SCALE physics, new seed."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_geom_eval import run_geom_eval
from lumina_core.birth.awakening_geom_flags import (
    TAG_S_MISSING,
    compose_geom_flags,
    compute_geom_leg,
    empty_leg,
    license_geom,
)
from lumina_core.birth.awakening_geom_report import render_audit, render_verdict
from lumina_core.birth.awakening_geom_reward import GeomProtocolError
from lumina_core.birth.awakening_geom_tables import (
    HONESTY_PARAGRAPH,
    table_t0_identity,
    table_t1_honesty,
    table_t2_leg,
    table_t3_license,
)
from lumina_core.birth.awakening_geom_tape import (
    BASELINE_SHA256,
    BASELINE_ZIP_NAME,
    CHILD_ZIP_NAME,
    FLAGS_NAME,
    GEOM_ROOT,
    GEOM_SEEDS,
    ORIGIN_EYES_ZIP,
    inspect_geom_protocol,
    persist_geom_fixture,
)
from lumina_core.birth.awakening_geom_touch import G2_NAME, first_touch_books, write_g2_first_touch
from lumina_core.birth.awakening_geom_train import run_geom_v1_train, should_learn
from lumina_core.birth.awakening_occupancy_tape import write_bytes_sha
from lumina_core.birth.awakening_path_exit_k3 import load_close_jsonl
from lumina_core.birth.awakening_scale_run import origin_guard_paths as scale_origin_guard_paths
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
    "## Pointer — AWAKENING_GEOMETRY_REWARD\n\n"
    "First-touch gate 0.10 then train-only +1.21/−1.04 close reward on a NEW SCALE-physics "
    "tape lives under `reports/awakening_geom_run`. Floor 150 stays. GENESIS_EYES_OK is false. "
    "REAL=no. world_engineering_closed stays true. Policy goal 0.46 is not the gate.\n"
)
SCALE_FLAGS = REPO_ROOT / "reports" / "awakening_scale_run" / "artifacts" / "awakening_scale_flags.json"


def origin_guard_paths(*, repo: Path | None = None) -> dict[str, Path]:
    paths = dict(scale_origin_guard_paths(repo=repo))
    root = repo or REPO_ROOT
    sj = root / "reports" / "awakening_scale_run" / "artifacts"
    sl = root / "reports" / "awakening_scale_run"
    paths.update(
        {
            "awakening_scale_flags.json": sj / "awakening_scale_flags.json",
            "01_scale_fixture_manifest.json": sj / "01_scale_fixture_manifest.json",
            "awakening_scale_v1_pi_star.zip": sj / "awakening_scale_v1_pi_star.zip",
            "awakening_scale_v1_pi_star.json": sj / "awakening_scale_v1_pi_star.json",
            "scale_baseline_a9ffa852_pi_star.zip": sj / "baseline_a9ffa852_pi_star.zip",
            "scale_base_A_close_ledger.jsonl": sj / "scale_base_A_close_ledger.jsonl",
            "scale_base_B_close_ledger.jsonl": sj / "scale_base_B_close_ledger.jsonl",
            "scale_child_A_close_ledger.jsonl": sj / "scale_child_A_close_ledger.jsonl",
            "scale_child_B_close_ledger.jsonl": sj / "scale_child_B_close_ledger.jsonl",
            "AWAKENING_SCALE_VERDICT.md": sl / "AWAKENING_SCALE_VERDICT.md",
            "LUMINA_SCALE_EXPERIMENT_LOG.md": sl / "LUMINA_SCALE_EXPERIMENT_LOG.md",
        }
    )
    return paths


def snapshot_origin_artifacts(*, repo: Path | None = None) -> dict[str, str]:
    return {name: file_sha256(path) if path.is_file() else "" for name, path in origin_guard_paths(repo=repo).items()}


def assert_origin_untouched(before: dict[str, str], *, repo: Path | None = None) -> None:
    after = snapshot_origin_artifacts(repo=repo)
    for name, sha in before.items():
        if sha and after.get(name) != sha:
            raise GeomProtocolError(f"origin artifact overwritten: {name}")


def copy_baseline_zip(art: Path) -> str:
    art.mkdir(parents=True, exist_ok=True)
    if not ORIGIN_EYES_ZIP.is_file():
        raise GeomProtocolError("frozen living MARK_EYES zip missing")
    dest = art / BASELINE_ZIP_NAME
    shutil.copy2(ORIGIN_EYES_ZIP, dest)
    digest = write_bytes_sha(dest)
    if digest != BASELINE_SHA256:
        raise GeomProtocolError(f"baseline sha must be a9ffa852 pin, got {digest[:16]}")
    return digest


def prepare_geom_trees(*, repo: Path | None = None) -> tuple[Path, Path, Path]:
    root = (repo or REPO_ROOT) / "reports" / "awakening_geom_run"
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


def _restore_exam_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def live_check_g0() -> dict[str, Any]:
    if int(POLICY_EDGE_MIN_TRADES) != 150:
        raise GeomProtocolError("G0: POLICY_EDGE_MIN_TRADES must be 150")
    if not SCALE_FLAGS.is_file():
        raise GeomProtocolError("G0: origin scale flags missing")
    booked = json.loads(SCALE_FLAGS.read_text(encoding="utf-8"))
    if str(booked.get("tag") or "") != "SCALE_BODY":
        raise GeomProtocolError(f"G0: scale tag must be SCALE_BODY, got {booked.get('tag')}")
    if booked.get("world_engineering_closed") is not True:
        raise GeomProtocolError("G0: world_engineering_closed must stay true")
    n_a = int((booked.get("A") or {}).get("n_policy_child") or 0)
    n_b = int((booked.get("B") or {}).get("n_policy_child") or 0)
    if n_a != 150 or n_b != 150:
        raise GeomProtocolError(f"G0: scale child n_policy must be 150/150, got {n_a}/{n_b}")
    return {"tag": "SCALE_BODY", "world_engineering_closed": True, "n_policy_child": [n_a, n_b], "floor": 150}


def run_awakening_geom(*, repo: Path | None = None) -> dict[str, Any]:
    previous_env = {
        "LUMINA_FABRIC_SUPERVISOR": os.environ.get("LUMINA_FABRIC_SUPERVISOR"),
        "VOICE_ENABLED": os.environ.get("VOICE_ENABLED"),
        "LUMINA_CONFIG": os.environ.get("LUMINA_CONFIG"),
    }
    os.environ["LUMINA_FABRIC_SUPERVISOR"] = "0"
    os.environ["VOICE_ENABLED"] = "false"
    try:
        return _run_awakening_geom_body(repo=repo)
    finally:
        _restore_exam_env(previous_env)


def _run_awakening_geom_body(*, repo: Path | None = None) -> dict[str, Any]:
    origin_before = snapshot_origin_artifacts(repo=repo)
    reports, work, art = prepare_geom_trees(repo=repo)
    os.environ["LUMINA_CONFIG"] = str((work / "config.yaml").resolve())
    proto = inspect_geom_protocol()
    g0_booked = live_check_g0()
    gate0 = {
        "origin_main": _git("origin/main"),
        "POLICY_EDGE_MIN_TRADES": int(POLICY_EDGE_MIN_TRADES),
        "OBSERVATION_DIM": int(OBSERVATION_DIM),
        "pct_synthetic": real_data_percentage([{"source": "synthetic_cloud_fixture"}]),
        "inspect_complete": bool(proto.get("gate0_complete")),
        "scale_live": g0_booked,
        "seeds": list(GEOM_SEEDS),
        "drift_rth": 8.0e-6,
    }
    _write_json(art / "g0_recon.json", {**gate0, "protocol": proto})
    missing = False
    reason = ""
    fixture: dict[str, Any] = {}
    baseline_sha = BASELINE_SHA256
    train_out: dict[str, Any] = {}
    base_eval: dict[str, Any] = {}
    child_eval: dict[str, Any] = {}
    touch: dict[str, Any] = {}
    world_ok = False
    unhittable = False
    try:
        baseline_sha = copy_baseline_zip(art)
        fixture = persist_geom_fixture(work, art)
        world_ok = bool(fixture.get("world_ok"))
        if float(fixture.get("real_data_pct") or 0.0) == 100.0:
            raise GeomProtocolError("Gate 1 regression: real_data_pct printed 100")
        if not world_ok:
            missing = True
            reason = "G1 world_ok false"
    except GeomProtocolError as exc:
        missing = True
        reason = str(exc)
    if world_ok and not missing:
        try:
            base_eval = run_geom_eval(work=work, art=art, zip_path=art / BASELINE_ZIP_NAME, kind="base")
            if bool(base_eval.get("S_MISSING")) or not bool(base_eval.get("both_loaded")):
                missing = True
                reason = str(base_eval.get("reason") or "G2 load failed")
        except GeomProtocolError as exc:
            missing = True
            reason = str(exc)
    if world_ok and not missing and base_eval:
        rows_a = load_close_jsonl(Path(str((base_eval.get("A") or {}).get("ledger") or "")))
        rows_b = load_close_jsonl(Path(str((base_eval.get("B") or {}).get("ledger") or "")))
        touch = first_touch_books(rows_a, rows_b)
        write_g2_first_touch(art / G2_NAME, touch)
        if bool(touch.get("baseline_thin")):
            missing = True
            reason = "G2 n_policy < 150"
        unhittable = bool(touch.get("unhittable"))
    if world_ok and not missing and should_learn(
        unhittable=unhittable,
        n_policy_a=int(touch.get("n_policy_A") or 0),
        n_policy_b=int(touch.get("n_policy_B") or 0),
    ):
        try:
            train_out = run_geom_v1_train(
                work=work, art=art, train_seed=int(fixture.get("seed_used") or 0), init_zip=None
            )
            if str(train_out.get("status") or "") != "ok":
                missing = True
                reason = str(train_out.get("error") or "G3 S_MISSING")
        except GeomProtocolError as exc:
            missing = True
            reason = str(exc)
    if world_ok and not missing and bool(train_out.get("learn_called")):
        try:
            child_eval = run_geom_eval(work=work, art=art, zip_path=art / CHILD_ZIP_NAME, kind="child")
            if bool(child_eval.get("S_MISSING")):
                missing = True
                reason = str(child_eval.get("reason") or "G4 load failed")
        except GeomProtocolError as exc:
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
    have_books = bool(base_eval)
    if (not world_ok) or (not have_books):
        leg_a = {**empty_leg(), "S_MISSING": True}
        leg_b = {**empty_leg(), "S_MISSING": True}
        licensed = license_geom(leg_a, leg_b, missing=True)
    else:
        leg_a = compute_geom_leg(base_a, child_a, missing=missing)
        leg_b = compute_geom_leg(base_b, child_b, missing=missing)
        licensed = license_geom(leg_a, leg_b, missing=missing, unhittable=unhittable)
    flags = compose_geom_flags(
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
            "target_frac": float(touch.get("target_frac") or 0.0),
            "stop_frac": float(touch.get("stop_frac") or 0.0),
            "time_frac": float(touch.get("time_frac") or 0.0),
            "unhittable": bool(unhittable),
            "A": leg_a,
            "B": leg_b,
            **licensed,
            "real_data_pct": float(fixture.get("real_data_pct") or 0.0),
            "missing_reason": reason,
        }
    )
    if missing and not unhittable:
        flags["tag"] = TAG_S_MISSING
        flags["law"] = "NONE"
        flags["licensed_next_family"] = "H_NONE"
    flags["world_engineering_closed"] = True
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
    (reports / "AWAKENING_GEOM_AUDIT.md").write_text(
        render_audit(
            gate0=gate0, proto=proto, t0=t0, t1=t1, t2_a=t2_a, t2_b=t2_b, t3=t3, flags=flags, g6=g6, touch=touch
        ),
        encoding="utf-8",
    )
    (reports / "AWAKENING_GEOM_VERDICT.md").write_text(
        render_verdict(flags=flags, t2_a=t2_a, t2_b=t2_b), encoding="utf-8"
    )
    _append_logs(flags, fixture, touch)
    assert_origin_untouched(origin_before, repo=repo)
    flags["g0"] = gate0
    return flags


def _append_logs(flags: dict[str, Any], fixture: dict[str, Any], touch: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    a, b = flags.get("A") or {}, flags.get("B") or {}
    block = [
        f"## {now} — AWAKENING_GEOMETRY_REWARD",
        "",
        "LAW: last world knob was SCALE. This window is the Awakening payoff.",
        "First-touch gate 0.10. Policy goal 0.46 is not the gate.",
        f"target/stop/time fracs={flags.get('target_frac')}/{flags.get('stop_frac')}/{flags.get('time_frac')}",
        f"tag=`{flags.get('tag')}`",
        "",
        f"- tag=`{flags.get('tag')}` law=`{flags.get('law')}` "
        f"licensed_next_family=`{flags.get('licensed_next_family')}` "
        f"in_band=`{flags.get('in_band')}` world_ok=`{flags.get('world_ok')}` "
        f"world_engineering_closed=`{flags.get('world_engineering_closed')}` "
        f"unhittable=`{flags.get('unhittable')}` drift_rth=`{flags.get('drift_rth')}`",
        f"- seed_used=`{flags.get('seed_used')}` hash=`{flags.get('fixture_train_hash')}` "
        f"slope_abs_used=`{flags.get('slope_abs_used')}` prod_slope_abs=`{flags.get('prod_slope_abs')}` "
        f"train_force_open=`{flags.get('train_force_open')}` eval_force_open=`{flags.get('eval_force_open')}` "
        f"baseline=`{str(flags.get('baseline_sha256') or '')[:16]}` "
        f"child=`{str(flags.get('child_sha256') or '')[:16]}`",
        f"- n_policy G2 base A/B={a.get('n_policy_base')}/{b.get('n_policy_base')} "
        f"G4 child A/B={a.get('n_policy_child')}/{b.get('n_policy_child')}",
        f"- first-touch n_target/n_stop/n_time={touch.get('n_target')}/{touch.get('n_stop')}/{touch.get('n_time')} "
        f"pooled={touch.get('n_policy_pooled')}",
        f"- init_policy=scratch learn_called=`{flags.get('learn_called')}` "
        f"actual_timesteps=`{flags.get('actual_timesteps')}` "
        f"floor=150 floor_waived=false guard_bypassed=false GENESIS_EYES_OK=false "
        f"oracle_regime=false REAL=no G6=`{flags.get('G6_tag')}`",
        "",
        HONESTY_PARAGRAPH,
        "",
    ]
    log_path = GEOM_ROOT / "LUMINA_GEOM_EXPERIMENT_LOG.md"
    existing = (
        log_path.read_text(encoding="utf-8")
        if log_path.is_file()
        else "# LUMINA Awakening GEOMETRY_REWARD experiment log\n\n"
    )
    log_path.write_text(existing.rstrip() + "\n\n" + "\n".join(block), encoding="utf-8")
    birth_log = REPO_ROOT / "reports" / "birth_cloud_run" / "LUMINA_BIRTH_EXPERIMENT_LOG.md"
    if birth_log.is_file():
        text = birth_log.read_text(encoding="utf-8")
        if "Pointer — AWAKENING_GEOMETRY_REWARD" not in text:
            birth_log.write_text(text.rstrip() + POINTER, encoding="utf-8")


def main() -> int:
    flags = run_awakening_geom()
    print(json.dumps(flags, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
