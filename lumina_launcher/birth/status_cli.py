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
