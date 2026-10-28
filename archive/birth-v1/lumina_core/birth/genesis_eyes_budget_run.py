"""CLI: frozen first-life students on a NEW thick holdout. No learn."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import REPO_ROOT
from lumina_core.birth.genesis_eyes_budget import (
    BUDGET_FIXTURE_SEED,
    BUDGET_ROOT,
    STUDENT_BIRTH_SHA256,
    STUDENT_EYES_SHA256,
    BudgetProtocolError,
    assert_g5_ledgers_untouched,
    copy_frozen_students,
    g5_ledger_fingerprints,
    inspect_budget_protocol,
    persist_budget_fixture,
    prepare_budget_trees,
)
from lumina_core.birth.genesis_eyes_budget_eval import run_budget_eval
from lumina_core.birth.genesis_eyes_budget_flags import (
    TAG_S_MISSING,
    compose_budget_flags,
    compute_budget_leg,
    empty_leg,
    license_budget,
)
from lumina_core.birth.genesis_eyes_budget_report import render_audit, render_verdict
from lumina_core.birth.genesis_eyes_budget_tables import (
    HONESTY_PARAGRAPH,
    table_t0_identity,
    table_t1_honesty,
    table_t2_leg,
    table_t3_license,
)
from lumina_core.birth.genesis_real_door import audit_real_door
from lumina_core.rl.observation_builder import OBSERVATION_DIM

POINTER = (
    "\n---\n\n"
    "## Pointer — GENESIS_EYES_BUDGET\n\n"
    "Frozen first-life zips on a NEW thick holdout live under "
    "`reports/genesis_budget_run`. No second 10k. Floor 150 stays. "
    "GENESIS_EYES_OK is false. REAL=no.\n"
)


def _git(sha_ref: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", sha_ref], cwd=str(REPO_ROOT), text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def run_genesis_eyes_budget(*, repo: Path | None = None) -> dict[str, Any]:
    os.environ["LUMINA_FABRIC_SUPERVISOR"] = "0"
    os.environ["VOICE_ENABLED"] = "false"
    g5_before = g5_ledger_fingerprints()
    reports, work, art = prepare_budget_trees(repo=repo)
    os.environ["LUMINA_CONFIG"] = str((work / "config.yaml").resolve())
    proto = inspect_budget_protocol()
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
    students: dict[str, str] = {
        "student_birth_sha256": STUDENT_BIRTH_SHA256,
        "student_eyes_sha256": STUDENT_EYES_SHA256,
    }
    try:
        students = copy_frozen_students(art)
        fixture = persist_budget_fixture(work, art)
        if float(fixture.get("real_data_pct") or 0.0) == 100.0:
            raise BudgetProtocolError("Gate 1 regression: real_data_pct printed 100")
    except BudgetProtocolError as exc:
        missing = True
        reason = str(exc)
    eval_out: dict[str, Any] = {}
    if not missing:
        try:
            eval_out = run_budget_eval(
                work=work, art=art, holdout_pct=float(fixture.get("holdout_pct") or 0.40)
            )
            missing = bool(eval_out.get("S_MISSING"))
            reason = str(eval_out.get("reason") or reason)
        except BudgetProtocolError as exc:
            missing = True
            reason = str(exc)
    g6 = audit_real_door(
        work=work, art=art, fixture=fixture or {"real_data_pct": 0.0, "source": "synthetic_cloud_fixture"},
        container_start_called=False, nt_called=False,
    )
    if float(g6.get("real_data_pct") or 0.0) == 100.0:
        missing = True
        reason = "Gate 1 regression: G6 real_data_pct printed 100"
    birth_a = dict(eval_out.get("birth_A") or {})
    birth_b = dict(eval_out.get("birth_B") or {})
    eyes_a = dict(eval_out.get("eyes_A") or {})
    eyes_b = dict(eval_out.get("eyes_B") or {})
    leg_a = compute_budget_leg(birth_a, eyes_a, missing=missing) if eval_out else empty_leg()
    leg_b = compute_budget_leg(birth_b, eyes_b, missing=missing) if eval_out else empty_leg()
    if not eval_out:
        leg_a = {**empty_leg(), "S_MISSING": True}
        leg_b = {**empty_leg(), "S_MISSING": True}
    licensed = license_budget(leg_a, leg_b, missing=missing)
    flags = compose_budget_flags(
        {
            "fixture_train_hash": str(fixture.get("hash") or ""),
            "holdout_tick_count": int(fixture.get("holdout_tick_count") or 0),
            "ticks_per_leg": list(fixture.get("ticks_per_leg") or eval_out.get("ticks_per_leg") or [0, 0]),
            "student_birth_sha256": students.get("student_birth_sha256", STUDENT_BIRTH_SHA256),
            "student_eyes_sha256": students.get("student_eyes_sha256", STUDENT_EYES_SHA256),
            "A": leg_a,
            "B": leg_b,
            **licensed,
            "real_data_pct": float(fixture.get("real_data_pct") or 0.0),
            "missing_reason": reason,
        }
    )
    if missing:
        flags["tag"] = TAG_S_MISSING
        flags["law"] = "NONE"
        flags["licensed_next_family"] = "H_NONE"
    t0 = table_t0_identity(
        origin_main=str(gate0["origin_main"]),
        train_hash=str(flags.get("fixture_train_hash") or ""),
        birth_sha=str(flags.get("student_birth_sha256") or ""),
        eyes_sha=str(flags.get("student_eyes_sha256") or ""),
    )
    t1 = table_t1_honesty()
    t2_a = table_t2_leg("A", leg_a)
    t2_b = table_t2_leg("B", leg_b)
    t3 = table_t3_license(licensed)
    _write_json(art / "genesis_eyes_budget_flags.json", flags)
    (reports / "GENESIS_EYES_BUDGET_AUDIT.md").write_text(
        render_audit(gate0=gate0, proto=proto, t0=t0, t1=t1, t2_a=t2_a, t2_b=t2_b, t3=t3, flags=flags, g6=g6),
        encoding="utf-8",
    )
    (reports / "GENESIS_EYES_BUDGET_VERDICT.md").write_text(
        render_verdict(flags=flags, t2_a=t2_a, t2_b=t2_b), encoding="utf-8"
    )
    _append_logs(flags)
    assert_g5_ledgers_untouched(g5_before)
    flags["g0"] = gate0
    return flags


def _append_logs(flags: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    block = [
        f"## {now} — GENESIS_EYES_BUDGET",
        "",
        f"- tag=`{flags.get('tag')}` law=`{flags.get('law')}` "
        f"licensed_next_family=`{flags.get('licensed_next_family')}`",
        f"- hash=`{flags.get('fixture_train_hash')}` holdout=`{flags.get('holdout_tick_count')}` "
        f"legs=`{flags.get('ticks_per_leg')}` seed=`{BUDGET_FIXTURE_SEED}`",
        f"- HOLE_MOVED A/B=`{flags.get('HOLE_MOVED_A')}`/`{flags.get('HOLE_MOVED_B')}` "
        f"floor=150 GENESIS_EYES_OK=false learn_called=false REAL=no G6=`{flags.get('G6_tag')}`",
        "",
        HONESTY_PARAGRAPH,
        "",
    ]
    log_path = BUDGET_ROOT / "LUMINA_GENESIS_BUDGET_EXPERIMENT_LOG.md"
    existing = (
        log_path.read_text(encoding="utf-8")
        if log_path.is_file()
        else "# LUMINA Genesis EYES budget experiment log\n\n"
    )
    if "GENESIS_EYES_BUDGET" not in existing or flags.get("tag"):
        log_path.write_text(existing.rstrip() + "\n\n" + "\n".join(block), encoding="utf-8")
    birth_log = REPO_ROOT / "reports" / "birth_cloud_run" / "LUMINA_BIRTH_EXPERIMENT_LOG.md"
    if birth_log.is_file():
        text = birth_log.read_text(encoding="utf-8")
        if "Pointer — GENESIS_EYES_BUDGET" not in text:
            birth_log.write_text(text.rstrip() + POINTER, encoding="utf-8")


def main() -> int:
    flags = run_genesis_eyes_budget()
    print(json.dumps(flags, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
