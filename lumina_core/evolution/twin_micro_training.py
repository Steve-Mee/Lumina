"""Ongoing micro-training sessions (daily/weekly) for Approval Twin.

Mix: ApprovalGym synthetic + high-stakes unlabeled decisions + twin↔Steve disagreements.
Dual-channel (app + Telegram). Same MC format as base curriculum.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from lumina_core.evolution.approval_gym import ApprovalGym
from lumina_core.evolution.steve_values_registry import SteveValueRecord
from lumina_core.evolution.twin_curriculum_types import (
    TwinChoice,
    TwinMcQuestion,
    mc_answer_to_steve_fields,
)
from lumina_core.evolution.twin_pending_store import TwinPendingStore
from lumina_core.evolution.twin_question_style import (
    format_micro_live_scenario,
    metrics_hint_from_live,
    standard_avm_choices,
)
from lumina_core.evolution.twin_training_metrics import HIGH_CONF_THRESHOLD, _tail_jsonl


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def proposal_to_mc(
    summary: str,
    dna_hash: str,
    *,
    conf: float = 0.6,
    recommendation: bool | None | str = None,
    risk_flags: list[str] | None = None,
    source_hint: str = "",
) -> TwinMcQuestion:
    """Micro MC in base_v4 style: live bullets + terms + ± choice consequences."""
    scenario = format_micro_live_scenario(
        conf=float(conf),
        recommendation=recommendation,
        risk_flags=risk_flags,
        dna_hash=str(dna_hash),
        summary=summary,
        source_hint=source_hint,
    )
    return TwinMcQuestion(
        question_id=f"micro_{str(dna_hash)[:16]}",
        axis="approve_veto_modify",
        scenario=scenario,
        choices=standard_avm_choices(),
        context_dna_hash=str(dna_hash),
        channel_policy="dual",
        allow_clarify=True,
        estimated_seconds=18,
        metrics_hint=metrics_hint_from_live(
            conf=float(conf),
            risk_flags=risk_flags,
            extra={"source": source_hint or "micro"},
        ),
    )


class TwinMicroTrainingMixin:
    """start_micro_session / submit_micro — dual channel capable."""

    def _micro_pending(self) -> TwinPendingStore:
        store = getattr(self, "pending_store", None)
        if store is None:
            store = TwinPendingStore()
            self.pending_store = store
        return store

    def start_micro_session(
        self,
        *,
        count: int = 3,
        prefer_historical: bool = True,
        dual_channel: bool = True,
        notify_telegram: bool = True,
    ) -> dict[str, Any]:
        target = max(1, min(5, int(count)))
        questions: list[TwinMcQuestion] = []
        sources: list[str] = []

        # 1) High-stakes unlabeled twin decisions
        try:
            decisions_path = getattr(self, "decisions_path", None)
            labeled = set()
            if hasattr(self, "_labeled_dna_hashes"):
                labeled = self._labeled_dna_hashes()  # type: ignore[attr-defined]
            if decisions_path is not None:
                raw = _tail_jsonl(decisions_path, limit=80)
                for item in reversed(raw):
                    if len(questions) >= target:
                        break
                    dna = str(item.get("dna_hash") or "").strip()
                    if not dna or dna in labeled:
                        continue
                    score = item.get("score", item.get("confidence"))
                    try:
                        sc = float(score) if score is not None else 0.5
                    except (TypeError, ValueError):
                        sc = 0.5
                    risks = item.get("risk_flags") or []
                    high = bool(risks) or sc < HIGH_CONF_THRESHOLD
                    if not high:
                        continue
                    rec = item.get("recommendation")
                    explanation = str(
                        item.get("explanation") or item.get("reason") or ""
                    ).strip()
                    summary = explanation or "Eerdere high-stakes Twin-beslissing zonder menslabel."
                    questions.append(
                        proposal_to_mc(
                            summary,
                            dna,
                            conf=sc,
                            recommendation=rec if isinstance(rec, bool) else rec,
                            risk_flags=[str(f) for f in risks[:6]],
                            source_hint="live high-stakes beslissing (nog niet door jou gelabeld)",
                        )
                    )
                    sources.append("high_stakes_decision")
        except Exception:
            pass

        # 2) Gym synthetic / historical fill
        if len(questions) < target:
            gym = ApprovalGym(registry=self.registry)  # type: ignore[attr-defined]
            hist = None
            if prefer_historical and hasattr(self, "_load_historical_dna"):
                try:
                    hist = self._load_historical_dna(limit=12)  # type: ignore[attr-defined]
                except Exception:
                    hist = None
            proposals = gym.generate_proposals(
                historical_dna=hist or None,
                count=target - len(questions),
            )
            for p in proposals:
                if len(questions) >= target:
                    break
                is_synth = str(p.dna_hash).startswith("sim_")
                questions.append(
                    proposal_to_mc(
                        p.summary,
                        p.dna_hash,
                        conf=float(p.estimated_confidence),
                        recommendation=None,
                        risk_flags=None,
                        source_hint=(
                            "synthetische gym-oefening"
                            if is_synth
                            else "historische DNA-candidate"
                        ),
                    )
                )
                sources.append("synthetic" if is_synth else "historical")

        session_id = str(uuid.uuid4())
        pending_ids: list[str] = []
        items: list[dict[str, Any]] = []
        store = self._micro_pending()
        policy = "dual" if dual_channel else "app_only"
        existing_tg = [
            rec for rec in store.list_pending(kind="micro") if rec.channels.get("telegram")
        ]
        telegram_budget = 0 if existing_tg else 1

        for q in questions:
            send_this = bool(dual_channel and notify_telegram and telegram_budget > 0)
            rec = store.create(
                kind="micro",
                question=q.to_dict(),
                channel_policy=policy,
                channels={"deck": True, "telegram": send_this},
                context={"session_id": session_id},
                dna_hash=q.context_dna_hash,
                ttl_sec=86400,
            )
            pending_ids.append(rec.pending_id)
            items.append(
                {
                    "pending_id": rec.pending_id,
                    "question": q.to_dict(),
                    "expires_at": rec.expires_at,
                }
            )
            if send_this:
                try:
                    from lumina_core.notifications.telegram_notifier import TelegramNotifier

                    n = TelegramNotifier()
                    if hasattr(n, "send_twin_mc_question"):
                        n.send_twin_mc_question(
                            pending_id=rec.pending_id,
                            question=q.to_dict(),
                            resolve_token=rec.resolve_token,
                            kind="micro",
                        )
                    telegram_budget -= 1
                except Exception:
                    pass

        return {
            "session_id": session_id,
            "count": len(items),
            "items": items,
            "pending_ids": pending_ids,
            "sources": sources[: len(items)],
            "channel_policy": policy,
            "practice_only": True,
            "local_only": True,
        }

    def submit_micro(
        self,
        *,
        pending_id: str,
        choice_id: str,
        clarify: str = "",
        resolved_by: str = "deck",
        resolve_token: str | None = None,
        train_now: bool = True,
    ) -> dict[str, Any]:
        store = self._micro_pending()
        result = store.resolve(
            pending_id,
            choice_id=choice_id,
            clarify=clarify,
            resolved_by=resolved_by,  # type: ignore[arg-type]
            resolve_token=resolve_token,
            allow_missing_token=True,
        )
        if not result.get("ok"):
            return {**result, "recorded": False}
        if result.get("already_resolved"):
            return {
                "recorded": True,
                "already_resolved": True,
                "pending_id": pending_id,
                "resolved_by": result.get("resolved_by"),
                "local_only": True,
            }

        q_raw = result.get("question") or {}
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
            question_id=str(q_raw.get("question_id") or pending_id),
            axis=str(q_raw.get("axis") or "approve_veto_modify"),  # type: ignore[arg-type]
            scenario=str(q_raw.get("scenario") or ""),
            choices=choices,
            context_dna_hash=str(result.get("dna_hash") or q_raw.get("context_dna_hash") or pending_id),
            channel_policy="dual",
        )
        vraag, antwoord, conf = mc_answer_to_steve_fields(
            question, choice_id=choice_id, clarify=clarify
        )
        record = SteveValueRecord.create(
            vraag=vraag,
            steve_antwoord=antwoord,
            context_dna_hash=question.context_dna_hash,
            confidence_score=conf,
        )
        self.registry.append(record)  # type: ignore[attr-defined]
        rlhf = None
        if train_now and hasattr(self, "twin") and hasattr(self.twin, "rlhf_light_update"):
            rlhf = self.twin.rlhf_light_update(records=[record])  # type: ignore[attr-defined]

        # Journal the answer; no Telegram ACK spam
        try:
            from lumina_core.notifications.telegram_journal import record_reply

            record_reply(
                correlation_id=str(pending_id),
                reply_text=str(choice_id),
                resolved_by=str(resolved_by or "deck"),
                kind="twin_micro",
                source="twin_micro_training.submit",
                question_text=str(q_raw.get("scenario") or ""),
            )
        except Exception:
            pass

        return {
            "recorded": True,
            "already_resolved": False,
            "pending_id": pending_id,
            "label": antwoord,
            "record": asdict(record),
            "rlhf": rlhf,
            "resolved_by": resolved_by,
            "local_only": True,
        }
