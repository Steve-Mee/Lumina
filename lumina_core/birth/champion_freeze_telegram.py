"""Telegram bridge for champion freeze (OR5) — remote accept/wipe + app echo.

Autonomy goal: operator can resolve freeze away from the PC via Telegram; app
and CLI decisions are mirrored to Telegram for auditability.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.champion_freeze_telegram")

PENDING_REL = Path("state") / "champion_freeze_telegram_pending.json"
_POLL_LOCK = threading.Lock()
_LAST_POLL_MONO: dict[str, float] = {}
_POLL_MIN_INTERVAL_SEC = 8.0

# Canonical reply tokens (case-insensitive)
CMD_ACCEPT = "ACCEPT"
CMD_ACCEPT_NO_START = "ACCEPT_NO_START"
CMD_WIPE = "WIPE"
CMD_WIPE_FULL = "WIPE_FULL"
CMD_STATUS = "STATUS"
CMD_HELP = "HELP"

_FREEZE_CMDS = frozenset(
    {
        CMD_ACCEPT,
        CMD_ACCEPT_NO_START,
        CMD_WIPE,
        CMD_WIPE_FULL,
        CMD_STATUS,
        CMD_HELP,
        "ACCEPT_CHAMPION",
        "WIPE_AND_RETRY",
        "WIPE_KEEP_CACHE",
    }
)


def pending_path(workspace_root: Path | str) -> Path:
    return Path(workspace_root) / PENDING_REL


def load_pending(workspace_root: Path | str) -> dict[str, Any] | None:
    path = pending_path(workspace_root)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else None
    except Exception:
        return None


def write_pending(workspace_root: Path | str, payload: dict[str, Any]) -> None:
    path = pending_path(workspace_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = dict(payload)
    body["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(body, indent=2, ensure_ascii=True), encoding="utf-8")


def clear_pending(workspace_root: Path | str) -> None:
    path = pending_path(workspace_root)
    try:
        if path.is_file():
            path.unlink()
    except Exception as exc:
        logger.debug("champion_freeze_telegram.clear_pending_failed: %s", exc)


def format_freeze_telegram_body(card: dict[str, Any]) -> str:
    """Human-readable freeze questions for Telegram (mirrors app popup)."""
    lines = [
        "LUMINA — Champion freeze (sacred fork)",
        "",
        str(card.get("guidance") or "Accept champion or wipe. Do not train through freeze."),
        "",
        f"phase: {card.get('phase') or '-'} / {card.get('sub_phase') or '-'}",
        f"trades: {card.get('cumulative_trades')}  budget_left: {card.get('trade_budget_remaining')}",
    ]
    if card.get("stage_blocker_metric"):
        lines.append(
            f"blocker: {card.get('stage_blocker_metric')}={card.get('stage_blocker_value')} "
            f"wr={card.get('stage_winrate')} edgescore={card.get('edgescore')}"
        )
    if card.get("pass_reason"):
        lines.append(f"detail: {card.get('pass_reason')}")
    lines.extend(
        [
            "",
            "Reply with ONE command:",
            "• ACCEPT — accept champion and continue training",
            "• ACCEPT_NO_START — accept champion, clear freeze only (checklist first)",
            "• WIPE — wipe birth training (keep tick cache)",
            "• WIPE_FULL — wipe all birth training data",
            "• STATUS — re-send this decision card",
            "",
            "Checklist: docs/birth-stage2-certified-reentry-checklist.md",
            "CLI: python scripts/validation/champion_freeze_ops.py --workspace . status",
        ]
    )
    return "\n".join(lines)


def notify_champion_freeze_decision(
    workspace_root: Path | str,
    *,
    progress: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Send freeze questions to Telegram + attention SSOT. Idempotent via pending."""
    from lumina_core.birth.champion_freeze_ops import build_champion_freeze_decision_card
    from lumina_core.notifications.attention_events import birth_champion_freeze_event
    from lumina_core.notifications.attention_notifier import notify_attention

    root = Path(workspace_root)
    prog = dict(progress or {})
    if not prog:
        try:
            from lumina_core.birth.progress import read_birth_progress

            prog = dict(read_birth_progress(root) or {})
        except Exception:
            prog = {}

    card = build_champion_freeze_decision_card(progress=prog, workspace=str(root))
    if not card.get("freeze_active"):
        return {"ok": False, "error": "no_freeze", "card": card}

    pending = load_pending(root)
    if pending and pending.get("status") == "pending" and not force:
        # Already asked — still ensure attention fields, skip Telegram spam
        return {"ok": True, "skipped": "already_pending", "card": card, "pending": pending}

    wr = None
    try:
        wr = float(card.get("stage_winrate")) if card.get("stage_winrate") is not None else None
    except (TypeError, ValueError):
        wr = None

    event = birth_champion_freeze_event(
        summary=str(card.get("guidance") or "Champion freeze — accept or wipe."),
        stage_trades=int(card.get("cumulative_trades") or 0),
        winrate=wr,
        blocker_detail=str(card.get("pass_reason") or ""),
        reason_code=str(
            prog.get("swarm_fail_reason_code")
            or prog.get("attention_reason_code")
            or "swarm_no_tournament_lift"
        ),
    )
    notify_attention(event, workspace_root=root)

    body = format_freeze_telegram_body(card)
    sent = False
    try:
        from lumina_core.notifications.telegram_notifier import TelegramNotifier

        tg = TelegramNotifier()
        if hasattr(tg, "configure_workspace"):
            tg.configure_workspace(root)  # type: ignore[attr-defined]
        else:
            setattr(tg, "_workspace_root", root)
        sent = bool(tg.send_attention_alert(event.title, body, severity="critical"))
    except Exception as exc:
        logger.warning("champion_freeze_telegram.notify_send_failed: %s", exc)

    pending_payload = {
        "schema": "champion_freeze_telegram_pending_v1",
        "status": "pending",
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "telegram_sent": sent,
        "decision": card.get("decision"),
        "commands": [CMD_ACCEPT, CMD_ACCEPT_NO_START, CMD_WIPE, CMD_WIPE_FULL, CMD_STATUS],
        "checklist": "docs/birth-stage2-certified-reentry-checklist.md",
    }
    write_pending(root, pending_payload)
    return {"ok": True, "telegram_sent": sent, "card": card, "pending": pending_payload}


def parse_freeze_telegram_command(text: str) -> str | None:
    """Return normalized freeze command or None if not a freeze reply."""
    raw = str(text or "").strip()
    if not raw:
        return None
    # First token only; allow "ACCEPT please"
    token = raw.split()[0].strip().upper().replace("-", "_")
    aliases = {
        "ACCEPT_CHAMPION": CMD_ACCEPT,
        "WIPE_AND_RETRY": CMD_WIPE,
        "WIPE_KEEP_CACHE": CMD_WIPE,
        "WIPE_KEEP": CMD_WIPE,
        "ACCEPTONLY": CMD_ACCEPT_NO_START,
        "ACCEPT_ONLY": CMD_ACCEPT_NO_START,
    }
    token = aliases.get(token, token)
    if token in _FREEZE_CMDS or token in {
        CMD_ACCEPT,
        CMD_ACCEPT_NO_START,
        CMD_WIPE,
        CMD_WIPE_FULL,
        CMD_STATUS,
        CMD_HELP,
    }:
        return token
    return None


def try_handle_telegram_freeze_text(
    workspace_root: Path | str,
    text: str,
    *,
    apply: bool = True,
) -> dict[str, Any] | None:
    """Handle Telegram freeze replies. Returns None if text is not freeze-related.

    When freeze is not active, STATUS/HELP may still answer; mutations require freeze
    (or pending) unless command is STATUS.
    """
    cmd = parse_freeze_telegram_command(text)
    if cmd is None:
        return None

    root = Path(workspace_root)
    from lumina_core.birth.champion_freeze_ops import (
        build_champion_freeze_decision_card,
        freeze_active_from_workspace_payloads,
    )

    progress = {}
    try:
        from lumina_core.birth.progress import read_birth_progress

        progress = dict(read_birth_progress(root) or {})
    except Exception:
        progress = {}

    freeze = freeze_active_from_workspace_payloads(progress=progress, checkpoint_metrics=None)
    pending = load_pending(root)

    if cmd in (CMD_STATUS, CMD_HELP):
        card = build_champion_freeze_decision_card(progress=progress, workspace=str(root))
        body = format_freeze_telegram_body(card)
        _send_plain(root, body)
        return {"ok": True, "action": "status", "freeze_active": freeze, "card": card}

    if not freeze and not (pending and pending.get("status") == "pending"):
        _send_plain(
            root,
            "Lumina: no champion freeze open. Nothing to ACCEPT/WIPE. "
            "Send STATUS to refresh.",
        )
        return {"ok": False, "error": "no_freeze", "action": cmd}

    if not apply:
        return {"ok": True, "action": cmd, "dry_run": True, "freeze_active": freeze}

    return apply_freeze_command(root, cmd, source="telegram")


def apply_freeze_command(
    workspace_root: Path | str,
    cmd: str,
    *,
    source: str = "telegram",
    target_trades: int | None = None,
) -> dict[str, Any]:
    """Execute ACCEPT / WIPE from Telegram (or internal caller)."""
    root = Path(workspace_root)
    normalized = parse_freeze_telegram_command(cmd) or str(cmd).strip().upper()

    try:
        from lumina_launcher.services.birth_service import BirthService

        svc = BirthService()
        if hasattr(svc, "configure_workspace"):
            svc.configure_workspace(root)
    except Exception as exc:
        msg = f"Lumina: cannot open BirthService ({exc})"
        _send_plain(root, msg)
        return {"ok": False, "error": str(exc), "action": normalized}

    result: dict[str, Any]
    if normalized == CMD_ACCEPT:
        result = svc.accept_champion_birth(
            target_trades=target_trades,
            start=True,
            source=source,
        )
        clear_pending(root)
        _send_plain(
            root,
            "Lumina: ACCEPT received via Telegram — champion accepted, training continue requested.\n"
            "Next: docs/birth-stage2-certified-reentry-checklist.md (watch Stage 2 flat band).",
        )
        return {"ok": True, "action": CMD_ACCEPT, "result": result, "source": source}

    if normalized == CMD_ACCEPT_NO_START:
        result = svc.accept_champion_birth(
            target_trades=target_trades,
            start=False,
            source=source,
        )
        clear_pending(root)
        _send_plain(
            root,
            "Lumina: ACCEPT_NO_START — freeze cleared, Birth NOT started.\n"
            "Follow checklist, then start certified Stage 2 re-entry from the app or CLI.",
        )
        return {"ok": True, "action": CMD_ACCEPT_NO_START, "result": result, "source": source}

    if normalized in (CMD_WIPE, "WIPE_KEEP_CACHE", "WIPE_AND_RETRY"):
        result = svc.wipe_all_birth_data(
            preserve_tick_cache=True,
            source=source,
        )
        clear_pending(root)
        status = str(result.get("status") or "")
        if status == "rejected":
            _send_plain(root, f"Lumina: WIPE rejected — {result.get('message')}")
            return {"ok": False, "action": CMD_WIPE, "result": result, "source": source}
        _send_plain(
            root,
            "Lumina: WIPE (keep tick cache) completed via Telegram.\n"
            "Re-enter Birth via checklist (full curriculum if genesis required).",
        )
        return {"ok": True, "action": CMD_WIPE, "result": result, "source": source}

    if normalized == CMD_WIPE_FULL:
        result = svc.wipe_all_birth_data(
            preserve_tick_cache=False,
            source=source,
        )
        clear_pending(root)
        status = str(result.get("status") or "")
        if status == "rejected":
            _send_plain(root, f"Lumina: WIPE_FULL rejected — {result.get('message')}")
            return {"ok": False, "action": CMD_WIPE_FULL, "result": result, "source": source}
        _send_plain(
            root,
            "Lumina: WIPE_FULL completed via Telegram.\n"
            "Setup/genesis may be required before certified Birth re-entry.",
        )
        return {"ok": True, "action": CMD_WIPE_FULL, "result": result, "source": source}

    _send_plain(root, f"Lumina: unknown freeze command `{normalized}`. Send HELP.")
    return {"ok": False, "error": "unknown_command", "action": normalized}


def echo_operator_decision(
    workspace_root: Path | str,
    *,
    action: str,
    source: str,
    detail: str = "",
    started: bool | None = None,
) -> bool:
    """Mirror app/CLI operator choice into Telegram chat (audit + remote awareness)."""
    root = Path(workspace_root)
    src = str(source or "app").strip().lower()
    # Telegram apply path already sends a confirmation; still echo for dual-path clarity
    # is optional — skip only pure internal dry runs.
    if src == "echo_skip":
        return False
    act = str(action or "").strip().upper()
    lines = [
        "LUMINA — Operator decision recorded",
        f"action: {act}",
        f"source: {src}",
    ]
    if started is not None:
        lines.append(f"birth_started: {bool(started)}")
    if detail:
        lines.append(str(detail)[:500])
    lines.append(f"at: {datetime.now(timezone.utc).isoformat()}")
    lines.append("Checklist: docs/birth-stage2-certified-reentry-checklist.md")
    ok = _send_plain(root, "\n".join(lines))
    if act in {CMD_ACCEPT, CMD_ACCEPT_NO_START, CMD_WIPE, CMD_WIPE_FULL, "ACCEPT", "WIPE"}:
        if src in {"app", "cli", "api", "tauri", "ui"}:
            clear_pending(root)
    return ok


def maybe_poll_freeze_telegram(
    workspace_root: Path | str,
    *,
    force: bool = False,
) -> list[dict[str, Any]]:
    """Poll Telegram for freeze replies when freeze/pending active. Throttled."""
    root = Path(workspace_root)
    key = str(root.resolve())
    now = time.monotonic()
    with _POLL_LOCK:
        last = _LAST_POLL_MONO.get(key, 0.0)
        if not force and (now - last) < _POLL_MIN_INTERVAL_SEC:
            return []
        _LAST_POLL_MONO[key] = now

    # Only poll when there is something to resolve or pending questions
    try:
        from lumina_core.birth.champion_freeze_ops import freeze_active_from_workspace_payloads
        from lumina_core.birth.progress import read_birth_progress

        progress = dict(read_birth_progress(root) or {})
        freeze = freeze_active_from_workspace_payloads(progress=progress, checkpoint_metrics=None)
        pending = load_pending(root)
        if not freeze and not (pending and pending.get("status") == "pending"):
            return []
    except Exception:
        # Fail open to poll if we cannot read progress
        pass

    try:
        from lumina_core.notifications.telegram_notifier import TelegramNotifier

        tg = TelegramNotifier()
        if hasattr(tg, "configure_workspace"):
            tg.configure_workspace(root)  # type: ignore[attr-defined]
        else:
            setattr(tg, "_workspace_root", root)
        return list(tg.poll_for_replies() or [])
    except Exception as exc:
        logger.debug("champion_freeze_telegram.poll_failed: %s", exc)
        return []


def _send_plain(workspace_root: Path, message: str) -> bool:
    try:
        from lumina_core.notifications.telegram_notifier import TelegramNotifier

        tg = TelegramNotifier()
        if hasattr(tg, "configure_workspace"):
            tg.configure_workspace(workspace_root)  # type: ignore[attr-defined]
        else:
            setattr(tg, "_workspace_root", workspace_root)
        return bool(tg._send_telegram_message(message))  # noqa: SLF001 — shared send path
    except Exception as exc:
        logger.debug("champion_freeze_telegram.send_failed: %s", exc)
        return False


__all__ = [
    "CMD_ACCEPT",
    "CMD_ACCEPT_NO_START",
    "CMD_HELP",
    "CMD_STATUS",
    "CMD_WIPE",
    "CMD_WIPE_FULL",
    "apply_freeze_command",
    "clear_pending",
    "echo_operator_decision",
    "format_freeze_telegram_body",
    "load_pending",
    "maybe_poll_freeze_telegram",
    "notify_champion_freeze_decision",
    "parse_freeze_telegram_command",
    "try_handle_telegram_freeze_text",
    "write_pending",
]
