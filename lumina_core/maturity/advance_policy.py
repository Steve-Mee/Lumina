"""Advance policy after phase completion: manual | telegram | auto_evolve."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import (
    clear_pending_advance,
    load_continuum,
    next_phase_id,
    pending_advance_expired,
    set_pending_advance,
)

logger = get_logger("lumina.maturity.advance")


def on_phase_complete(workspace_root: Path | str, completed_phase: str) -> dict[str, Any]:
    """Decide what happens after a phase completes. Never auto-arms REAL capital."""
    root = Path(workspace_root)
    data = load_continuum(root)
    mode = str(data.get("advance_mode") or "manual")
    nxt = next_phase_id(list(data.get("completed_phases") or []))
    result: dict[str, Any] = {
        "completed": completed_phase,
        "next": nxt,
        "mode": mode,
        "action": "hub",
    }
    if not nxt:
        result["action"] = "complete"
        return result
    # REAL never pure auto
    if nxt == "real":
        result["action"] = "hub_real_confirm"
        _notify_phase_complete(root, completed_phase, nxt, need_confirm=True)
        return result

    if mode == "manual":
        result["action"] = "hub"
        _notify_phase_complete(root, completed_phase, nxt, need_confirm=False)
        return result

    if mode == "telegram":
        data = set_pending_advance(root, from_phase=completed_phase, to_phase=nxt)
        pending = data.get("pending_advance") or {}
        token = pending.get("telegram_token")
        expires_at = pending.get("expires_at")
        result["action"] = "telegram_confirm"
        result["telegram_token"] = token
        result["expires_at"] = expires_at
        _notify_telegram_advance(
            root,
            completed_phase,
            nxt,
            str(token or ""),
            expires_at=str(expires_at or ""),
            ttl_sec=int(pending.get("ttl_sec") or 86400),
        )
        return result

    if mode == "auto_evolve":
        result["action"] = "auto_start"
        result["start_phase"] = nxt
        _notify_phase_complete(root, completed_phase, nxt, need_confirm=False, auto=True)
        return result

    return result


def confirm_telegram_advance(
    workspace_root: Path | str,
    *,
    token: str,
) -> dict[str, Any]:
    root = Path(workspace_root)
    data = load_continuum(root)
    pending = data.get("pending_advance")
    if not isinstance(pending, dict):
        return {"ok": False, "error": "no_pending_advance"}
    if str(pending.get("telegram_token") or "") != str(token or ""):
        return {"ok": False, "error": "invalid_token"}
    if pending_advance_expired(pending):
        clear_pending_advance(root)
        return {
            "ok": False,
            "error": "token_expired",
            "expires_at": pending.get("expires_at"),
        }
    to_phase = str(pending.get("to") or "")
    clear_pending_advance(root)
    return {"ok": True, "start_phase": to_phase}


def reissue_telegram_advance(workspace_root: Path | str) -> dict[str, Any]:
    """Issue a fresh TTL token for next phase when advance_mode is telegram."""
    root = Path(workspace_root)
    data = load_continuum(root)
    if str(data.get("advance_mode") or "") != "telegram":
        return {"ok": False, "error": "advance_mode_not_telegram"}
    completed = list(data.get("completed_phases") or [])
    nxt = next_phase_id(completed)
    if not nxt or nxt == "real":
        return {"ok": False, "error": "no_reissuable_next_phase", "next": nxt}
    from_phase = completed[-1] if completed else "genesis"
    data = set_pending_advance(root, from_phase=from_phase, to_phase=nxt)
    pending = data.get("pending_advance") or {}
    token = str(pending.get("telegram_token") or "")
    expires_at = str(pending.get("expires_at") or "")
    _notify_telegram_advance(
        root,
        from_phase,
        nxt,
        token,
        expires_at=expires_at,
        ttl_sec=int(pending.get("ttl_sec") or 86400),
    )
    from lumina_core.maturity.continuum import pending_advance_remaining_sec

    remaining = pending_advance_remaining_sec(pending if isinstance(pending, dict) else None)
    return {
        "ok": True,
        "from": from_phase,
        "to": nxt,
        "expires_at": expires_at,
        "ttl_sec": int(pending.get("ttl_sec") or 86400) if isinstance(pending, dict) else None,
        "remaining_sec": remaining,
        "has_token": bool(token),
        "status": "active",
        "message": (
            f"New Telegram advance token for {from_phase} → {nxt}. "
            f"Expires {expires_at} (remaining ~{remaining}s)."
            if remaining is not None
            else f"New Telegram advance token for {from_phase} → {nxt}."
        ),
    }


def try_handle_telegram_text(workspace_root: Path | str, text: str) -> dict[str, Any] | None:
    """Parse YES / CONFIRM / ADVANCE + token from Telegram body. Returns None if not advance-related."""
    raw = str(text or "").strip()
    if not raw:
        return None
    upper = raw.upper()
    parts = raw.split()
    token: str | None = None
    if parts and parts[0].upper() in ("YES", "CONFIRM", "ADVANCE", "START") and len(parts) >= 2:
        token = parts[1]
    elif len(parts) == 1 and len(parts[0]) >= 12:
        token = parts[0]
    if not token:
        data = load_continuum(workspace_root)
        pending = data.get("pending_advance")
        if isinstance(pending, dict) and upper in ("YES", "CONFIRM", "ADVANCE", "START"):
            token = str(pending.get("telegram_token") or "")
    if not token:
        return None
    conf = confirm_telegram_advance(workspace_root, token=token)
    if not conf.get("ok"):
        return conf
    try:
        from lumina_core.maturity.maturity_service import maturity_service

        maturity_service.configure_workspace(Path(workspace_root))
        return maturity_service.start_phase(str(conf.get("start_phase") or ""), explicit_user_start=True)
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _notify_phase_complete(
    root: Path,
    completed: str,
    nxt: str,
    *,
    need_confirm: bool,
    auto: bool = False,
) -> None:
    try:
        from lumina_core.notifications.attention_notifier import notify_attention
        from lumina_core.notifications.milestone_events import MilestoneCategory, MilestoneEvent

        summary = (
            f"Phase {completed} complete. Next: {nxt}."
            + (" Confirm REAL on hub." if need_confirm else "")
            + (" Auto-evolve will start next." if auto else " Open Phase Hub to continue.")
        )
        ev = MilestoneEvent(
            milestone_id=f"phase_complete:{completed}",
            category=MilestoneCategory.BIRTH,
            title=f"Phase complete: {completed}",
            summary=summary,
            context={"next": nxt, "auto": auto},
            dedupe_key=f"phase_complete:{completed}",
        )
        notify_attention(ev, workspace_root=root)
    except Exception as exc:
        logger.debug("advance.notify_failed: %s", exc)


def _notify_telegram_advance(
    root: Path,
    completed: str,
    nxt: str,
    token: str,
    *,
    expires_at: str = "",
    ttl_sec: int = 86400,
) -> None:
    try:
        from lumina_core.notifications.attention_notifier import notify_attention
        from lumina_core.notifications.milestone_events import MilestoneCategory, MilestoneEvent

        hours = max(1, int(ttl_sec) // 3600)
        expiry_line = (
            f"Token expires: {expires_at} (~{hours}h). Reply before then.\n"
            if expires_at
            else f"Token TTL: ~{hours}h.\n"
        )
        summary = (
            f"Phase {completed} complete. Reply YES <token> to start {nxt}.\n"
            f"Token: {token}\n"
            f"{expiry_line}"
            f"Or open Phase Hub on PC and press Start / paste token."
        )
        # M7: include expires_at in dedupe so reissue is not swallowed as noise
        dedupe_suffix = str(expires_at or token or "")[-24:]
        ev = MilestoneEvent(
            milestone_id=f"phase_advance_request:{completed}:{nxt}",
            category=MilestoneCategory.BIRTH,
            title=f"Start next phase? → {nxt}",
            summary=summary,
            context={
                "token": token,
                "to": nxt,
                "from": completed,
                "expires_at": expires_at,
                "ttl_sec": ttl_sec,
            },
            dedupe_key=f"phase_advance_request:{completed}:{nxt}:{dedupe_suffix}",
        )
        notify_attention(ev, workspace_root=root)
    except Exception as exc:
        logger.debug("advance.telegram_notify_failed: %s", exc)
