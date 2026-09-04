"""Genesis cloud ladder orchestrator: first life Birth → Awakening → REAL door."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from lumina_core.birth.foundation_history import FOUNDATION_HISTORY_START_DAYS
from lumina_core.birth.genesis_cloud_birth import genesis_birth_exit_exam, run_genesis_birth
from lumina_core.birth.genesis_cloud_const import (
    BIRTH_INCOMPLETE,
    EYES_ZIP_NAME,
    G5_BIRTH_ONLY,
    G5_S_MISSING,
    G6_TAG,
    GENESIS_FIXTURE_SEED,
    GENESIS_INSTRUMENT,
    NEWBORN_ZIP_NAME,
    OVERALL,
    REPO_ROOT,
    SKIP_BIRTH_INCOMPLETE,
    SOURCE_GENESIS,
)
from lumina_core.birth.genesis_cloud_protocol import assert_genesis_seed
from lumina_core.birth.genesis_cloud_workspace import (
    assert_old_zips_untouched,
    persist_genesis_fixture,
    prepare_genesis_trees,
    snapshot_old_parent_zips,
)
from lumina_core.birth.genesis_mark_eyes_eval import run_genesis_eval
from lumina_core.birth.genesis_mark_eyes_train import run_genesis_mark_eyes_train
from lumina_core.birth.genesis_real_door import audit_real_door
from lumina_core.birth.genesis_reports import (
    append_birth_log_pointer,
    write_audit_verdict,
    write_autopsy,
    write_experiment_log,
    write_flags,
    write_next_experiments,
)
from lumina_core.birth.synthetic_cloud_fixture import SCHEMA_VERSION, SOURCE_LABEL
from lumina_core.rl.observation_builder import OBSERVATION_DIM


def _git(rev: str) -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", rev], cwd=str(REPO_ROOT), text=True)
        return out.strip()
    except Exception:
        return ""


def g0_recon(*, old_zips: dict[str, str]) -> dict[str, Any]:
    parent = REPO_ROOT / "reports" / "birth_cloud_run" / "artifacts" / "birth_exit_pi_star.zip"
    return {
        "origin_main": _git("origin/main"),
        "HEAD": _git("HEAD"),
        "OBS": int(OBSERVATION_DIM),
        "SOURCE_LABEL": SOURCE_LABEL,
        "SCHEMA_VERSION": SCHEMA_VERSION,
        "DAYS": int(FOUNDATION_HISTORY_START_DAYS),
        "OLD_PARENT_PRESENT_DO_NOT_LOAD": parent.is_file(),
        "old_parent_zip_sha256": old_zips.get("birth_exit_pi_star.zip", ""),
        "fixture_seed": GENESIS_FIXTURE_SEED,
        "mode": "sim",
        "practice_mode": False,
    }


def run_genesis_ladder(
    *,
    timeout_sec: int = 3600,
    target_trades: int = 8_000,
    rth_bar_seconds: int = 10,
    skip_birth: bool = False,
    repo: Path | None = None,
) -> dict[str, Any]:
    assert_genesis_seed(GENESIS_FIXTURE_SEED)
    root = repo or REPO_ROOT
    old_zips = snapshot_old_parent_zips(root)
    reports, work, art = prepare_genesis_trees(repo=root)
    g0 = g0_recon(old_zips=old_zips)
    (art / "g0_recon.json").write_text(json.dumps(g0, indent=2) + "\n", encoding="utf-8")
    try:
        g1 = persist_genesis_fixture(work, art, rth_bar_seconds=int(rth_bar_seconds))
    except (MemoryError, OSError):
        if int(rth_bar_seconds) < 20:
            g1 = persist_genesis_fixture(work, art, rth_bar_seconds=20)
            g1["wall_weakness"] = "rth_bar_seconds raised to 20 (calendar 90 untouched)"
        else:
            raise
    if skip_birth:
        g2 = {"status": BIRTH_INCOMPLETE, "skip": True, "checkpoint": {}, "progress": {}}
    else:
        g2 = run_genesis_birth(
            work,
            art,
            timeout_sec=int(timeout_sec),
            target_trades=int(target_trades),
            instrument=str(g1.get("symbol") or GENESIS_INSTRUMENT),
        )
    g3 = genesis_birth_exit_exam(work, art)
    skipped = SKIP_BIRTH_INCOMPLETE if not bool(g3.get("exited")) else ""
    g4: dict[str, Any]
    if skipped:
        g4 = {"status": "skipped", "skip_reason": skipped, "learn_called": False, "actual_timesteps": 0}
        (art / "g4_mark_eyes_train.json").write_text(json.dumps(g4, indent=2) + "\n")
    else:
        g4 = run_genesis_mark_eyes_train(work=work, art=art, init_zip=None)
        (art / "g4_mark_eyes_train.json").write_text(json.dumps(g4, indent=2, default=str) + "\n")
    newborn = art / NEWBORN_ZIP_NAME
    eyes = art / EYES_ZIP_NAME
    g5 = run_genesis_eval(
        work=work,
        art=art,
        newborn_zip=newborn if newborn.is_file() else None,
        eyes_zip=eyes if eyes.is_file() else None,
        learn_called=bool(g4.get("learn_called")),
        actual_timesteps=int(g4.get("actual_timesteps") or 0),
        skip_reason=skipped,
    )
    g6 = audit_real_door(
        work=work,
        art=art,
        fixture=g1,
        container_start_called=False,
        nt_called=False,
    )
    state = {"g1": g1, "g2": g2, "g3": g3, "g4": g4, "g5": g5, "g6": g6}
    rows = write_autopsy(art, work, state)
    write_next_experiments(art, rows)
    g5_tag = str(g5.get("G5_tag") or G5_BIRTH_ONLY)
    if str(g4.get("status")) == G5_S_MISSING:
        g5_tag = G5_S_MISSING
    flags = write_flags(
        art,
        {
            "source": SOURCE_GENESIS,
            "fixture_seed": GENESIS_FIXTURE_SEED,
            "fixture_train_hash": str(g1.get("hash") or ""),
            "real_data_pct": 0.0,
            "birth_exited": bool(g3.get("exited")),
            "birth_status": str(g2.get("status") or "") if g3.get("exited") else BIRTH_INCOMPLETE,
            "newborn_zip_sha256": str(g3.get("newborn_zip_sha256") or ""),
            "mark_eyes_child_sha256": str(g4.get("child_sha256") or ""),
            "learn_called": bool(g4.get("learn_called")),
            "actual_timesteps": int(g4.get("actual_timesteps") or 0),
            "G5_tag": g5_tag,
            "G6_tag": G6_TAG,
            "evolution_proof_stamped": False,
            "REAL": "no",
            "playground": False,
            "hook_default": False,
            "used_old_path_early": False,
            "used_old_parent_zip": False,
            "overall": OVERALL,
        },
    )
    write_experiment_log(reports, art, flags=flags, rows=rows)
    append_birth_log_pointer(root)
    write_audit_verdict(reports, g0=g0, g1=g1, g2=g2, g3=g3, g4=g4, g5=g5, g6=g6, rows=rows, flags=flags)
    assert_old_zips_untouched(old_zips, repo=root)
    flags["g0"] = g0
    return flags


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genesis first-life cloud ladder (SIM / synthetic)")
    parser.add_argument(
        "--timeout-sec", type=int, default=int(os.environ.get("LUMINA_GENESIS_BIRTH_TIMEOUT_SEC", "3600"))
    )
    parser.add_argument("--target-trades", type=int, default=8_000)
    parser.add_argument("--rth-bar-seconds", type=int, default=10)
    parser.add_argument("--skip-birth", action="store_true")
    args = parser.parse_args(argv)
    sys.path.insert(0, str(REPO_ROOT))
    out = run_genesis_ladder(
        timeout_sec=int(args.timeout_sec),
        target_trades=int(args.target_trades),
        rth_bar_seconds=int(args.rth_bar_seconds),
        skip_birth=bool(args.skip_birth),
    )
    print(
        json.dumps(
            {
                k: out.get(k)
                for k in ("overall", "G5_tag", "G6_tag", "REAL", "birth_exited", "birth_status", "fixture_train_hash")
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["g0_recon", "main", "run_genesis_ladder"]
