"""Approval Twin EventBus publish helpers + observation metrics."""
from __future__ import annotations

from typing import Any

from lumina_core.agent_orchestration.schemas import (
    TwinDecisionEvent,
    TwinModePromotionEvent,
    TwinShadowObservationEvent,
    TwinTrainingUpdateEvent,
)
from lumina_core.evolution.twin_mode_promotion_gate import apply_mode_authority
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.evolution.twin")


class ApprovalTwinBusPublishMixin:
    def _publish_decision(
        self,
        *,
        dna_hash: str,
        recommendation: bool,
        confidence: float,
        risk_flags: list[str],
        explanation: str,
        call: str = "evaluate_dna_promotion",
        executable: bool | None = None,
        authority: str | None = None,
        effective_recommendation: bool | None = None,
    ) -> None:
        """Best-effort publish of TwinDecisionEvent + Telegram operator feed.

        Post-hoc observability only — never a pre-approval gate. Never raises.
        Optional OK|FIX feedback trains Twin after the fact.
        """
        mode = str(getattr(self, "_mode", "") or "")
        # Telegram / local feed first so operator sees decisions even without bus.
        try:
            from lumina_core.evolution.twin_decision_notify import notify_twin_decision

            notify_twin_decision(
                dna_hash=str(dna_hash),
                recommendation=bool(recommendation),
                confidence=float(confidence),
                risk_flags=list(risk_flags or []),
                explanation=str(explanation or ""),
                call=str(call),
                mode=mode,
                notify_telegram=True,
                executable=executable,
                authority=authority,
                effective_recommendation=effective_recommendation,
            )
        except Exception:
            pass

        if self._event_bus is None:
            return
        try:
            payload = TwinDecisionEvent(
                dna_hash=str(dna_hash),
                recommendation=bool(recommendation),
                confidence=float(confidence),
                risk_flags=list(risk_flags or []),
                explanation=str(explanation or ""),
                call=str(call),
            ).model_dump(mode="json")
            if authority is not None:
                payload["authority"] = str(authority)
            if executable is not None:
                payload["executable"] = bool(executable)
            if effective_recommendation is not None:
                payload["effective_recommendation"] = bool(effective_recommendation)
            self._event_bus.publish_validated(
                topic="evolution.twin.decision",
                producer="evolution.approval_twin_agent",
                payload=payload,
            )
        except Exception:
            # Observability only; decisions and training must never be impacted.
            pass

    def _finalize_and_publish_decision(
        self,
        decision: dict[str, Any],
        *,
        dna_hash: str,
        call: str,
    ) -> dict[str, Any]:
        """Apply mode authority, publish post-hoc feed, return authoritative decision."""
        out = self.apply_mode_authority(decision)
        try:
            self._publish_decision(
                dna_hash=str(dna_hash),
                recommendation=bool(out.get("recommendation", decision.get("recommendation"))),
                confidence=float(out.get("confidence", decision.get("confidence") or 0.0)),
                risk_flags=list(out.get("risk_flags") or decision.get("risk_flags") or []),
                explanation=str(out.get("explanation") or decision.get("explanation") or ""),
                call=str(call),
                executable=bool(out.get("executable")) if "executable" in out else None,
                authority=str(out.get("authority") or "") or None,
                effective_recommendation=(
                    bool(out.get("effective_recommendation"))
                    if "effective_recommendation" in out
                    else None
                ),
            )
        except Exception:
            pass
        return out

    def _publish_mode_promotion(
        self,
        *,
        result: dict[str, Any],
        target_mode: str,
    ) -> None:
        """Best-effort publish of TwinModePromotionEvent. Observability only."""
        if self._event_bus is None:
            return
        try:
            decision = result.get("decision") if isinstance(result.get("decision"), dict) else {}
            snap = {}
            try:
                snap = self._metrics_store.snapshot().to_dict()
            except Exception:
                snap = {}
            payload = TwinModePromotionEvent(
                current_mode=str(result.get("previous_mode") or result.get("mode") or self._mode),
                target_mode=str(target_mode or result.get("mode") or self._mode),
                promoted=bool(result.get("promoted", False)),
                fail_reasons=list(result.get("fail_reasons") or decision.get("fail_reasons") or []),
                reason=str(result.get("reason") or decision.get("reason") or ""),
                agreement_pct=float(snap.get("agreement_pct", 0.0) or 0.0),
                false_positive_pct=float(snap.get("false_positive_pct", 100.0) or 100.0),
                samples=int(snap.get("samples", 0) or 0),
            ).model_dump(mode="json")
            # If already at mode or demoted, current_mode is previous; stamp accurately
            if result.get("previous_mode"):
                payload["current_mode"] = str(result["previous_mode"])
            elif not result.get("promoted"):
                payload["current_mode"] = str(result.get("mode") or self._mode)
            self._event_bus.publish_validated(
                topic="evolution.twin.mode_promotion",
                producer="evolution.approval_twin_agent",
                payload=payload,
            )
        except Exception:
            pass

    def _publish_shadow_observation(
        self,
        *,
        dna_hash: str,
        source_topic: str,
        twin_recommendation: bool,
        observed_allowed_or_pass: bool,
        agreed: bool,
        confidence: float,
        risk_flags: list[str],
        explanation: str,
    ) -> None:
        if self._event_bus is None:
            return
        try:
            payload = TwinShadowObservationEvent(
                dna_hash=str(dna_hash or ""),
                source_topic=str(source_topic),
                twin_recommendation=bool(twin_recommendation),
                observed_allowed_or_pass=bool(observed_allowed_or_pass),
                agreed=bool(agreed),
                confidence=float(max(0.0, min(1.0, confidence))),
                risk_flags=list(risk_flags or []),
                explanation=str(explanation or ""),
            ).model_dump(mode="json")
            self._event_bus.publish_validated(
                topic="evolution.twin.shadow_observation",
                producer="evolution.approval_twin_agent",
                payload=payload,
            )
        except Exception:
            pass

    def _publish_training_update(self, *, result: dict[str, Any], records_len: int) -> None:
        """Best-effort publish of TwinTrainingUpdateEvent after RLHF/fine-tune."""
        if self._event_bus is None:
            return
        try:
            payload = TwinTrainingUpdateEvent(
                records_processed=int(records_len),
                updates=int(result.get("updates", 0) or 0),
                avg_prediction_error=float(result.get("avg_prediction_error", 0.0) or 0.0),
                reward=float(result.get("reward", 0.0) or 0.0),
                training_steps=int(result.get("training_steps", 0) or 0),
            ).model_dump(mode="json")
            self._event_bus.publish_validated(
                topic="evolution.twin.training_update",
                producer="evolution.approval_twin_agent",
                payload=payload,
            )
        except Exception:
            pass

    def observation_metrics(self) -> dict[str, Any]:
        """In-memory shadow-observe counters for CLI / dashboards."""
        total = max(0, int(self.observations_total))
        agrees = max(0, int(self.agreements))
        durable = {}
        try:
            durable = self._metrics_store.metrics_dict()
        except Exception:
            durable = {}
        return {
            "mode": self._mode,
            "authority": apply_mode_authority(
                raw_recommendation=True, mode=self._mode
            ).get("authority"),
            "observations_total": total,
            "agreements": agrees,
            "disagreements": max(0, int(self.disagreements)),
            "agreement_pct": round((agrees / total) * 100.0, 2) if total else 0.0,
            "durable_metrics": durable,
        }
