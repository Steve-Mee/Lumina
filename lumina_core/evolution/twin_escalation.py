"""Doubt escalation protocol for Approval Twin (ADR-0037).

When calibrated confidence is low, entropy is high, or pattern is novel:
Twin does NOT decide — creates TwinEscalationRecord, dual-channel push,
human answer → SteveValueRecord + online RLHF.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.evolution.steve_values_registry import SteveValueRecord
from lumina_core.evolution.twin_curriculum_types import (
    DEFAULT_ESCALATION_TTL_SEC,
    HIGH_CONF_THRESHOLD,
    TwinChoice,
    TwinMcQuestion,
    mc_answer_to_steve_fields,
)
from lumina_core.evolution.twin_pending_store import TwinPendingStore
from lumina_core.evolution.twin_question_style import (
    format_escalation_live_scenario,
    metrics_hint_from_live,
    standard_avm_choices,
)

logger = logging.getLogger(__name__)

_DEFAULT_ESCALATION_LOG = Path("state/monitoring_twin_escalations.jsonl")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def detect_doubt(
    *,
    confidence: float,
    risk_flags: list[str] | None = None,
    dna_hash: str = "",
    labeled_hashes: set[str] | None = None,
    high_conf_threshold: float = HIGH_CONF_THRESHOLD,
    near_threshold_band: float = 0.08,
) -> list[str]:
    """Return list of doubt_reasons (empty = no doubt)."""
    reasons: list[str] = []
    conf = float(confidence)
    thr = float(high_conf_threshold)
    if conf < thr:
        reasons.append("low_conf")
    flags = [str(f) for f in (risk_flags or []) if str(f).strip()]
    if flags and conf < thr + near_threshold_band:
        reasons.append("conflicting_risk_flags")
    labeled = labeled_hashes or set()
    dna = str(dna_hash or "").strip()
    if dna and labeled and dna not in labeled and not dna.startswith("curriculum_"):
        reasons.append("novel_pattern")
    if flags:
        # Unseen-ish soft flags often deserve human eyes
        novelish = {"correlated_instruments", "overnight", "black_swan", "low_liquidity"}
        if any(f in novelish or "novel" in f.lower() for f in flags):
            if "novel_pattern" not in reasons:
                reasons.append("unseen_risk_flags")
    return reasons


def build_escalation_question(
    *,
    dna_hash: str,
    confidence: float,
    risk_flags: list[str] | None,
    explanation: str = "",
    twin_recommendation: bool | None = None,
    doubt_reasons: list[str] | None = None,
) -> TwinMcQuestion:
    """Forced-choice question for human resolution of twin doubt (base_v4 clarity)."""
    flags = list(risk_flags or [])
    scenario = format_escalation_live_scenario(
        conf=float(confidence),
        recommendation=twin_recommendation,
        risk_flags=flags,
        dna_hash=str(dna_hash or ""),
        explanation=explanation,
        doubt_reasons=doubt_reasons,
    )
    return TwinMcQuestion(
        question_id=f"esc_{dna_hash[:12] or 'unknown'}",
        axis="approve_veto_modify",
        scenario=scenario,
        choices=standard_avm_choices(
            approve_plus="Besluit valt; Twin leert dat dit pad ok is bij deze twijfel",
            approve_minus="Als het toch fout was, loopt de loop door met jouw zegen",
            veto_plus="Pad geblokkeerd tot er iets verandert — fail-closed",
            veto_minus="Geen vooruitgang op dit DNA tot een nieuw voorstel",
            modify_plus="Door met strengere voorwaarden / kleinere scope",
            modify_minus="Extra ronde werk; trager dan pure APPROVE",
        ),
        context_dna_hash=str(dna_hash or "escalation_unknown"),
        channel_policy="dual",
        allow_clarify=True,
        estimated_seconds=20,
        metrics_hint=metrics_hint_from_live(
            conf=float(confidence),
            risk_flags=flags,
            extra={"kind": "escalation"},
        ),
    )


class TwinEscalationMixin:
    """create/resolve escalations; dual-channel via TwinPendingStore."""

    pending_store: TwinPendingStore | None = None
    escalation_log_path: Path = _DEFAULT_ESCALATION_LOG

    def _pending(self) -> TwinPendingStore:
        store = getattr(self, "pending_store", None)
        if store is None:
            store = TwinPendingStore()
            self.pending_store = store
        return store

    def _labeled_hashes_for_doubt(self) -> set[str]:
        try:
            records = self.registry.list_recent(limit=2000)  # type: ignore[attr-defined]
            return {
                str(r.context_dna_hash).strip()
                for r in records
                if str(getattr(r, "context_dna_hash", "") or "").strip()
            }
        except Exception:
            return set()

    def should_escalate_decision(
        self,
        *,
        confidence: float,
        risk_flags: list[str] | None = None,
        dna_hash: str = "",
    ) -> tuple[bool, list[str]]:
        reasons = detect_doubt(
            confidence=confidence,
            risk_flags=risk_flags,
            dna_hash=dna_hash,
            labeled_hashes=self._labeled_hashes_for_doubt(),
        )
        return (len(reasons) > 0, reasons)

    def create_escalation(
        self,
        *,
        dna_hash: str,
        confidence: float,
        risk_flags: list[str] | None = None,
        explanation: str = "",
        twin_recommendation: bool | None = None,
        features: dict[str, Any] | None = None,
        doubt_reasons: list[str] | None = None,
        ttl_sec: int = DEFAULT_ESCALATION_TTL_SEC,
        notify_telegram: bool = True,
    ) -> dict[str, Any]:
        dna = str(dna_hash or "").strip() or "unknown"
        existing = self._pending().find_open(kind="escalation", dna_hash=dna)
        if existing is not None:
            return {
                "created": False,
                "deduped": True,
                "escalation_id": existing.pending_id,
                "status": existing.status,
                "doubt_reasons": list(doubt_reasons or []),
                "question": dict(existing.question),
                "channels": dict(existing.channels),
                "telegram_sent": False,
                "expires_at": existing.expires_at,
                "dna_hash": dna,
                "local_only": True,
                "resolve_token": existing.resolve_token,
            }
        reasons = list(doubt_reasons or [])
        if not reasons:
            _, reasons = self.should_escalate_decision(
                confidence=confidence, risk_flags=risk_flags, dna_hash=dna
            )
        question = build_escalation_question(
            dna_hash=dna,
            confidence=float(confidence),
            risk_flags=list(risk_flags or []),
            explanation=explanation,
            twin_recommendation=twin_recommendation,
            doubt_reasons=reasons,
        )
        context = {
            "twin_internal": {
                "confidence": float(confidence),
                "risk_flags": list(risk_flags or []),
                "doubt_reasons": reasons,
                "twin_recommendation": twin_recommendation,
                "explanation": str(explanation or "")[:400],
            },
            "features": dict(features or {}),
            "frozen_decision": True,
        }
        rec = self._pending().create(
            kind="escalation",
            question=question.to_dict(),
            channel_policy="dual",
            channels={"deck": True, "telegram": bool(notify_telegram)},
            context=context,
            dna_hash=dna,
            ttl_sec=ttl_sec,
        )
        self._append_escalation_log(
            {
                "event": "twin.escalation.created",
                "escalation_id": rec.pending_id,
                "dna_hash": dna,
                "confidence": float(confidence),
                "doubt_reasons": reasons,
                "status": "pending",
                "timestamp": _utcnow(),
            }
        )
        self._publish_escalation_event(
            escalation_id=rec.pending_id,
            dna_hash=dna,
            status="pending",
            confidence=float(confidence),
            doubt_reasons=reasons,
        )
        telegram_sent = False
        if notify_telegram:
            telegram_sent = self._notify_telegram_escalation(rec.pending_id, question.to_dict(), rec.resolve_token)

        return {
            "created": True,
            "escalation_id": rec.pending_id,
            "status": "pending",
            "doubt_reasons": reasons,
            "question": question.to_dict(),
            "channels": rec.channels,
            "telegram_sent": telegram_sent,
            "expires_at": rec.expires_at,
            "dna_hash": dna,
            "local_only": True,
            # Token only for internal/system use — API public list strips it
            "resolve_token": rec.resolve_token,
        }

    def list_pending_escalations(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for rec in self._pending().list_pending(kind="escalation"):
            d = rec.public_dict(include_token=False)
            d["escalation_id"] = rec.pending_id
            out.append(d)
        return out

    def resolve_escalation(
        self,
        escalation_id: str,
        *,
        choice_id: str,
        clarify: str = "",
        resolved_by: str = "deck",
        resolve_token: str | None = None,
        train_now: bool = True,
    ) -> dict[str, Any]:
        result = self._pending().resolve(
            escalation_id,
            choice_id=choice_id,
            clarify=clarify,
            resolved_by=resolved_by,  # type: ignore[arg-type]
            resolve_token=resolve_token,
            allow_missing_token=True,
        )
        if not result.get("ok"):
            return {**result, "resolved": False}

        if result.get("already_resolved"):
            return {
                "resolved": True,
                "already_resolved": True,
                "escalation_id": escalation_id,
                "resolved_by": result.get("resolved_by"),
                "answer": result.get("answer"),
                "local_only": True,
            }

        # Build Steve label from MC question payload
        q_raw = result.get("question") or {}
        try:
            choices = tuple(
                TwinChoice(
                    id=str(c.get("id")),
                    label=str(c.get("label")),
                    value_signal=str(c.get("value_signal")),  # type: ignore[arg-type]
                )
                for c in (q_raw.get("choices") or [])
                if isinstance(c, dict)
            )
            question = TwinMcQuestion(
                question_id=str(q_raw.get("question_id") or escalation_id),
                axis=str(q_raw.get("axis") or "approve_veto_modify"),  # type: ignore[arg-type]
                scenario=str(q_raw.get("scenario") or ""),
                choices=choices,
                context_dna_hash=str(
                    result.get("dna_hash") or q_raw.get("context_dna_hash") or escalation_id
                ),
                channel_policy="dual",
            )
            vraag, antwoord, conf = mc_answer_to_steve_fields(
                question, choice_id=str(choice_id), clarify=clarify
            )
        except Exception as exc:
            logger.warning("escalation label build failed: %s", exc)
            vraag = f"escalation {escalation_id}"
            antwoord = f"MODIFY: choice={choice_id}"
            conf = 0.45

        record = SteveValueRecord.create(
            vraag=vraag,
            steve_antwoord=antwoord,
            context_dna_hash=str(result.get("dna_hash") or escalation_id),
            confidence_score=conf,
        )
        self.registry.append(record)  # type: ignore[attr-defined]

        rlhf = None
        if train_now and hasattr(self, "twin") and hasattr(self.twin, "rlhf_light_update"):
            rlhf = self.twin.rlhf_light_update(records=[record])  # type: ignore[attr-defined]

        from lumina_core.evolution.approval_twin_scoring import ApprovalTwinScoringMixin

        label_score = ApprovalTwinScoringMixin._label_from_answer(antwoord)
        steve_approve = label_score is not None and label_score >= 0.6
        if hasattr(self, "twin") and hasattr(self.twin, "record_steve_label_comparison"):
            try:
                self.twin.record_steve_label_comparison(  # type: ignore[attr-defined]
                    twin_recommendation=None,
                    steve_approve=steve_approve,
                    dna_hash=str(result.get("dna_hash") or ""),
                    steve_label=antwoord[:64],
                )
            except Exception:
                pass

        self._append_escalation_log(
            {
                "event": "twin.escalation.resolved",
                "escalation_id": escalation_id,
                "dna_hash": result.get("dna_hash"),
                "status": "resolved",
                "resolved_by": resolved_by,
                "choice_id": str(choice_id).upper(),
                "label": antwoord,
                "timestamp": _utcnow(),
            }
        )
        self._publish_escalation_event(
            escalation_id=escalation_id,
            dna_hash=str(result.get("dna_hash") or ""),
            status="resolved",
            confidence=conf,
            doubt_reasons=[],
            channel=str(resolved_by),
        )

        # Cross-channel resolution notice (journal only — no Telegram ACK spam)
        try:
            from lumina_core.notifications.telegram_journal import record_reply

            record_reply(
                correlation_id=str(escalation_id),
                reply_text=f"{choice_id}" + (f" — {antwoord}" if antwoord else ""),
                resolved_by=str(resolved_by or "deck"),
                kind="twin_escalation",
                source="twin_escalation.resolve",
                question_text=str((result.get("question") or {}).get("scenario") or vraag),
            )
        except Exception:
            logger.debug("escalation reply journal failed", exc_info=True)

        return {
            "resolved": True,
            "already_resolved": False,
            "escalation_id": escalation_id,
            "resolved_by": resolved_by,
            "label": antwoord,
            "record": asdict(record),
            "rlhf": rlhf,
            "decision_unblocked": True,
            "steve_approve": steve_approve,
            "local_only": True,
        }

    def _append_escalation_log(self, payload: dict[str, Any]) -> None:
        path = Path(getattr(self, "escalation_log_path", _DEFAULT_ESCALATION_LOG))
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except OSError:
            logger.debug("escalation log write failed", exc_info=True)

    def _publish_escalation_event(
        self,
        *,
        escalation_id: str,
        dna_hash: str,
        status: str,
        confidence: float,
        doubt_reasons: list[str],
        channel: str = "",
    ) -> None:
        twin = getattr(self, "twin", None)
        bus = getattr(twin, "_event_bus", None) if twin is not None else None
        if bus is None:
            return
        try:
            from lumina_core.agent_orchestration.schemas_evolution import TwinEscalationEvent

            evt = TwinEscalationEvent(
                escalation_id=escalation_id,
                dna_hash=dna_hash,
                status=status,
                confidence=float(confidence),
                doubt_reasons=list(doubt_reasons),
                channel=channel,
            )
            bus.publish("evolution.twin.escalation", evt)
        except Exception:
            logger.debug("twin escalation bus publish failed", exc_info=True)

    def _notify_telegram_escalation(
        self, escalation_id: str, question: dict[str, Any], resolve_token: str
    ) -> bool:
        try:
            from lumina_core.notifications.telegram_notifier import TelegramNotifier

            notifier = TelegramNotifier()
            if hasattr(notifier, "send_twin_mc_question"):
                return bool(
                    notifier.send_twin_mc_question(
                        pending_id=escalation_id,
                        question=question,
                        resolve_token=resolve_token,
                        kind="escalation",
                    )
                )
            # Fallback: plain text if method not yet present
            scenario = str(question.get("scenario") or "")[:500]
            lines = [
                f"LUMINA Twin escalatie [{escalation_id[:8]}]",
                scenario,
            ]
            for c in question.get("choices") or []:
                if isinstance(c, dict):
                    lines.append(f"{c.get('id')}: {c.get('label')}")
            lines.append(f"Antwoord: A|B|C|D + token {resolve_token[:8]}…")
            if hasattr(notifier, "send_message"):
                return bool(notifier.send_message("\n".join(lines)))
        except Exception:
            logger.debug("telegram escalation notify failed", exc_info=True)
        return False
