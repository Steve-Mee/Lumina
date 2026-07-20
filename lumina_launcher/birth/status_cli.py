"""Birth Phase status reporting for headless operators and scripts."""

from __future__ import annotations

import json
import sys
import time
from typing import Any

from lumina_launcher.services.birth_service import birth_service
from lumina_launcher.telemetry.hooks import emit_launcher_event


def _compact_summary(status: dict[str, Any]) -> dict[str, Any]:
    progress = status.get("progress") if isinstance(status.get("progress"), dict) else {}
    return {
        "status": status.get("status"),
        "stage": progress.get("stage") or status.get("stage"),
        "phase": progress.get("phase") or status.get("phase"),
        "message": progress.get("message") or status.get("message"),
        "progress_pct": progress.get("progress_pct"),
        "trades_done": progress.get("trades_done"),
        "target_trades": progress.get("target_trades"),
        "stage_index": progress.get("stage_index"),
        "pass_reason": progress.get("pass_reason"),
        "auto_recovery_active": progress.get("auto_recovery_active"),
        "certificate_state": progress.get("certificate_state") or progress.get("certificate_status"),
        "runner": status.get("runner"),
    }


def run_phase2_status(*, as_json: bool = False, window_hours: int = 24) -> int:
    """Slice B: answer 'did Phase 2 help?' from one command."""
    from lumina_core.birth.config import load_birth_v2_config
    from lumina_core.birth.phase2_autonomy.features import Phase2AutonomyFeatures
    from lumina_core.birth.phase2_autonomy.metrics import phase2_status_payload

    features = Phase2AutonomyFeatures()
    try:
        v2 = load_birth_v2_config()
        features = Phase2AutonomyFeatures.from_curriculum_cfg(v2.curriculum)
    except Exception:
        pass

    payload = phase2_status_payload(
        window_hours=max(1, int(window_hours)),
        recent_limit=5,
        features=features,
    )
    emit_launcher_event(
        "launcher.birth.phase2_status",
        proposals=int((payload.get("metrics") or {}).get("phase2_proposals_total", 0) or 0),
        apply_rate=(payload.get("metrics") or {}).get("phase2_apply_rate_pct"),
    )
    if as_json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
        return 0

    m = payload.get("metrics") or {}
    f = payload.get("features") or {}
    print(
        f"phase2 enabled={f.get('enabled', False)} "
        f"wall={f.get('dynamic_wall_enabled', False)} "
        f"params={f.get('self_adaptive_params_enabled', False)} "
        f"instance={f.get('instance_adapt_enabled', False)}"
    )
    print(
        f"window={m.get('window_hours')}h "
        f"proposals={m.get('phase2_proposals_total', 0)} "
        f"applied={m.get('phase2_applied_total', 0)} "
        f"apply_rate_pct={m.get('phase2_apply_rate_pct', 0.0)} "
        f"allowed_rate_pct={m.get('phase2_allowed_rate_pct', 0.0)}"
    )
    rejects = m.get("phase2_gate_reject_by_reason") or {}
    if rejects:
        top = ", ".join(f"{k}={v}" for k, v in list(rejects.items())[:5])
        print(f"rejects: {top}")
    last = m.get("last_decision")
    if isinstance(last, dict):
        print(
            f"last: pillar={last.get('pillar')} allowed={last.get('allowed')} "
            f"applied={last.get('applied')} reason={last.get('reason')} "
            f"stage={last.get('stage')}"
        )
    else:
        print("last: (none — master off or no decisions yet)")
    path = m.get("monitoring_path")
    if path:
        print(f"log: {path}")
    return 0


def run_birth_status(*, as_json: bool = False) -> int:
    payload = birth_service.get_status()
    emit_launcher_event("launcher.birth.status", status=str(payload.get("status", "")))
    summary = _compact_summary(payload)
    if as_json:
        print(json.dumps(summary, ensure_ascii=True, indent=2))
    else:
        parts = [
            f"status={summary.get('status')}",
            f"stage={summary.get('stage')}",
            f"phase={summary.get('phase')}",
        ]
        if summary.get("progress_pct") is not None:
            parts.append(f"progress_pct={summary.get('progress_pct')}")
        if summary.get("message"):
            parts.append(f"message={summary.get('message')}")
        print(" ".join(str(p) for p in parts if p))
    return 0


def run_birth_watch(*, interval_sec: int = 5) -> int:
    last_key = ""
    print(f"Watching birth status (interval={interval_sec}s). Ctrl+C to stop.", file=sys.stderr)
    try:
        while True:
            payload = birth_service.get_status()
            summary = _compact_summary(payload)
            key = f"{summary.get('status')}|{summary.get('stage')}|{summary.get('phase')}"
            if key != last_key:
                last_key = key
                emit_launcher_event(
                    "launcher.birth.stage_changed",
                    status=summary.get("status"),
                    stage=summary.get("stage"),
                    phase=summary.get("phase"),
                )
                print(json.dumps(summary, ensure_ascii=True))
            time.sleep(max(1, interval_sec))
    except KeyboardInterrupt:
        print("\nBirth watch stopped.", file=sys.stderr)
        return 0
