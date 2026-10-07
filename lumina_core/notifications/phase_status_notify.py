"""Send post-birth phase status to Telegram. Informational only — never a gate."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.notifications.phase_status_report import (
    STATUS_PHASES,
    fingerprint_phase_status,
    format_phase_status,
)

logger = get_logger("lumina.notifications.phase_status")

_LOCK = threading.RLock()
_STATE_NAME = "phase_status_telegram.json"
_MAX_FINGERPRINTS = 400


def notify_phase_status(
    workspace_root: Path | str,
    phase: str,
    *,
    kind: str,
    message: str | None = None,
    learned: dict[str, Any] | None = None,
    missing: list[str] | None = None,
    error: str | None = None,
    stop_reason: str | None = None,
    next_step: str | None = None,
    dedupe: bool = True,
    expects_reply: bool = False,
) -> bool:
    """Send one honest status. Returns False when skipped, disabled, or undelivered."""
    phase_id = str(phase or "").strip().lower()
    if phase_id not in STATUS_PHASES:
        return False
    try:
        title, body, resolved = format_phase_status(
            phase_id,
            kind=kind,
            message=message,
            learned=learned,
            missing=missing,
            error=error,
            stop_reason=stop_reason,
            next_step=next_step,
            goal=_goal(phase_id) if str(kind).strip().lower() == "started" else None,
        )
        fp = fingerprint_phase_status(
            phase_id,
            kind=resolved,
            message=message,
            learned=learned,
            missing=missing,
            error=error,
            stop_reason=stop_reason,
            next_step=next_step,
        )
        root = Path(workspace_root)
        if dedupe and _already(root, fp):
            return False
        sent = _send(
            root,
            title,
            body,
            correlation_id=f"{phase_id}:{resolved}",
            expects_reply=expects_reply,
        )
        if sent:
            _remember(root, fp)
        return sent
    except Exception as exc:
        logger.warning("phase_status.notify_failed phase=%s kind=%s err=%s", phase_id, kind, exc)
        return False


def notify_phase_handoff(
    workspace_root: Path | str,
    *,
    completed: str,
    nxt: str,
    need_confirm: bool = False,
    auto: bool = False,
    token: str = "",
    expires_at: str = "",
    ttl_sec: int = 0,
    learned: dict[str, Any] | None = None,
    expects_reply: bool = False,
) -> bool:
    """Tell the operator what just finished and what the next phase is. Does not start it."""
    done = str(completed or "").strip().lower()
    target = str(nxt or "").strip().lower()
    if not done or not target:
        return False
    lines = [
        f"Fase {done} is afgerond.",
        f"Volgende fase: {target}.",
    ]
    if need_confirm:
        lines.append("REAL start niet vanzelf. Bevestig op de Phase Hub.")
    elif auto:
        lines.append("Auto-evolve start de volgende fase. REAL wordt nooit automatisch aangezet.")
    elif token:
        lines.append("Antwoord YES of CONFIRM om de volgende fase te starten.")
        lines.append(f"Token: {token}")
        if expires_at:
            lines.append(f"Token verloopt: {expires_at}")
        elif ttl_sec > 0:
            lines.append(f"Token TTL: ~{max(1, int(ttl_sec) // 3600)} uur.")
        lines.append("Of start op de Phase Hub.")
    else:
        lines.append("Open de Phase Hub om verder te gaan.")
    if done == "birth" and isinstance(learned, dict):
        _title, metric_body, _kind = format_phase_status(
            "birth",
            kind="progress",
            learned=learned,
        )
        if "Gemeten:" in metric_body:
            lines.append("Birth-meting (uit het continuum, niet herberekend):")
            lines.append(metric_body)
    body = "\n".join(lines)
    title = f"Volgende fase: {target}"
    fp = f"handoff|{done}|{target}|{int(need_confirm)}|{int(auto)}|{expires_at}|{token[-8:]}"
    root = Path(workspace_root)
    try:
        if _already(root, fp):
            return False
        sent = _send(
            root,
            title,
            body,
            correlation_id=f"handoff:{done}:{target}",
            expects_reply=expects_reply or bool(token),
        )
        if sent:
            _remember(root, fp)
        return sent
    except Exception as exc:
        logger.warning("phase_status.handoff_failed from=%s to=%s err=%s", done, target, exc)
        return False


def forget_phase_status(workspace_root: Path | str, phases: list[str] | tuple[str, ...]) -> None:
    """Drop dedupe keys after a wipe so the next run can notify again."""
    phase_ids = {str(phase).strip().lower() for phase in phases if str(phase).strip()}
    if not phase_ids:
        return
    prefixes = tuple(f"{phase}|" for phase in phase_ids)
    root = Path(workspace_root)
    with _LOCK:
        kept: list[str] = []
        for item in _load(root):
            if item.startswith(prefixes):
                continue
            if item.startswith("handoff|"):
                parts = item.split("|")
                if len(parts) > 1 and parts[1] in phase_ids:
                    continue
            kept.append(item)
        _save(root, kept)


def _goal(phase: str) -> str | None:
    try:
        from lumina_core.maturity.phase_specs import PHASE_SPECS

        spec = PHASE_SPECS.get(phase)
        if spec is None:
            return None
        return str(spec.human_goal or "") or None
    except Exception:
        return None


def _send(
    workspace_root: Path,
    title: str,
    body: str,
    *,
    correlation_id: str,
    expects_reply: bool = False,
) -> bool:
    from lumina_core.notifications.telegram_notifier import get_telegram_notifier

    notifier = get_telegram_notifier()
    notifier.configure_workspace(workspace_root)
    text = f"LUMINA STATUS — {title}\n\n{body}"
    return bool(
        notifier.send_message(
            text,
            kind="phase_status",
            correlation_id=correlation_id,
            expects_reply=expects_reply,
            source="phase_status_notify",
        )
    )


def _state_path(workspace_root: Path) -> Path:
    return workspace_root / "state" / _STATE_NAME


def _load(workspace_root: Path) -> list[str]:
    path = _state_path(workspace_root)
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return []
    items = raw.get("fingerprints") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    return [str(item) for item in items if item]


def _save(workspace_root: Path, fingerprints: list[str]) -> None:
    path = _state_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"fingerprints": fingerprints[-_MAX_FINGERPRINTS:]}
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")


def _already(workspace_root: Path, fingerprint: str) -> bool:
    with _LOCK:
        return fingerprint in _load(workspace_root)


def _remember(workspace_root: Path, fingerprint: str) -> None:
    with _LOCK:
        current = _load(workspace_root)
        if fingerprint in current:
            return
        current.append(fingerprint)
        _save(workspace_root, current)
