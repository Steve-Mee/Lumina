"""Perfect Birth campaign report (M5 extract from perfect_birth_gate)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.perfect_birth_gather import gather_perfect_birth_kpis
from lumina_core.birth.perfect_birth_types import (
    PerfectBirthKpis,
    PerfectBirthThresholds,
    evaluate_perfect_birth_conjunction,
)


def build_perfect_birth_campaign_report(
    workspace_root: Path | str | None = None,
    *,
    thresholds: PerfectBirthThresholds | None = None,
    kpis: PerfectBirthKpis | None = None,
) -> dict[str, Any]:
    """T5: Ops campaign report — checklist + gaps + ordered actions (never declares).

    Use for operator campaigns and CI soft status. Declare remains a separate
    explicit step via ``declare_perfect_birth`` / CLI (conjunction only).
    """
    root = Path(workspace_root) if workspace_root else Path.cwd()
    thr = thresholds or PerfectBirthThresholds()
    try:
        if thresholds is None:
            from lumina_core.birth.config import load_birth_v2_config

            thr = PerfectBirthThresholds.from_curriculum_cfg(
                load_birth_v2_config(root).curriculum
            )
    except Exception:
        pass

    from lumina_core.birth.perfect_birth_gate import perfect_birth_status

    status = perfect_birth_status(root, thresholds=thr)
    measured = kpis or gather_perfect_birth_kpis(root)
    conj = evaluate_perfect_birth_conjunction(measured, thresholds=thr)
    thr_d = conj.thresholds if conj.thresholds else thr.__dict__  # type: ignore[attr-defined]
    m = conj.metrics if conj.metrics else measured.to_dict()

    def _item(
        item_id: str,
        title: str,
        *,
        ok: bool,
        actual: Any,
        target: Any,
        action: str,
        source: str = "",
    ) -> dict[str, Any]:
        return {
            "id": item_id,
            "title": title,
            "ok": bool(ok),
            "actual": actual,
            "target": target,
            "action": action,
            "source": source,
        }

    sources = dict(measured.source_notes or {})
    checklist = [
        _item(
            "certificate",
            "Birth certificate valid",
            ok=bool(measured.certificate_valid),
            actual=bool(measured.certificate_valid),
            target=True,
            action="Complete Birth curriculum + certificate issuance",
            source=str(sources.get("certificate", "")),
        ),
        _item(
            "constitution",
            "Constitution violations = 0",
            ok=int(measured.constitution_violations) <= int(
                thr_d.get("max_constitution_violations", 0) or 0
            ),
            actual=int(measured.constitution_violations),
            target=int(thr_d.get("max_constitution_violations", 0) or 0),
            action="Clear constitution blocks; re-run birth without hard_const",
            source=str(sources.get("progress", "")),
        ),
        _item(
            "twin_labels",
            "Twin Steve labels (N)",
            ok=int(measured.twin_samples) >= int(thr_d.get("min_samples_labels", 30) or 30),
            actual=int(measured.twin_samples),
            target=int(thr_d.get("min_samples_labels", 30) or 30),
            action="python -m lumina_launcher twin review  (label A/V until N met)",
            source=str(sources.get("twin_training", "")),
        ),
        _item(
            "twin_agreement",
            "Twin↔Steve agreement %",
            ok=(
                int(measured.twin_samples) >= int(thr_d.get("min_samples_labels", 30) or 30)
                and float(measured.twin_steve_agreement_pct)
                >= float(thr_d.get("min_twin_steve_agreement_pct", 80.0) or 80.0)
            ),
            actual=float(measured.twin_steve_agreement_pct),
            target=float(thr_d.get("min_twin_steve_agreement_pct", 80.0) or 80.0),
            action="Train twin from labels; raise agreement before declare",
            source=str(sources.get("twin_training", "")),
        ),
        _item(
            "recovery_attempts",
            "Autonomous recovery attempts",
            ok=int(measured.autonomous_recovery_attempts)
            >= int(thr_d.get("min_recovery_attempts", 8) or 8),
            actual=int(measured.autonomous_recovery_attempts),
            target=int(thr_d.get("min_recovery_attempts", 8) or 8),
            action="Run multi-day Birth with never-stop recovery paths enabled",
            source=str(sources.get("progress", "")),
        ),
        _item(
            "recovery_rate",
            "Autonomous recovery rate %",
            ok=(
                int(measured.autonomous_recovery_attempts)
                >= int(thr_d.get("min_recovery_attempts", 8) or 8)
                and float(measured.autonomous_recovery_rate_pct)
                >= float(thr_d.get("min_autonomous_recovery_rate_pct", 85.0) or 85.0)
            ),
            actual=float(measured.autonomous_recovery_rate_pct),
            target=float(thr_d.get("min_autonomous_recovery_rate_pct", 85.0) or 85.0),
            action="Improve recovery success; avoid TERMINAL_NOTIFY_ONLY thrash",
            source=str(sources.get("progress", "")),
        ),
        _item(
            "auto_approve_n",
            "Auto-approve decisions (24h window)",
            ok=int(measured.auto_approved_decisions) >= 20,
            actual=int(measured.auto_approved_decisions),
            target=20,
            action="Accumulate twin decisions in monitoring window (≥20)",
            source=str(sources.get("autonomy", "")),
        ),
        _item(
            "auto_approve_pct",
            "Auto-approve %",
            ok=(
                int(measured.auto_approved_decisions) >= 20
                and float(measured.auto_approved_pct)
                >= float(thr_d.get("min_auto_approved_pct", 60.0) or 60.0)
            ),
            actual=float(measured.auto_approved_pct),
            target=float(thr_d.get("min_auto_approved_pct", 60.0) or 60.0),
            action="Raise twin high-conf auto path under Constitution",
            source=str(sources.get("autonomy", "")),
        ),
        _item(
            "shadow_samples",
            "Shadow alignment samples",
            ok=int(measured.shadow_samples) >= 5,
            actual=int(measured.shadow_samples),
            target=5,
            action="Run shadow twin alignment telemetry (monitoring JSONL)",
            source=str(sources.get("shadow", "")),
        ),
        _item(
            "shadow_alignment",
            "Shadow↔twin alignment %",
            ok=(
                int(measured.shadow_samples) >= 5
                and float(measured.shadow_twin_alignment_pct)
                >= float(thr_d.get("min_shadow_twin_alignment_pct", 75.0) or 75.0)
            ),
            actual=float(measured.shadow_twin_alignment_pct),
            target=float(thr_d.get("min_shadow_twin_alignment_pct", 75.0) or 75.0),
            action="Improve shadow alignment before declare",
            source=str(sources.get("shadow", "")),
        ),
        _item(
            "attention_clean",
            "No TERMINAL_NOTIFY / needs_attention signal",
            ok=int(measured.terminal_notify_recent)
            <= int(thr_d.get("max_terminal_notify_recent", 0) or 0),
            actual=int(measured.terminal_notify_recent),
            target=int(thr_d.get("max_terminal_notify_recent", 0) or 0),
            action="Clear needs_attention (accept champion / wipe / resolve stalls); 48h clean",
            source=str(sources.get("progress", "")),
        ),
        _item(
            "evidence_unlock",
            "Flag + evidence unlock (passed=true)",
            ok=bool(status.get("unlock_valid")),
            actual={
                "flag": status.get("flag_exists"),
                "evidence_passed": status.get("evidence_passed"),
                "detail": status.get("unlock_detail"),
            },
            target="flag+evidence.passed",
            action=(
                "python scripts/validation/declare_perfect_birth.py"
                if conj.passed
                else "Close KPI gaps first — do not --force"
            ),
            source=str(status.get("flag_path") or ""),
        ),
    ]

    open_items = [c for c in checklist if not c["ok"]]
    actions: list[str] = []
    for c in open_items:
        act = str(c.get("action") or "").strip()
        if act and act not in actions:
            actions.append(act)
    if conj.passed and not status.get("unlock_valid"):
        actions.insert(
            0,
            "python scripts/validation/declare_perfect_birth.py  # conjunction green — declare evidence",
        )
    if status.get("unlock_valid"):
        actions = [
            "Phase 2: enable SIM shadow campaign after evidence unlock "
            "(scripts/validation or birth API phase2-enable-shadow); REAL apply forbidden"
        ]

    passed_n = sum(1 for c in checklist if c["ok"])
    return {
        "schema": "perfect_birth_campaign_v1",
        "ok": bool(status.get("unlock_valid")),
        "campaign_ready_to_declare": bool(conj.passed) and not bool(status.get("unlock_valid")),
        "would_pass": bool(conj.passed),
        "unlock_valid": bool(status.get("unlock_valid")),
        "checklist_passed": passed_n,
        "checklist_total": len(checklist),
        "checklist": checklist,
        "open_items": [c["id"] for c in open_items],
        "ordered_actions": actions,
        "failures": list(conj.failures),
        "missing_sources": list(status.get("missing_sources") or []),
        "metrics": m,
        "thresholds": thr_d if isinstance(thr_d, dict) else {},
        "auto_declare_enabled": bool(status.get("auto_declare_enabled")),
        "capital_mode_safe": True,
        "policy": {
            "hollow_flag_forbidden": True,
            "force_declare_does_not_unlock": True,
            "never_opens_real_capital": True,
            "phase2_requires_evidence": True,
        },
        "commands": {
            "status": "python scripts/validation/perfect_birth_campaign.py",
            "declare": "python scripts/validation/declare_perfect_birth.py",
            "declare_dry_run": "python scripts/validation/declare_perfect_birth.py --dry-run",
        },
        "next_step": status.get("next_step"),
        "status": status,
    }

