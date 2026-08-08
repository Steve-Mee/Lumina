"""OR1–OR6 operator residual board (post deep-audit T1–T15 / self-play Phase 0).

Automated code gates already exist. Residuals are **evidence / human forks**:
this module aggregates status + checklists so nothing is silent or forgotten.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


def _load_progress(workspace: Path) -> dict[str, Any]:
    for name in ("lumina_birth_progress.json", "first_boot_progress.json"):
        path = workspace / "state" / name
        if path.is_file():
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                return raw if isinstance(raw, dict) else {}
            except Exception:
                return {}
    return {}


def _item(
    *,
    id: str,
    title: str,
    status: str,
    automated_ok: bool,
    human_required: bool,
    blocks_sp3: bool,
    summary: str,
    next_actions: list[str],
    command: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": id,
        "title": title,
        "status": status,  # green | yellow | red | blocked
        "automated_ok": automated_ok,
        "human_required": human_required,
        "blocks_sp3": blocks_sp3,
        "summary": summary,
        "next_actions": next_actions,
        "command": command,
        "evidence": evidence or {},
    }


def _or1_fabric(*, run_mock: bool) -> dict[str, Any]:
    """OR1: Fabric SAFE_MODE — mock automated; live NT8 still operator."""
    mock_ok = True
    mock_detail: dict[str, Any] = {"skipped": not run_mock}
    if run_mock:
        try:
            import subprocess
            import sys

            root = Path(__file__).resolve().parents[2]
            proc = subprocess.run(
                [
                    sys.executable,
                    "scripts/validation/fabric_safe_mode_gate.py",
                    "--mock",
                ],
                cwd=str(root),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )
            mock_ok = proc.returncode == 0
            mock_detail = {
                "ok": mock_ok,
                "returncode": proc.returncode,
                "stdout_tail": (proc.stdout or "")[-400:],
            }
        except Exception as exc:
            mock_ok = False
            mock_detail = {"ok": False, "error": str(exc)}

    return _item(
        id="OR1",
        title="Fabric live SAFE_MODE / heartbeat ≥5s cancel (NT8)",
        status="yellow" if mock_ok else "red",
        automated_ok=mock_ok,
        human_required=True,
        blocks_sp3=False,  # SP3 is SIM self-play apply; Fabric is capital path residual
        summary=(
            "Brain mock SAFE_MODE pack available; live host heartbeat-timeout cancel "
            "remains operator-manual on NT8 (never REAL)."
            if mock_ok
            else "Fabric mock gate failed — fix Brain SAFE_MODE tests first."
        ),
        next_actions=[
            "python scripts/validation/fabric_safe_mode_gate.py --mock",
            "With NT8+AddOn SIM only: python scripts/validation/fabric_safe_mode_gate.py --live",
            "Operator: stop heartbeats ≥5s → confirm cancel + SAFE_MODE (docs/execution-fabric-phase0.md)",
        ],
        command="python scripts/validation/fabric_safe_mode_gate.py --mock",
        evidence={"mock": mock_detail, "live_required": True},
    )


def _or2_aperture(workspace: Path) -> dict[str, Any]:
    from lumina_core.risk.capital_aperture_lineage import evaluate_aperture_coverage_gate

    result = evaluate_aperture_coverage_gate(
        workspace_root=workspace,
        audit_limit=200,
        min_coverage_pct=95.0,
        min_sample_size=10,
        phase2_band=False,
    )
    soft = bool(result.get("soft_pass"))
    sample = int(result.get("sample_size") or 0)
    cov = result.get("lineage_coverage_pct")
    hard_fail = not bool(result.get("ok")) and not soft
    if hard_fail:
        status = "red"
        summary = f"Coverage below 95% with samples={sample} (actual={cov})."
    elif soft:
        status = "yellow"
        summary = (
            f"Soft pass: insufficient production samples (sample_size={sample}). "
            "H1 ≥95% not yet measurable."
        )
    else:
        status = "green"
        summary = f"Coverage ok: {cov}% over {sample} samples."

    return _item(
        id="OR2",
        title="Capital aperture live coverage ≥95%",
        status=status,
        automated_ok=not hard_fail,
        human_required=soft or hard_fail,
        blocks_sp3=False,
        summary=summary,
        next_actions=[
            "python scripts/validation/aperture_coverage_gate.py --workspace . --json",
            "Run SIM/REAL-path orders through single capital aperture to accumulate samples",
            "Re-run until sample_size≥10 and lineage_coverage_pct≥95",
        ],
        command="python scripts/validation/aperture_coverage_gate.py",
        evidence={
            "sample_size": sample,
            "lineage_coverage_pct": cov,
            "soft_pass": soft,
            "ok": result.get("ok"),
        },
    )


def _or3_perfect_birth(workspace: Path) -> dict[str, Any]:
    from lumina_core.birth.perfect_birth_gate import build_perfect_birth_campaign_report

    report = build_perfect_birth_campaign_report(workspace)
    unlock = bool(report.get("unlock_valid"))
    would = bool(report.get("would_pass") or report.get("campaign_ready_to_declare"))
    checklist = report.get("checklist") if isinstance(report.get("checklist"), list) else []
    passed = int(
        report.get("checklist_passed")
        if report.get("checklist_passed") is not None
        else sum(1 for c in checklist if isinstance(c, dict) and c.get("ok"))
    )
    total = int(
        report.get("checklist_total")
        if report.get("checklist_total") is not None
        else len(checklist)
    )
    if unlock:
        status = "green"
        summary = "Perfect Birth unlock valid (evidence + flag path honest)."
    elif would or passed > 0:
        status = "yellow"
        summary = f"Campaign progress {passed}/{total}; not unlocked — declare forbidden."
    else:
        status = "yellow"
        summary = f"Campaign incomplete {passed}/{total}; fail-closed (no hollow declare)."

    actions = list(report.get("ordered_actions") or [])[:5]
    actions.append("python scripts/validation/perfect_birth_campaign.py --workspace .")
    actions.append(
        "Only when unlock green: python scripts/validation/declare_perfect_birth.py --dry-run"
    )

    return _item(
        id="OR3",
        title="Perfect Birth campaign evidence + intentional declare",
        status=status,
        automated_ok=True,  # tooling ok; evidence may be incomplete
        human_required=not unlock,
        # SP3 prefers unlock; SP4 (birth-loop) should wait for unlock
        blocks_sp3=not unlock,
        summary=summary,
        next_actions=actions,
        command="python scripts/validation/perfect_birth_campaign.py",
        evidence={
            "unlock_valid": unlock,
            "would_pass": would,
            "checklist_passed": passed,
            "checklist_total": total,
            "next_step": report.get("next_step"),
        },
    )


def _or4_twin(workspace: Path) -> dict[str, Any]:
    from lumina_core.evolution.twin_discipline import build_twin_promote_ops_report
    from lumina_core.evolution.twin_mode_ssot_audit import build_twin_mode_ssot_audit

    ssot = build_twin_mode_ssot_audit(workspace=workspace)
    promote = build_twin_promote_ops_report(mode_status=None, controller=None, capital_mode="sim")
    try:
        from lumina_core.evolution.twin_mode_controller import TwinModeController

        ctrl = TwinModeController(initial_mode="shadow")
        promote = build_twin_promote_ops_report(
            mode_status=ctrl.status(),
            controller=ctrl,
            capital_mode="sim",
        )
    except Exception as exc:
        promote = {
            "live_mode": "shadow",
            "error": str(exc),
            "ladder": [],
            "readiness": {},
        }

    ssot_ok = bool(ssot.get("ok"))
    mode = str(ssot.get("ssot_mode") or promote.get("live_mode") or "shadow")
    rd = promote.get("readiness") if isinstance(promote.get("readiness"), dict) else {}
    assisted = rd.get("assisted") if isinstance(rd.get("assisted"), dict) else {}
    full_auto = rd.get("full_auto") if isinstance(rd.get("full_auto"), dict) else {}
    assisted_ready = bool(assisted.get("promoted") or assisted.get("ready"))
    fa_ready = bool(full_auto.get("promoted") or full_auto.get("ready"))

    if not ssot_ok:
        status = "red"
        summary = f"Twin SSOT audit failed (mode={mode})."
    elif mode == "full_auto" and fa_ready:
        status = "green"
        summary = "Twin SSOT healthy; full_auto via gate evidence."
    elif mode in {"assisted", "full_auto"} or assisted_ready:
        status = "yellow"
        summary = f"Twin SSOT ok mode={mode}; promote ladder still needs labels/evidence for full_auto."
    else:
        status = "yellow"
        summary = f"Twin SSOT ok mode={mode}; still on shadow — label → assisted path open."

    return _item(
        id="OR4",
        title="Twin promote ladder + mode SSOT audit",
        status=status,
        automated_ok=ssot_ok,
        human_required=mode != "full_auto",
        # SSOT must be healthy; full_auto not required for SIM shadow apply
        blocks_sp3=not ssot_ok,
        summary=summary,
        next_actions=[
            "python scripts/validation/twin_mode_ssot_audit.py",
            "python scripts/validation/twin_promote_ops.py --isolated",
            "Label high-stakes queue; promote assisted only when gate ready",
            "Never set evolution.approval_twin.mode: full_auto in yaml",
        ],
        command="python scripts/validation/twin_mode_ssot_audit.py",
        evidence={
            "ssot_mode": mode,
            "ssot_ok": ssot_ok,
            "ssot_source": ssot.get("ssot_source"),
            "assisted_ready": assisted_ready,
            "full_auto_ready": fa_ready,
            "has_warnings": ssot.get("has_warnings"),
        },
    )


def _or5_champion_freeze(workspace: Path, progress: dict[str, Any]) -> dict[str, Any]:
    from lumina_core.birth.starship_swarm_gates import build_champion_freeze_verification_report

    report = build_champion_freeze_verification_report(progress=progress)
    freeze = bool(report.get("freeze_active") or report.get("rejected_no_lift"))
    accepted = bool(report.get("champion_accepted"))
    auto_ok = bool(report.get("ok", True))

    if freeze and not accepted:
        status = "blocked"
        summary = (
            "Champion freeze ACTIVE — no train / no SP apply. "
            "Operator must accept_champion or wipe_and_retry."
        )
        human = True
    elif accepted:
        status = "green"
        summary = "Champion accepted after freeze — freeze resolved."
        human = False
    else:
        status = "green"
        summary = "No active champion freeze on progress."
        human = False

    return _item(
        id="OR5",
        title="Live champion freeze → accept or wipe only",
        status=status,
        automated_ok=auto_ok,
        human_required=human,
        blocks_sp3=freeze and not accepted,
        summary=summary,
        next_actions=(
            [
                "python scripts/validation/champion_freeze_ops.py --workspace . status",
                "Telegram: reply ACCEPT | ACCEPT_NO_START | WIPE | WIPE_FULL",
                "Accept: python scripts/validation/champion_freeze_ops.py --workspace . accept --confirm --no-start",
                "Wipe: python scripts/validation/champion_freeze_ops.py --workspace . wipe --confirm --keep-tick-cache",
                "Or Tauri Birth: Accept champion OR Wipe & restart (echoed to Telegram)",
                "Do not auto-resume training under freeze",
                "Checklist: docs/birth-stage2-certified-reentry-checklist.md",
                "python scripts/validation/champion_freeze_gate.py --workspace . --no-pytest",
            ]
            if freeze and not accepted
            else [
                "python scripts/validation/champion_freeze_ops.py --workspace . status",
                "python scripts/validation/champion_freeze_gate.py --no-pytest",
                "Unit pack: python scripts/validation/champion_freeze_gate.py",
            ]
        ),
        command="python scripts/validation/champion_freeze_ops.py --workspace . status",
        evidence={
            "freeze_active": freeze,
            "champion_accepted": accepted,
            "message": report.get("message"),
            "report_ok": report.get("ok"),
        },
    )


def _or6_recovery_theater(workspace: Path, progress: dict[str, Any]) -> dict[str, Any]:
    from lumina_core.birth.recovery_compress import build_recovery_theater_ops_report

    report = build_recovery_theater_ops_report(progress)
    theater = bool(report.get("theater"))
    next_action = str(report.get("next_action") or "none")
    active = str(report.get("active") or "none")
    report_ok = bool(report.get("ok", True))

    if theater and next_action in {
        "accept_champion_or_wipe",
        "accept_champion",
        "wipe_and_retry",
    }:
        status = "blocked"
        summary = (
            f"Recovery theater active (surface={active}); next={next_action} — "
            "stop ladder spin; human fork only."
        )
        human = True
        blocks = True
    elif theater:
        status = "yellow"
        summary = f"Theater signal on surface={active}; next={next_action}."
        human = True
        blocks = False
    else:
        status = "green"
        summary = f"Single active recovery surface ok (active={active})."
        human = False
        blocks = False

    return _item(
        id="OR6",
        title="Recovery theater residual (single surface; no ladder spin)",
        status=status,
        automated_ok=report_ok,
        human_required=human,
        blocks_sp3=blocks,
        summary=summary,
        next_actions=[
            "python scripts/validation/recovery_theater_gate.py --workspace . --no-pytest",
            "If theater + freeze: accept_champion_or_wipe only",
            "Do not run parallel plateau ladder under champion freeze",
        ],
        command="python scripts/validation/recovery_theater_gate.py --no-pytest",
        evidence={
            "active": active,
            "theater": theater,
            "next_action": next_action,
            "residual_layers": report.get("residual_parallel_layers"),
            "flags": report.get("flags"),
        },
    )


def build_operator_residuals_report(
    *,
    workspace: Path | str | None = None,
    run_fabric_mock: bool = False,
) -> dict[str, Any]:
    """Aggregate OR1–OR6 status for operators and SP3 readiness."""
    root = Path(workspace).resolve() if workspace else Path.cwd().resolve()
    progress = _load_progress(root)

    items = [
        _or1_fabric(run_mock=run_fabric_mock),
        _or2_aperture(root),
        _or3_perfect_birth(root),
        _or4_twin(root),
        _or5_champion_freeze(root, progress),
        _or6_recovery_theater(root, progress),
    ]

    blocked = [i for i in items if i["status"] == "blocked"]
    red = [i for i in items if i["status"] == "red"]
    yellow = [i for i in items if i["status"] == "yellow"]
    green = [i for i in items if i["status"] == "green"]
    sp3_blockers = [i["id"] for i in items if i.get("blocks_sp3")]

    # Board is "ops honest" when no red automated failures (blocked/yellow are expected)
    ok = len(red) == 0

    return {
        "schema": "operator_residuals_or1_or6_v1",
        "ok": ok,
        "workspace": str(root),
        "counts": {
            "green": len(green),
            "yellow": len(yellow),
            "red": len(red),
            "blocked": len(blocked),
        },
        "items": items,
        "sp3_sp4_readiness": {
            "ready": len(sp3_blockers) == 0 and len(red) == 0,
            "blockers": sp3_blockers,
            "note": (
                "SP3 (SIM apply under Twin) and SP4 (birth-loop observe) require: "
                "no red residuals; OR3 PB path honest; OR4 twin SSOT/promote path; "
                "OR5/OR6 not blocked on freeze/theater. OR1/OR2 are capital path residual "
                "and should be green before production REAL, but SP3 remains SIM-only."
            ),
        },
        "sp1_sp2_status": {
            "SP1": "implemented — lumina_core/birth/self_play pure package + tests",
            "SP2": "implemented — self_play_lab_gate.py + deep-audit soft wire",
            "SP0": "done — ADR-0037 Accepted (lab scaffold)",
            "SP3": "deferred",
            "SP4": "deferred",
        },
        "commands": {
            "board": "python scripts/validation/operator_residuals_gate.py",
            "board_with_fabric_mock": (
                "python scripts/validation/operator_residuals_gate.py --fabric-mock"
            ),
            "runbook": "docs/operator-residuals-or1-or6.md",
        },
    }


__all__ = ["build_operator_residuals_report"]
