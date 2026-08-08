"""Gather Perfect Birth KPIs from state/monitoring (M5 extract)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.birth.perfect_birth_types import (
    PerfectBirthKpis,
    _read_json,
    _tail_jsonl,
)
from lumina_core.logging_utils import resolve_monitoring_state_dir

def gather_perfect_birth_kpis(
    workspace_root: Path | str | None = None,
) -> PerfectBirthKpis:
    """Best-effort KPI gather from state/monitoring files (fail-soft → zeros)."""
    root = Path(workspace_root) if workspace_root else Path.cwd()
    state = root / "state"
    notes: dict[str, str] = {}

    # Certificate
    cert_path = state / "lumina_birth_certificate.json"
    cert = _read_json(cert_path)
    certificate_valid = False
    constitution_violations = 0
    if cert:
        constitution_violations = int(
            cert.get("constitution_violations", cert.get("violations", 0)) or 0
        )
        # Accept common validity signals
        if cert.get("valid") is True or cert.get("status") in {"issued", "valid", "ok"}:
            certificate_valid = True
        elif cert.get("certificate_id") or cert.get("issued_at") or cert.get("stage"):
            certificate_valid = constitution_violations == 0
        notes["certificate"] = str(cert_path)
    else:
        # Also try BirthService certificate_ok
        try:
            from lumina_launcher.services.birth_service import BirthService

            svc = BirthService()
            svc.configure_workspace(root)
            if svc.certificate_ok():
                certificate_valid = True
                notes["certificate"] = "birth_service.certificate_ok"
            else:
                notes["certificate"] = "missing"
        except Exception:
            notes["certificate"] = "missing"

    # Progress recovery metrics
    progress = _read_json(state / "lumina_birth_progress.json")
    recovery_rate = float(
        progress.get("autonomous_recovery_rate_pct")
        or progress.get("autonomous_recovery_rate")
        or 0.0
    )
    recovery_attempts = int(
        progress.get("autonomous_recovery_attempts")
        or progress.get("recovery_attempts")
        or progress.get("autonomous_recovery_count")
        or 0
    )
    if progress.get("constitution_violations") is not None:
        constitution_violations = max(
            constitution_violations, int(progress.get("constitution_violations") or 0)
        )
    notes["progress"] = "state/lumina_birth_progress.json"

    # Twin agreement: prefer workspace twin summary, then monitoring jsonl
    twin_pct = 0.0
    twin_samples = 0
    twin_summary = state / "twin_mode_metrics_summary.json"
    if twin_summary.is_file():
        ts = _read_json(twin_summary)
        twin_samples = int(ts.get("samples", 0) or 0)
        twin_pct = float(
            ts.get("steve_label_agreement_pct")
            or ts.get("agreement_pct")
            or ts.get("twin_steve_agreement_pct")
            or 0.0
        )
        notes["twin_training"] = str(twin_summary)
    if twin_samples <= 0:
        mon = resolve_monitoring_state_dir()
        twin_rows = _tail_jsonl(mon / "monitoring_twin_training.jsonl", limit=30)
        for row in reversed(twin_rows):
            if "twin_steve_agreement_pct" in row or "samples" in row:
                twin_pct = float(row.get("twin_steve_agreement_pct", twin_pct) or twin_pct)
                twin_samples = int(row.get("samples", twin_samples) or twin_samples)
                break
        notes["twin_training"] = str(mon / "monitoring_twin_training.jsonl")

    # Autonomy auto-approve from compute_autonomy_snapshot
    auto_pct = 0.0
    auto_decisions = 0
    try:
        from lumina_core.logging_utils import compute_autonomy_snapshot

        snap = compute_autonomy_snapshot(window_hours=24)
        auto_pct = float(snap.get("autonomy_level_pct", 0.0) or 0.0)
        auto_decisions = int(snap.get("decisions_total", 0) or 0)
        notes["autonomy"] = "monitoring_twin_decisions.jsonl"
    except Exception:
        notes["autonomy"] = "unavailable"

    # Shadow alignment
    mon = resolve_monitoring_state_dir()
    align_rows = _tail_jsonl(mon / "monitoring_shadow_twin_alignment.jsonl", limit=50)
    shadow_samples = len(align_rows)
    shadow_aligned = sum(1 for r in align_rows if bool(r.get("aligned")))
    shadow_pct = (
        round((shadow_aligned / shadow_samples) * 100.0, 2) if shadow_samples else 0.0
    )
    notes["shadow"] = str(mon / "monitoring_shadow_twin_alignment.jsonl")

    # Terminal notify heuristic from progress / autonomy metrics
    terminal_notify = int(progress.get("terminal_notify_count_recent", 0) or 0)
    if progress.get("needs_attention"):
        terminal_notify = max(terminal_notify, 1)

    return PerfectBirthKpis(
        certificate_valid=certificate_valid,
        constitution_violations=constitution_violations,
        twin_steve_agreement_pct=twin_pct,
        twin_samples=twin_samples,
        autonomous_recovery_rate_pct=recovery_rate,
        autonomous_recovery_attempts=recovery_attempts,
        auto_approved_pct=auto_pct,
        auto_approved_decisions=auto_decisions,
        shadow_twin_alignment_pct=shadow_pct,
        shadow_samples=shadow_samples,
        terminal_notify_recent=terminal_notify,
        source_notes=notes,
    )



__all__ = ["gather_perfect_birth_kpis"]
