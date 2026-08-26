#!/usr/bin/env python3
"""R2: Birth zero-human validation cadence (every 15–60 min).

Runs the honest residual + Perfect Birth + theater + Phase 2 status board.
Never declares Perfect Birth, never arms REAL, never auto-wipes.

Usage:
  python scripts/validation/birth_zero_human_cadence.py
  python scripts/validation/birth_zero_human_cadence.py --workspace .
  python scripts/validation/birth_zero_human_cadence.py --json
  python scripts/validation/birth_zero_human_cadence.py --fabric-mock
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_report(workspace: Path, *, fabric_mock: bool) -> dict[str, Any]:
    from lumina_core.ops.operator_residuals import build_operator_residuals_report
    from lumina_core.birth.perfect_birth_gate import build_perfect_birth_campaign_report
    from lumina_core.birth.recovery_compress import build_recovery_theater_ops_report
    from lumina_core.birth.phase2_autonomy.sim_campaign import (
        build_phase2_shadow_campaign_ops_report,
    )
    from lumina_core.birth.training_window_sla import training_window_sla_report

    progress: dict[str, Any] = {}
    for name in ("lumina_birth_progress.json", "first_boot_progress.json"):
        path = workspace / "state" / name
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    progress = raw
                    break
            except Exception:
                pass

    residuals = build_operator_residuals_report(
        workspace=workspace,
        run_fabric_mock=fabric_mock,
    )
    pb = build_perfect_birth_campaign_report(workspace)
    theater = build_recovery_theater_ops_report(progress)
    phase2 = build_phase2_shadow_campaign_ops_report(workspace)

    days_loaded = int(
        progress.get("actual_calendar_days")
        or progress.get("data_days_loaded")
        or (progress.get("data_manifest") or {}).get("actual_calendar_days")
        or (progress.get("data_manifest") or {}).get("days_loaded")
        or 0
    )
    requested = int(
        progress.get("requested_days")
        or (progress.get("data_manifest") or {}).get("requested_days")
        or 0
    )
    sla = training_window_sla_report(
        days_loaded=days_loaded,
        requested_days=requested,
        degraded_data_mode=bool(
            (progress.get("data_manifest") or {}).get("degraded_data_mode")
        ),
    )

    needs_attention = bool(progress.get("needs_attention"))
    terminal_reason = str(progress.get("terminal_stall_reason") or "").strip()
    silent_stall = bool(terminal_reason) and not needs_attention

    kill_criteria = {
        "silent_terminal_stall_hours": 0 if not silent_stall else 1,
        "supervisor_monitoring_fatal": "check structured_errors for SUPERVISOR_LOOP_CRASH",
        "training_window_sla_ok": bool(sla.get("ok")),
        "hollow_perfect_birth": bool(pb.get("unlock_valid")) and not bool(pb.get("would_pass")),
        "yaml_twin_full_auto_force": False,  # enforced by twin SSOT audit in residuals
        "real_auto_arm": False,
    }

    ordered: list[str] = []
    for item in residuals.get("items") or []:
        if not isinstance(item, dict):
            continue
        if item.get("status") in {"yellow", "red", "blocked"}:
            for a in item.get("next_actions") or []:
                if a and a not in ordered:
                    ordered.append(str(a))
    for a in pb.get("ordered_actions") or []:
        if a and a not in ordered:
            ordered.append(str(a))
    for a in phase2.get("ordered_actions") or []:
        if a and a not in ordered:
            ordered.append(str(a))
    if silent_stall:
        ordered.insert(
            0,
            "C2: terminal_stall without needs_attention — investigate progress SSOT",
        )
    if not sla.get("ok") and requested > 0:
        ordered.insert(0, "C3: expand data or wipe — training window SLA shortfall")

    counts = residuals.get("counts") or {}
    ok = bool(residuals.get("ok")) and not silent_stall

    return {
        "schema": "birth_zero_human_cadence_v1",
        "ok": ok,
        "workspace": str(workspace),
        "residuals": {
            "ok": residuals.get("ok"),
            "counts": counts,
            "sp3_sp4_ready": (residuals.get("sp3_sp4_readiness") or {}).get("ready"),
            "sp3_blockers": (residuals.get("sp3_sp4_readiness") or {}).get("blockers"),
        },
        "perfect_birth": {
            "unlock_valid": pb.get("unlock_valid"),
            "campaign_ready_to_declare": pb.get("campaign_ready_to_declare"),
            "checklist_passed": pb.get("checklist_passed"),
            "checklist_total": pb.get("checklist_total"),
        },
        "recovery_theater": {
            "ok": theater.get("ok"),
            "active": theater.get("active"),
            "theater": theater.get("theater"),
            "next_action": theater.get("next_action"),
            "productive": theater.get("productive"),
        },
        "phase2": {
            "ok": phase2.get("ok"),
            "observe_ready": phase2.get("observe_ready"),
            "mode": phase2.get("mode"),
            "perfect_birth_unlock": phase2.get("perfect_birth_unlock"),
            "can_enable_observe": phase2.get("can_enable_observe"),
            "can_enable_shadow": phase2.get("can_enable_shadow"),
            "can_promote_sim_apply": phase2.get("can_promote_sim_apply"),
        },
        "training_window_sla": sla,
        "progress_attention": {
            "needs_attention": needs_attention,
            "attention_reason_code": progress.get("attention_reason_code"),
            "terminal_stall_reason": terminal_reason or None,
            "silent_stall": silent_stall,
            "phase": progress.get("phase"),
            "curriculum_stage": progress.get("curriculum_stage") or progress.get("stage"),
        },
        "kill_criteria": kill_criteria,
        "ordered_actions": ordered[:12],
        "commands": {
            "residuals": "python scripts/validation/operator_residuals_gate.py --workspace .",
            "pb": "python scripts/validation/perfect_birth_campaign.py --workspace .",
            "theater": "python scripts/validation/recovery_theater_gate.py --workspace . --no-pytest",
            "phase2_observe": "python scripts/validation/phase2_shadow_campaign.py --observe",
            "phase2_shadow": "python scripts/validation/phase2_shadow_campaign.py --enable",
            "twin": "python scripts/validation/twin_mode_ssot_audit.py",
            "runbook": "docs/birth-zero-human-metrics-runbook.md",
        },
        "policy": {
            "never_auto_declare_perfect_birth": True,
            "never_auto_real": True,
            "never_auto_wipe": True,
            "never_yaml_twin_full_auto_force": True,
            "cadence_minutes": "15-60",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Birth zero-human validation cadence (R2)")
    parser.add_argument("--workspace", type=str, default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--fabric-mock", action="store_true")
    args = parser.parse_args(argv)

    workspace = Path(args.workspace).resolve() if args.workspace else ROOT
    report = _run_report(workspace, fabric_mock=bool(args.fabric_mock))

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=True, default=str))
    else:
        print(
            f"birth_zero_human_cadence ok={report['ok']} "
            f"residuals={report['residuals'].get('counts')} "
            f"pb={report['perfect_birth'].get('checklist_passed')}/"
            f"{report['perfect_birth'].get('checklist_total')} "
            f"phase2_mode={report['phase2'].get('mode')} "
            f"sla_ok={report['training_window_sla'].get('ok')}"
        )
        att = report.get("progress_attention") or {}
        if att.get("silent_stall"):
            print(f"  [!] SILENT STALL: {att.get('terminal_stall_reason')}")
        if att.get("needs_attention"):
            print(
                f"  [!] needs_attention reason={att.get('attention_reason_code')} "
                f"terminal={att.get('terminal_stall_reason')}"
            )
        theater = report.get("recovery_theater") or {}
        print(
            f"  theater active={theater.get('active')} next={theater.get('next_action')} "
            f"productive={theater.get('productive')}"
        )
        pb = report.get("perfect_birth") or {}
        print(
            f"  perfect_birth unlock={pb.get('unlock_valid')} "
            f"ready_to_declare={pb.get('campaign_ready_to_declare')}"
        )
        p2 = report.get("phase2") or {}
        print(
            f"  phase2 observe_ready={p2.get('observe_ready')} "
            f"can_shadow={p2.get('can_enable_shadow')} "
            f"can_apply={p2.get('can_promote_sim_apply')}"
        )
        actions = report.get("ordered_actions") or []
        if actions:
            print("  next_actions:")
            for i, a in enumerate(actions[:8], 1):
                print(f"    {i}. {a}")
        print("  policy: no auto-PB, no auto-REAL, no auto-wipe")

    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
