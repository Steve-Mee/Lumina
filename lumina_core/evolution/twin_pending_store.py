"""Durable pending Twin questions (base session, micro, escalations).

Dual-channel: deck + telegram share the same pending id + resolve token.
First valid resolve wins (idempotent). TTL expiry is fail-closed.
"""

from __future__ import annotations

import json
import secrets
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lumina_core.evolution.twin_curriculum_types import (
    DEFAULT_ESCALATION_TTL_SEC,
    PendingKind,
    PendingStatus,
    ResolvedBy,
)

_DEFAULT_PATH = Path("state/twin_pending_questions.json")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _utcnow()).isoformat()


@dataclass
class TwinPendingRecord:
    pending_id: str
    kind: PendingKind
    status: PendingStatus
    created_at: str
    expires_at: str
    resolve_token: str
    question: dict[str, Any]
    channels: dict[str, bool] = field(default_factory=lambda: {"deck": True, "telegram": False})
    channel_policy: str = "app_only"
    context: dict[str, Any] = field(default_factory=dict)
    answer: dict[str, Any] | None = None
    resolved_by: str | None = None
    resolved_at: str | None = None
    dna_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def public_dict(self, *, include_token: bool = False) -> dict[str, Any]:
        """Hub-safe view; never leak resolve_token unless include_token (internal)."""
        d = self.to_dict()
        if not include_token:
            d.pop("resolve_token", None)
        return d

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> TwinPendingRecord:
        return cls(
            pending_id=str(raw.get("pending_id") or ""),
            kind=str(raw.get("kind") or "escalation"),  # type: ignore[arg-type]
            status=str(raw.get("status") or "pending"),  # type: ignore[arg-type]
            created_at=str(raw.get("created_at") or ""),
            expires_at=str(raw.get("expires_at") or ""),
            resolve_token=str(raw.get("resolve_token") or ""),
            question=dict(raw.get("question") or {}),
            channels=dict(raw.get("channels") or {"deck": True, "telegram": False}),
            channel_policy=str(raw.get("channel_policy") or "app_only"),
            context=dict(raw.get("context") or {}),
            answer=raw.get("answer") if isinstance(raw.get("answer"), dict) else None,
            resolved_by=str(raw["resolved_by"]) if raw.get("resolved_by") else None,
            resolved_at=str(raw["resolved_at"]) if raw.get("resolved_at") else None,
            dna_hash=str(raw.get("dna_hash") or ""),
        )


class TwinPendingStore:
    """JSON-backed pending store with RLock (local, no cloud)."""

    def __init__(self, path: Path | str = _DEFAULT_PATH) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._records: dict[str, TwinPendingRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._records = {}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            items = raw.get("records") if isinstance(raw, dict) else raw
            out: dict[str, TwinPendingRecord] = {}
            if isinstance(items, list):
                for row in items:
                    if isinstance(row, dict) and row.get("pending_id"):
                        rec = TwinPendingRecord.from_dict(row)
                        out[rec.pending_id] = rec
            elif isinstance(items, dict):
                for pid, row in items.items():
                    if isinstance(row, dict):
                        row = {**row, "pending_id": row.get("pending_id") or pid}
                        rec = TwinPendingRecord.from_dict(row)
                        out[rec.pending_id] = rec
            self._records = out
        except (OSError, json.JSONDecodeError, TypeError):
            self._records = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "updated_at": _iso(),
            "records": [r.to_dict() for r in self._records.values()],
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def create(
        self,
        *,
        kind: PendingKind,
        question: dict[str, Any],
        channel_policy: str = "app_only",
        channels: dict[str, bool] | None = None,
        context: dict[str, Any] | None = None,
        dna_hash: str = "",
        ttl_sec: int = DEFAULT_ESCALATION_TTL_SEC,
        pending_id: str | None = None,
    ) -> TwinPendingRecord:
        now = _utcnow()
        ttl = max(60, min(7 * 86400, int(ttl_sec)))
        ch = channels or {"deck": True, "telegram": channel_policy == "dual"}
        if channel_policy == "app_only":
            ch = {"deck": True, "telegram": False}
        rec = TwinPendingRecord(
            pending_id=str(pending_id or secrets.token_urlsafe(12)),
            kind=kind,
            status="pending",
            created_at=_iso(now),
            expires_at=_iso(now + timedelta(seconds=ttl)),
            resolve_token=secrets.token_urlsafe(16),
            question=dict(question),
            channels=dict(ch),
            channel_policy=str(channel_policy),
            context=dict(context or {}),
            dna_hash=str(dna_hash or question.get("context_dna_hash") or ""),
        )
        with self._lock:
            self._expire_unlocked(now=now)
            self._records[rec.pending_id] = rec
            self._save()
        return rec

    def get(self, pending_id: str) -> TwinPendingRecord | None:
        with self._lock:
            self._expire_unlocked()
            return self._records.get(str(pending_id))

    def get_by_prefix(self, pending_id: str) -> TwinPendingRecord | None:
        pid = str(pending_id or "").strip()
        if not pid:
            return None
        exact = self.get(pid)
        if exact is not None:
            return exact
        with self._lock:
            self._expire_unlocked()
            matches = [
                rec
                for rec in self._records.values()
                if rec.pending_id.startswith(pid) or pid.startswith(rec.pending_id[:10])
            ]
        pending = [rec for rec in matches if rec.status == "pending"]
        pool = pending or matches
        if len(pool) == 1:
            return pool[0]
        return None

    def find_open(self, *, kind: PendingKind, dna_hash: str) -> TwinPendingRecord | None:
        dna = str(dna_hash or "").strip()
        if not dna:
            return None
        for rec in self.list_pending(kind=kind):
            if rec.dna_hash == dna:
                return rec
        return None

    def list_pending(
        self,
        *,
        kind: PendingKind | None = None,
        include_expired: bool = False,
    ) -> list[TwinPendingRecord]:
        with self._lock:
            self._expire_unlocked()
            out: list[TwinPendingRecord] = []
            for rec in self._records.values():
                if kind is not None and rec.kind != kind:
                    continue
                if rec.status == "pending":
                    out.append(rec)
                elif include_expired and rec.status == "expired":
                    out.append(rec)
            out.sort(key=lambda r: r.created_at, reverse=True)
            return out

    def resolve(
        self,
        pending_id: str,
        *,
        choice_id: str,
        clarify: str = "",
        resolved_by: ResolvedBy = "deck",
        resolve_token: str | None = None,
        allow_missing_token: bool = True,
    ) -> dict[str, Any]:
        """Idempotent resolve. Returns status payload."""
        with self._lock:
            self._expire_unlocked()
            rec = self._records.get(str(pending_id))
            if rec is None:
                return {"ok": False, "reason": "not_found", "pending_id": pending_id}
            if rec.status == "resolved":
                return {
                    "ok": True,
                    "already_resolved": True,
                    "pending_id": rec.pending_id,
                    "resolved_by": rec.resolved_by,
                    "answer": rec.answer,
                    "record": rec.public_dict(),
                }
            if rec.status == "expired":
                return {"ok": False, "reason": "expired", "pending_id": rec.pending_id}
            if resolve_token is not None and str(resolve_token) != rec.resolve_token:
                if not (allow_missing_token and not resolve_token):
                    return {"ok": False, "reason": "invalid_token", "pending_id": rec.pending_id}
            # When token omitted, allow deck/api resolve (admin-authenticated surface).
            if resolve_token is None and not allow_missing_token:
                return {"ok": False, "reason": "token_required", "pending_id": rec.pending_id}

            rec.status = "resolved"
            rec.resolved_by = str(resolved_by)
            rec.resolved_at = _iso()
            rec.answer = {
                "choice_id": str(choice_id).strip().upper(),
                "clarify": str(clarify or "").strip()[:280],
                "resolved_by": str(resolved_by),
                "resolved_at": rec.resolved_at,
            }
            self._records[rec.pending_id] = rec
            self._save()
            return {
                "ok": True,
                "already_resolved": False,
                "pending_id": rec.pending_id,
                "resolved_by": rec.resolved_by,
                "answer": rec.answer,
                "record": rec.public_dict(include_token=False),
                "question": rec.question,
                "kind": rec.kind,
                "context": rec.context,
                "dna_hash": rec.dna_hash,
                "resolve_token": rec.resolve_token,
            }

    def _expire_unlocked(self, *, now: datetime | None = None) -> None:
        now = now or _utcnow()
        dirty = False
        for rec in self._records.values():
            if rec.status != "pending":
                continue
            try:
                exp = datetime.fromisoformat(rec.expires_at)
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
            except ValueError:
                rec.status = "expired"
                dirty = True
                continue
            if now > exp:
                rec.status = "expired"
                dirty = True
        if dirty:
            self._save()
