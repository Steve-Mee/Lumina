"""Append-only Telegram I/O journal (ADR-0043).

One list for every outbound/inbound message plus Twin question→answer threads.
Not a capital hash-chain: operator comms, not order audit.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from lumina_core.config_loader import ConfigLoader
from lumina_core.state.state_manager import safe_append_jsonl

SCHEMA_VERSION = "telegram_message_v1"
DEFAULT_RELATIVE_PATH = "state/monitoring_telegram_messages.jsonl"
THREAD_RESOLVED_KIND = "thread.resolved"

Direction = Literal["in", "out", "reply"]

_MAX_TEXT = 8000
_TAIL_MULTIPLIER = 8
_TAIL_FLOOR = 500


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_state_relative(relative: str, workspace_root: Path | str | None = None) -> Path:
    """Resolve a state/… path, honouring LUMINA_STATE_DIR when no workspace is given."""
    rel = Path(relative)
    if rel.is_absolute():
        return rel
    if workspace_root is not None:
        return Path(workspace_root) / rel
    env = os.getenv("LUMINA_STATE_DIR", "").strip()
    if env:
        parts = rel.parts
        if parts and parts[0] == "state":
            rest = Path(*parts[1:]) if len(parts) > 1 else Path()
            return Path(env) / rest
        return Path(env) / rel
    return Path.cwd() / rel


def resolve_journal_path(workspace_root: Path | str | None = None) -> Path:
    cfg = ConfigLoader.section("telegram", default={})
    rel = DEFAULT_RELATIVE_PATH
    if isinstance(cfg, dict):
        raw = str(cfg.get("journal_path") or "").strip()
        if raw:
            rel = raw
    return resolve_state_relative(rel, workspace_root)


def append_message(
    *,
    direction: Direction,
    kind: str,
    text: str,
    correlation_id: str = "",
    in_reply_to: str = "",
    expects_reply: bool = False,
    source: str = "",
    delivered: bool = True,
    drop_reason: str | None = None,
    telegram_message_id: int | None = None,
    telegram_update_id: int | None = None,
    resolved_by: str = "",
    question_text: str = "",
    reply_text: str = "",
    path: Path | str | None = None,
    workspace_root: Path | str | None = None,
) -> dict[str, Any]:
    """Append one journal row. Best-effort: never raises to callers."""
    target = Path(path) if path is not None else resolve_journal_path(workspace_root)
    record: dict[str, Any] = {
        "schema": SCHEMA_VERSION,
        "id": str(uuid4()),
        "ts": _utcnow(),
        "direction": str(direction),
        "kind": str(kind or "operator"),
        "text": str(text or "")[:_MAX_TEXT],
        "correlation_id": str(correlation_id or ""),
        "in_reply_to": str(in_reply_to or ""),
        "expects_reply": bool(expects_reply),
        "source": str(source or ""),
        "delivered": bool(delivered),
        "drop_reason": str(drop_reason) if drop_reason else None,
        "telegram_message_id": telegram_message_id,
        "telegram_update_id": telegram_update_id,
        "resolved_by": str(resolved_by or ""),
        "question_text": str(question_text or "")[:_MAX_TEXT],
        "reply_text": str(reply_text or "")[:_MAX_TEXT],
    }
    try:
        return safe_append_jsonl(target, record, hash_chain=False)
    except Exception:
        return record


def record_outbound(
    *,
    text: str,
    kind: str,
    correlation_id: str = "",
    expects_reply: bool = False,
    source: str = "",
    delivered: bool = True,
    drop_reason: str | None = None,
    telegram_message_id: int | None = None,
    path: Path | str | None = None,
    workspace_root: Path | str | None = None,
) -> dict[str, Any]:
    return append_message(
        direction="out",
        kind=kind,
        text=text,
        correlation_id=correlation_id,
        expects_reply=expects_reply,
        source=source,
        delivered=delivered,
        drop_reason=drop_reason,
        telegram_message_id=telegram_message_id,
        path=path,
        workspace_root=workspace_root,
    )


def record_inbound(
    *,
    text: str,
    kind: str = "operator",
    correlation_id: str = "",
    in_reply_to: str = "",
    source: str = "telegram_poll",
    telegram_update_id: int | None = None,
    telegram_message_id: int | None = None,
    path: Path | str | None = None,
    workspace_root: Path | str | None = None,
) -> dict[str, Any]:
    return append_message(
        direction="in",
        kind=kind,
        text=text,
        correlation_id=correlation_id,
        in_reply_to=in_reply_to,
        source=source,
        delivered=True,
        telegram_update_id=telegram_update_id,
        telegram_message_id=telegram_message_id,
        path=path,
        workspace_root=workspace_root,
    )


def lookup_question_text(
    correlation_id: str,
    *,
    path: Path | str | None = None,
    workspace_root: Path | str | None = None,
) -> str:
    cid = str(correlation_id or "").strip()
    if not cid:
        return ""
    target = Path(path) if path is not None else resolve_journal_path(workspace_root)
    for rec in reversed(_read_jsonl_tail(target, max_lines=2000)):
        if str(rec.get("correlation_id") or "") != cid:
            continue
        if rec.get("kind") == THREAD_RESOLVED_KIND:
            continue
        if rec.get("expects_reply") or rec.get("direction") == "out":
            return str(rec.get("text") or "")[:_MAX_TEXT]
    return ""


def record_reply(
    *,
    correlation_id: str,
    reply_text: str,
    resolved_by: str,
    kind: str,
    source: str = "",
    question_text: str = "",
    telegram_update_id: int | None = None,
    path: Path | str | None = None,
    workspace_root: Path | str | None = None,
) -> dict[str, Any]:
    """Log the operator answer and a joined Q+A thread.resolved row."""
    cid = str(correlation_id or "").strip()
    answer = str(reply_text or "")
    qtext = str(question_text or "").strip()
    if not qtext:
        qtext = lookup_question_text(cid, path=path, workspace_root=workspace_root)
    direction: Direction = "in" if str(resolved_by or "").lower() == "telegram" else "reply"
    reply_rec = append_message(
        direction=direction,
        kind=kind,
        text=answer,
        correlation_id=cid,
        in_reply_to=cid,
        source=source,
        delivered=True,
        telegram_update_id=telegram_update_id,
        resolved_by=str(resolved_by or ""),
        question_text=qtext,
        reply_text=answer,
        path=path,
        workspace_root=workspace_root,
    )
    joined = ""
    if qtext:
        joined = f"Q: {qtext}\nA: {answer}"
    else:
        joined = f"A: {answer}"
    resolved = append_message(
        direction="reply",
        kind=THREAD_RESOLVED_KIND,
        text=joined,
        correlation_id=cid,
        in_reply_to=cid,
        source=source,
        delivered=True,
        resolved_by=str(resolved_by or ""),
        question_text=qtext,
        reply_text=answer,
        path=path,
        workspace_root=workspace_root,
    )
    return {"reply": reply_rec, "resolved": resolved}


def list_records(
    *,
    limit: int = 200,
    path: Path | str | None = None,
    workspace_root: Path | str | None = None,
) -> list[dict[str, Any]]:
    cap = max(1, min(int(limit), 2000))
    target = Path(path) if path is not None else resolve_journal_path(workspace_root)
    rows = _read_jsonl_tail(target, max_lines=max(cap * _TAIL_MULTIPLIER, _TAIL_FLOOR))
    return rows[-cap:]


def list_threads(
    *,
    limit: int = 200,
    path: Path | str | None = None,
    workspace_root: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Chronological operator list: questions with attached reply when present."""
    cap = max(1, min(int(limit), 2000))
    target = Path(path) if path is not None else resolve_journal_path(workspace_root)
    rows = _read_jsonl_tail(target, max_lines=max(cap * _TAIL_MULTIPLIER, _TAIL_FLOOR))
    replies: dict[str, dict[str, Any]] = {}
    for rec in rows:
        cid = str(rec.get("correlation_id") or rec.get("in_reply_to") or "").strip()
        if not cid:
            continue
        if rec.get("kind") == THREAD_RESOLVED_KIND:
            replies[cid] = {
                "ts": rec.get("ts"),
                "text": rec.get("reply_text") or rec.get("text"),
                "resolved_by": rec.get("resolved_by") or "",
            }
            continue
        if rec.get("in_reply_to") or rec.get("direction") in {"in", "reply"}:
            if rec.get("expects_reply"):
                continue
            if rec.get("direction") == "out":
                continue
            replies[cid] = {
                "ts": rec.get("ts"),
                "text": rec.get("reply_text") or rec.get("text"),
                "resolved_by": rec.get("resolved_by") or "",
            }

    attached: set[str] = set()
    out: list[dict[str, Any]] = []
    for rec in rows:
        if rec.get("kind") == THREAD_RESOLVED_KIND:
            continue
        cid = str(rec.get("correlation_id") or "").strip()
        if rec.get("expects_reply") and rec.get("direction") == "out":
            item = _public_row(rec)
            if cid and cid in replies:
                item["reply"] = dict(replies[cid])
                attached.add(cid)
            else:
                item["reply"] = None
            out.append(item)
            continue
        if rec.get("in_reply_to") or (cid and cid in attached and rec.get("direction") != "out"):
            continue
        if rec.get("direction") == "out" or rec.get("direction") == "in":
            item = _public_row(rec)
            item["reply"] = None
            out.append(item)
    return out[-cap:]


def _public_row(rec: dict[str, Any]) -> dict[str, Any]:
    return {
        "ts": rec.get("ts"),
        "direction": rec.get("direction"),
        "kind": rec.get("kind"),
        "text": rec.get("text"),
        "correlation_id": rec.get("correlation_id") or "",
        "expects_reply": bool(rec.get("expects_reply")),
        "delivered": bool(rec.get("delivered", True)),
        "drop_reason": rec.get("drop_reason"),
        "source": rec.get("source") or "",
        "resolved_by": rec.get("resolved_by") or "",
        "telegram_update_id": rec.get("telegram_update_id"),
        "telegram_message_id": rec.get("telegram_message_id"),
    }


def _read_jsonl_tail(path: Path, *, max_lines: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    out: list[dict[str, Any]] = []
    for line in lines[-max(1, int(max_lines)) :]:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out
