"""Twin decision operator feed — journal every judgment; Telegram is opt-in.

Elon rules: Telegram is for human decisions, not Twin diary (ADR-0043).
Post-hoc judgments always land in the Telegram I/O journal; phone push only
when decision_notify.telegram is true (default false). Optional OK|FIX trains Twin.

Message shape (base_v4 / NL operator voice — see twin_telegram_copy):
  Situatie · Twin-oordeel · Zekerheid · Waarom · Feedback OK|A|B|C
"""

from __future__ import annotations

import json
import logging
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from lumina_core.config_loader import ConfigLoader
from lumina_core.evolution.twin_telegram_copy import (
    format_decision_telegram_message as _format_decision_telegram_message_v2,
    humanize_call,
    humanize_explanation,
    short_dna,
)

logger = logging.getLogger(__name__)

_DEFAULT_PENDING = Path("state/twin_decision_notify_pending.json")
_DEFAULT_AUDIT = Path("state/monitoring_twin_decision_notify.jsonl")
_FEEDBACK_TTL_SEC = 86400
_COALESCE_SAME_DNA_SEC = 45

# Module-level throttle (process-local)
_last_sent_mono: float = 0.0
_last_dna_key: str = ""
_last_dna_mono: float = 0.0
_lock = threading.RLock()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cfg() -> dict[str, Any]:
    twin = ConfigLoader.section("evolution", "approval_twin", default={}) or {}
    if not isinstance(twin, dict):
        return {}
    n = twin.get("decision_notify")
    return n if isinstance(n, dict) else {}


def format_twin_answer(*, recommendation: bool, confidence: float) -> str:
    verb = "GOEDKEUREN (APPROVE)" if recommendation else "AFKEUREN (VETO)"
    c = float(confidence)
    pct = int(round(c * 100)) if c <= 1.5 else int(round(c))
    return f"{verb} · zekerheid {pct}%"


def build_lumina_question(
    *,
    dna_hash: str,
    call: str,
    explanation: str,
    risk_flags: list[str] | None = None,
) -> str:
    """What Lumina asked the Twin to judge — plain operator language (audit + legacy)."""
    parts = [
        humanize_call(call),
        f"DNA: {short_dna(dna_hash)}",
    ]
    flags = [str(f) for f in (risk_flags or []) if str(f).strip()]
    if flags:
        from lumina_core.evolution.twin_question_style import _flags_nl

        parts.append(f"Risico-signalen: {_flags_nl(flags)}")
    expl = humanize_explanation(explanation)
    if expl:
        parts.append(f"Context: {expl}")
    return "\n".join(parts)


def build_why_text(
    *,
    explanation: str,
    confidence: float,
    risk_flags: list[str] | None,
    mode: str,
    recommendation: bool,
) -> str:
    """Plain-language why (stored for audit; Telegram uses twin_telegram_copy)."""
    c = float(confidence)
    pct = int(round(c * 100)) if c <= 1.5 else int(round(c))
    lean = "goedkeuren" if recommendation else "afkeuren"
    bits = [
        f"Twin neigt tot {lean} met {pct}% zekerheid"
        + (f" (modus {mode})" if mode else "")
        + ".",
    ]
    expl = humanize_explanation(explanation)
    if expl:
        bits.append(expl)
    else:
        bits.append(
            "Score lag op of boven de drempel."
            if recommendation
            else "Score lag onder de drempel of er waren risico-signalen (fail-closed)."
        )
    flags = [str(f) for f in (risk_flags or []) if str(f).strip()]
    if flags:
        from lumina_core.evolution.twin_question_style import _flags_nl

        bits.append(f"Risico-signalen: {_flags_nl(flags)}")
    return "\n".join(bits)


def format_execution_status(payload: dict[str, Any]) -> str:
    """Post-hoc status line (plain NL)."""
    exe = payload.get("executable")
    if exe is True:
        return (
            "Dit is nátijden: de Twin heeft al geoordeeld en Lumina heeft dat "
            "verwerkt. Jouw feedback leert de Twin voor later."
        )
    if exe is False:
        return (
            "Dit is nátijden: de Twin heeft geoordeeld maar dit was géén sole-auto "
            "uitvoering. Geen spoed-goedkeuring nodig — optionele bijsturing mag wel."
        )
    return (
        "Dit is nátijden: Twin-oordeel vastgelegd. Telegram is zichtbaarheid + "
        "optionele feedback, geen vooraf-goedkeuring."
    )


def format_decision_telegram_message(payload: dict[str, Any]) -> str:
    """Operator-facing Telegram body (base_v4 / twin_telegram_copy)."""
    return _format_decision_telegram_message_v2(payload)


class TwinDecisionNotifyStore:
    """Pending decision feedback records (local JSON)."""

    def __init__(self, path: Path | str = _DEFAULT_PENDING) -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._records: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._records = {}
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            items = raw.get("records") if isinstance(raw, dict) else {}
            if isinstance(items, dict):
                self._records = {str(k): dict(v) for k, v in items.items() if isinstance(v, dict)}
            elif isinstance(items, list):
                out: dict[str, dict[str, Any]] = {}
                for row in items:
                    if isinstance(row, dict) and row.get("decision_id"):
                        out[str(row["decision_id"])] = row
                self._records = out
            else:
                self._records = {}
        except (OSError, json.JSONDecodeError, TypeError):
            self._records = {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"updated_at": _utcnow(), "records": self._records}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)

    def put(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._expire_unlocked()
            did = str(record.get("decision_id") or secrets.token_urlsafe(8))
            record = {**record, "decision_id": did}
            self._records[did] = record
            # Cap memory
            if len(self._records) > 200:
                ordered = sorted(
                    self._records.items(),
                    key=lambda kv: str(kv[1].get("created_at") or ""),
                )
                for k, _ in ordered[: len(self._records) - 200]:
                    self._records.pop(k, None)
            self._save()
            return record

    def get(self, decision_id: str) -> dict[str, Any] | None:
        with self._lock:
            self._expire_unlocked()
            # prefix match
            did = str(decision_id or "").strip()
            if did in self._records:
                return dict(self._records[did])
            for k, v in self._records.items():
                if k.startswith(did) or did.startswith(k[:8]):
                    return dict(v)
            return None

    def list_recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            self._expire_unlocked()
            rows = list(self._records.values())
            rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
            return [dict(r) for r in rows[: max(1, int(limit))]]

    def mark_feedback(self, decision_id: str, feedback: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            rec = self.get(decision_id)
            if rec is None:
                return {"ok": False, "reason": "not_found"}
            did = str(rec["decision_id"])
            if rec.get("feedback"):
                return {
                    "ok": True,
                    "already_feedback": True,
                    "record": rec,
                }
            rec["feedback"] = feedback
            rec["feedback_at"] = _utcnow()
            self._records[did] = rec
            self._save()
            return {"ok": True, "already_feedback": False, "record": rec}

    def _expire_unlocked(self) -> None:
        now = datetime.now(timezone.utc)
        dirty = False
        for did, rec in list(self._records.items()):
            try:
                exp = datetime.fromisoformat(str(rec.get("expires_at") or ""))
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if now > exp and not rec.get("feedback"):
                    rec["status"] = "expired"
                    self._records[did] = rec
                    dirty = True
            except ValueError:
                continue
        if dirty:
            self._save()


_STORE: TwinDecisionNotifyStore | None = None


def get_decision_notify_store() -> TwinDecisionNotifyStore:
    global _STORE
    if _STORE is None:
        _STORE = TwinDecisionNotifyStore()
    return _STORE


def should_send_now(
    *,
    dna_hash: str,
    recommendation: bool,
    confidence: float,
    risk_flags: list[str] | None,
) -> bool:
    """Throttle spam without dropping high-stakes decisions."""
    global _last_sent_mono, _last_dna_key, _last_dna_mono
    cfg = _cfg()
    if cfg.get("enabled", True) is False:
        return False
    if cfg.get("telegram", False) is False:
        return False

    min_interval = float(cfg.get("min_interval_sec", 0) or 0)
    coalesce = float(cfg.get("coalesce_same_dna_sec", _COALESCE_SAME_DNA_SEC) or 0)
    force_low = bool(cfg.get("force_low_conf", False))
    force = False
    if force_low:
        force = (
            float(confidence) < 0.80
            or bool(risk_flags)
            or not bool(recommendation)
        )
    now = time.monotonic()
    dna_key = f"{dna_hash}:{int(bool(recommendation))}"
    with _lock:
        if coalesce > 0 and dna_key == _last_dna_key and (now - _last_dna_mono) < coalesce:
            if not force:
                return False
        if min_interval > 0 and (now - _last_sent_mono) < min_interval and not force:
            return False
        return True


def mark_sent(*, dna_hash: str, recommendation: bool) -> None:
    global _last_sent_mono, _last_dna_key, _last_dna_mono
    with _lock:
        _last_sent_mono = time.monotonic()
        _last_dna_key = f"{dna_hash}:{int(bool(recommendation))}"
        _last_dna_mono = _last_sent_mono


def notify_twin_decision(
    *,
    dna_hash: str,
    recommendation: bool,
    confidence: float,
    risk_flags: list[str] | None = None,
    explanation: str = "",
    call: str = "evaluate_dna_promotion",
    mode: str = "",
    notify_telegram: bool = True,
    executable: bool | None = None,
    authority: str | None = None,
    effective_recommendation: bool | None = None,
) -> dict[str, Any]:
    """Record + Telegram push for one Twin judgment. Best-effort, never raises.

    Not a pre-approval gate: judgment already exists; this is post-hoc audit + optional FIX.
    """
    try:
        cfg = _cfg()
        if cfg.get("enabled", True) is False:
            return {"sent": False, "reason": "disabled"}

        decision_id = secrets.token_urlsafe(9)
        question = build_lumina_question(
            dna_hash=dna_hash,
            call=call,
            explanation=explanation,
            risk_flags=risk_flags,
        )
        answer = format_twin_answer(recommendation=recommendation, confidence=confidence)
        why = build_why_text(
            explanation=explanation,
            confidence=confidence,
            risk_flags=risk_flags,
            mode=mode,
            recommendation=recommendation,
        )
        expires = datetime.now(timezone.utc) + timedelta(seconds=_FEEDBACK_TTL_SEC)
        record = {
            "decision_id": decision_id,
            "created_at": _utcnow(),
            "expires_at": expires.isoformat(),
            "status": "notified",
            "dna_hash": str(dna_hash or ""),
            "recommendation": bool(recommendation),
            "confidence": float(confidence),
            "risk_flags": list(risk_flags or []),
            "explanation": str(explanation or "")[:800],
            "call": str(call or ""),
            "mode": str(mode or ""),
            "executable": executable,
            "authority": authority,
            "effective_recommendation": effective_recommendation,
            "lumina_question": question,
            "twin_answer": answer,
            "why": why,
            "feedback": None,
            "post_hoc_only": True,
        }
        store = get_decision_notify_store()
        stored = store.put(record)
        msg = format_decision_telegram_message(stored)

        want_telegram = bool(notify_telegram) and bool(cfg.get("telegram", False))
        sent = False
        if want_telegram and should_send_now(
            dna_hash=dna_hash,
            recommendation=recommendation,
            confidence=confidence,
            risk_flags=risk_flags,
        ):
            try:
                from lumina_core.notifications.telegram_notifier import TelegramNotifier

                tg = TelegramNotifier()
                sent = bool(
                    tg.send_message(
                        msg,
                        kind="twin_decision",
                        correlation_id=decision_id,
                        expects_reply=True,
                        source="twin_decision_notify",
                    )
                )
            except Exception:
                logger.debug("twin decision telegram send failed", exc_info=True)
        else:
            drop_reason = "throttled" if want_telegram else "policy_shadow_diary"
            try:
                from lumina_core.notifications.telegram_journal import record_outbound

                record_outbound(
                    text=msg,
                    kind="twin_decision",
                    correlation_id=decision_id,
                    expects_reply=True,
                    source="twin_decision_notify",
                    delivered=False,
                    drop_reason=drop_reason,
                )
            except Exception:
                logger.debug("twin decision journal failed", exc_info=True)

        mark_sent(dna_hash=dna_hash, recommendation=recommendation)
        _append_audit(
            {
                "event": "twin.decision_notified",
                "decision_id": decision_id,
                "dna_hash": dna_hash,
                "recommendation": recommendation,
                "confidence": confidence,
                "telegram_sent": sent,
                "timestamp": _utcnow(),
            }
        )
        return {
            "sent": sent,
            "decision_id": decision_id,
            "record": stored,
            "local_only": True,
        }
    except Exception:
        logger.debug("notify_twin_decision failed", exc_info=True)
        return {"sent": False, "reason": "error"}


def apply_decision_feedback(
    decision_id: str,
    *,
    action: str,
    notes: str = "",
    resolved_by: str = "telegram",
    train_now: bool = True,
) -> dict[str, Any]:
    """OK = confirm Twin; FIX A/V/M = correct label + RLHF."""
    store = get_decision_notify_store()
    rec = store.get(decision_id)
    if rec is None:
        return {"ok": False, "reason": "not_found"}

    act = str(action or "").strip().upper()
    # Normalize
    if act in {"OK", "CORRECT", "AGREE", "YES"}:
        feedback_kind = "confirm"
        decision_kind = "approve" if rec.get("recommendation") else "reject"
    elif act in {"A", "APPROVE", "FIX_A", "FIXA"}:
        feedback_kind = "fix"
        decision_kind = "approve"
    elif act in {"V", "VETO", "REJECT", "FIX_V", "FIXV", "N", "NO"}:
        feedback_kind = "fix"
        decision_kind = "reject"
    elif act in {"M", "MODIFY", "FIX_M", "FIXM"}:
        feedback_kind = "fix"
        decision_kind = "modify"
    else:
        return {"ok": False, "reason": f"invalid_action:{action}"}

    note = str(notes or "").strip()[:280]
    if feedback_kind == "confirm":
        note = note or "operator_confirmed_twin"
    elif note:
        note = f"operator_fix:{note}"
    else:
        note = f"operator_fix_{decision_kind}"

    fb = {
        "action": act,
        "feedback_kind": feedback_kind,
        "decision_kind": decision_kind,
        "notes": note,
        "resolved_by": resolved_by,
    }
    marked = store.mark_feedback(str(rec["decision_id"]), fb)
    if not marked.get("ok"):
        return marked
    if marked.get("already_feedback"):
        return {**marked, "trained": False}

    # Ground truth → registry + light RLHF
    trained = None
    try:
        from lumina_core.evolution.twin_training_service import TwinTrainingService

        svc = TwinTrainingService()
        trained = svc.record_decision(
            decision=decision_kind,  # type: ignore[arg-type]
            dna_hash=str(rec.get("dna_hash") or rec["decision_id"]),
            notes=note,
            twin_score=float(rec.get("confidence") or 0.0),
            twin_recommendation=bool(rec.get("recommendation")),
            explanation=str(rec.get("explanation") or ""),
            risk_flags=list(rec.get("risk_flags") or []),
            train_now=train_now,
        )
    except Exception as exc:
        logger.warning("decision feedback train failed: %s", exc)
        return {
            "ok": True,
            "feedback": fb,
            "trained": False,
            "train_error": str(exc),
            "decision_id": rec["decision_id"],
        }

    _append_audit(
        {
            "event": "twin.decision_feedback",
            "decision_id": rec["decision_id"],
            "feedback": fb,
            "timestamp": _utcnow(),
        }
    )
    try:
        from lumina_core.notifications.telegram_journal import record_reply

        did = str(rec["decision_id"])
        record_reply(
            correlation_id=did,
            reply_text=str(act),
            resolved_by=str(resolved_by or "telegram"),
            kind="twin_decision",
            source="twin_decision_notify.apply_feedback",
            question_text=str(rec.get("lumina_question") or rec.get("twin_answer") or ""),
        )
    except Exception:
        logger.debug("twin decision reply journal failed", exc_info=True)

    return {
        "ok": True,
        "feedback": fb,
        "trained": True,
        "result": trained,
        "decision_id": rec["decision_id"],
        "local_only": True,
    }


def parse_decision_feedback_text(raw_text: str) -> dict[str, Any] | None:
    """Parse OK|FIX A/V/M|A/B/C + decision id (+ optional note).

    base_v4: A = had approve, B = had veto, C = modify.
    Legacy FIX A|V|M remains valid.
    """
    text = str(raw_text or "").strip()
    if not text:
        return None
    parts = text.split()
    if not parts:
        return None
    head = parts[0].upper().replace("-", "_")

    # OK <id>
    if head in {"OK", "CORRECT", "AGREE", "EENS"} and len(parts) >= 2:
        return {"action": "OK", "decision_id": parts[1], "notes": " ".join(parts[2:])}

    # base_v4 short: A|B|C <id> [notes]
    if head in {"A", "B", "C"} and len(parts) >= 2:
        letter = "A" if head == "A" else ("V" if head == "B" else "M")
        return {
            "action": f"FIX_{letter}",
            "decision_id": parts[1],
            "notes": " ".join(parts[2:]),
        }

    # FIX A|V|M <id> [notes]
    if head == "FIX" and len(parts) >= 3:
        letter = parts[1].upper()[:1]
        if letter in {"A", "V", "M", "B"}:
            if letter == "B":
                letter = "V"
            return {
                "action": f"FIX_{letter}",
                "decision_id": parts[2],
                "notes": " ".join(parts[3:]),
            }

    # FIXA / FIX_V style
    if head.startswith("FIX") and len(parts) >= 2:
        letter = head.replace("FIX", "").replace("_", "")[:1]
        if letter in {"A", "V", "M", "B"}:
            if letter == "B":
                letter = "V"
            return {
                "action": f"FIX_{letter}",
                "decision_id": parts[1],
                "notes": " ".join(parts[2:]),
            }

    # TD OK <id> / TD FIX A <id>
    if head == "TD" and len(parts) >= 3:
        sub = parts[1].upper()
        if sub in {"OK", "CORRECT", "EENS"}:
            return {"action": "OK", "decision_id": parts[2], "notes": " ".join(parts[3:])}
        if sub == "FIX" and len(parts) >= 4:
            letter = parts[2].upper()[:1]
            if letter in {"A", "V", "M", "B"}:
                if letter == "B":
                    letter = "V"
                return {
                    "action": f"FIX_{letter}",
                    "decision_id": parts[3],
                    "notes": " ".join(parts[4:]),
                }
    return None


def _append_audit(payload: dict[str, Any]) -> None:
    path = _DEFAULT_AUDIT
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except OSError:
        pass
