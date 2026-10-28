"""CLI: scratch 48-dim V2 one 10k on a NEW tape. License vs G2 a9ffa852 books."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.birth.awakening_mark_eyes_v2 import (
    BASELINE_SHA256,
    BASELINE_ZIP_NAME,
    CHILD_ZIP_NAME,
    FIXTURE_SEED,
    FLAGS_NAME,
    V2_ROOT,
    MarkEyesV2ProtocolError,
    assert_origin_untouched,
    copy_baseline_zip,
    inspect_v2_protocol,
    persist_v2_fixture,
    prepare_v2_trees,
    snapshot_origin_artifacts,
)
from lumina_core.birth.awakening_mark_eyes_v2_eval import run_v2_eval
from lumina_core.birth.awakening_mark_eyes_v2_flags import (
    TAG_S_MISSING,
    compose_v2_flags,
    compute_v2_leg,
    empty_leg,
    license_v2,
)
from lumina_core.birth.awakening_mark_eyes_v2_report import render_audit, render_verdict
from lumina_core.birth.awakening_mark_eyes_v2_tables import (
    HONESTY_PARAGRAPH,
    table_t0_identity,
    table_t1_honesty,
    table_t2_leg,
    table_t3_license,
)
from lumina_core.birth.awakening_mark_eyes_v2_train import run_mark_eyes_v2_train
from lumina_core.birth.data_source_honesty import real_data_percentage
from lumina_core.birth.foundation_metrics import POLICY_EDGE_MIN_TRADES
from lumina_core.birth.genesis_cloud_const import REPO_ROOT
from lumina_core.birth.genesis_real_door import audit_real_door
from lumina_core.rl.observation_builder import OBSERVATION_DIM

POINTER = (
    "\n---\n\n"
    "## Pointer — AWAKENING_MARK_EYES_V2\n\n"
    "New 48-dim eyes, one scratch 10k on a NEW tape, license vs frozen a9ffa852 lives under "
    "`reports/awakening_eyes_v2_run`. Floor 150 stays. GENESIS_EYES_OK is false. REAL=no.\n"
)


def _git(sha_ref: str) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", sha_ref], cwd=str(REPO_ROOT), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")


def run_awakening_mark_eyes_v2(*, repo: Path | None = None) -> dict[str, Any]:
    os.environ["LUMINA_FABRIC_SUPERVISOR"] = "0"
    os.environ["VOICE_ENABLED"] = "false"
    origin_before = snapshot_origin_artifacts(repo=repo)
    reports, work, art = prepare_v2_trees(repo=repo)
    os.environ["LUMINA_CONFIG"] = str((work / "config.yaml").resolve())
    proto = inspect_v2_protocol()
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
    try:
        baseline_sha = copy_baseline_zip(art)
        fixture = persist_v2_fixture(work, art)
        if float(fixture.get("real_data_pct") or 0.0) == 100.0:
            raise MarkEyesV2ProtocolError("Gate 1 regression: real_data_pct printed 100")
    except MarkEyesV2ProtocolError as exc:
        missing = True
        reason = str(exc)
    if not missing:
        try:
            base_eval = run_v2_eval(work=work, art=art, zip_path=art / BASELINE_ZIP_NAME, kind="base")
            if bool(base_eval.get("S_MISSING")) or not bool(base_eval.get("both_loaded")):
                missing = True
                reason = str(base_eval.get("reason") or "G2 load failed")
        except MarkEyesV2ProtocolError as exc:
            missing = True
            reason = str(exc)
    if not missing:
        try:
            train_out = run_mark_eyes_v2_train(work=work, art=art, init_zip=None)
            if str(train_out.get("status") or "") != "ok":
                missing = True
                reason = str(train_out.get("error") or "G3 S_MISSING")
        except MarkEyesV2ProtocolError as exc:
            missing = True
            reason = str(exc)
    if not missing:
        try:
            child_eval = run_v2_eval(work=work, art=art, zip_path=art / CHILD_ZIP_NAME, kind="child")
            if bool(child_eval.get("S_MISSING")):
                missing = True
                reason = str(child_eval.get("reason") or "G4 load failed")
        except MarkEyesV2ProtocolError as exc:
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
    leg_a = compute_v2_leg(base_a, child_a, missing=missing) if have_books else empty_leg()
    leg_b = compute_v2_leg(base_b, child_b, missing=missing) if have_books else empty_leg()
    if not have_books:
        leg_a = {**empty_leg(), "S_MISSING": True}
        leg_b = {**empty_leg(), "S_MISSING": True}
    licensed = license_v2(leg_a, leg_b, missing=missing)
    flags = compose_v2_flags(
        {
            "fixture_train_hash": str(fixture.get("hash") or ""),
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
    if missing:
        flags["tag"] = TAG_S_MISSING
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
    t3 = table_t3_license(licensed if not missing else {**licensed, "tag": TAG_S_MISSING})
    _write_json(art / FLAGS_NAME, flags)
    (reports / "AWAKENING_MARK_EYES_V2_AUDIT.md").write_text(
        render_audit(gate0=gate0, proto=proto, t0=t0, t1=t1, t2_a=t2_a, t2_b=t2_b, t3=t3, flags=flags, g6=g6),
        encoding="utf-8",
    )
    (reports / "AWAKENING_MARK_EYES_V2_VERDICT.md").write_text(
        render_verdict(flags=flags, t2_a=t2_a, t2_b=t2_b), encoding="utf-8"
    )
    _append_logs(flags)
    assert_origin_untouched(origin_before, repo=repo)
    flags["g0"] = gate0
    return flags


def _append_logs(flags: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).isoformat()
    block = [
        f"## {now} — AWAKENING_MARK_EYES_V2",
        "",
        f"- tag=`{flags.get('tag')}` law=`{flags.get('law')}` "
        f"licensed_next_family=`{flags.get('licensed_next_family')}`",
        f"- hash=`{flags.get('fixture_train_hash')}` seed=`{FIXTURE_SEED}` "
        f"baseline=`{str(flags.get('baseline_sha256') or '')[:16]}` "
        f"child=`{str(flags.get('child_sha256') or '')[:16]}`",
        f"- init_policy=scratch learn_called=`{flags.get('learn_called')}` "
        f"actual_timesteps=`{flags.get('actual_timesteps')}` "
        f"floor=150 GENESIS_EYES_OK=false polished_a9ffa852=false REAL=no G6=`{flags.get('G6_tag')}`",
        "",
        HONESTY_PARAGRAPH,
        "",
    ]
    log_path = V2_ROOT / "LUMINA_BIRTH_EXPERIMENT_LOG.md"
    existing = (
        log_path.read_text(encoding="utf-8")
        if log_path.is_file()
        else "# LUMINA Awakening MARK_EYES V2 experiment log\n\n"
    )
    log_path.write_text(existing.rstrip() + "\n\n" + "\n".join(block), encoding="utf-8")
    birth_log = REPO_ROOT / "reports" / "birth_cloud_run" / "LUMINA_BIRTH_EXPERIMENT_LOG.md"
    if birth_log.is_file():
        text = birth_log.read_text(encoding="utf-8")
        if "Pointer — AWAKENING_MARK_EYES_V2" not in text:
            birth_log.write_text(text.rstrip() + POINTER, encoding="utf-8")


def main() -> int:
    flags = run_awakening_mark_eyes_v2()
    print(json.dumps(flags, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
