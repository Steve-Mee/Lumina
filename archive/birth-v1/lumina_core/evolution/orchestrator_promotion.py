"""EvolutionOrchestrator promote-publish / promotion wiring mixin (Wave B PR-B2)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from lumina_core.agent_orchestration import EventBus
from lumina_core.governance import ApprovalChain, RealPromotionPayload

from .dna_registry import PolicyDNA
from .multi_day_sim_runner import MultiDaySimRunner
from .promotion_policy import PromotionPolicy

logger = logging.getLogger(__name__)


class OrchestratorPromotionMixin:
    """Promote-publish / promotion wiring surface for EvolutionOrchestrator."""

    def bind_promotion_event_bus(self, event_bus: EventBus | None) -> None:
        self._promotion_policy = PromotionPolicy(owner=self, logger=logger, event_bus=event_bus)
        # Also wire the ApprovalTwin so it can publish TwinDecisionEvent / TwinTrainingUpdateEvent
        if hasattr(self, "_approval_twin") and hasattr(self._approval_twin, "bind_event_bus"):
            self._approval_twin.bind_event_bus(event_bus)

    def _build_real_promotion_payload(self, *, dna: PolicyDNA, generation_offset: int) -> RealPromotionPayload:
        now = datetime.now(timezone.utc)
        dna_content = dna.content if isinstance(dna.content, dict) else {"raw_content": str(dna.content)}
        return RealPromotionPayload(
            dna_hash=str(dna.hash),
            target_mode="real",
            dna_content_digest=ApprovalChain.dna_content_digest(dna_content),
            promotion_epoch=f"generation:{generation_offset}:{dna.hash}",
            reason_context="evolution_orchestrator_real_promotion",
            created_at=now,
            expires_at=now + timedelta(minutes=30),
        )

    def _send_shadow_status_telegram(self, message: str) -> None:
        self._promotion_policy.send_shadow_status_telegram(message)

    def _send_promotion_status_telegram(self, *, dna_hash: str, promoted: bool, reason: str = "") -> None:
        self._promotion_policy.send_promotion_status_telegram(
            dna_hash=dna_hash,
            promoted=promoted,
            reason=reason,
        )
        if not promoted and reason:
            try:
                from lumina_core.notifications.attention_events import evolution_approval_pending_event
                from lumina_core.notifications.operator_notifier import notify_problem
                from lumina_launcher.core.workspace_root import resolve_birth_workspace_root

                notify_problem(
                    evolution_approval_pending_event(dna_id=dna_hash, detail=reason),
                    workspace_root=resolve_birth_workspace_root(),
                )
            except Exception:
                pass

    def _run_shadow_validation_gate(
        self,
        *,
        dna: PolicyDNA,
        winner_fitness: float,
        nightly_report: dict[str, Any],
        signed: bool,
        generation_ok: bool,
        shadow_runner: MultiDaySimRunner,
    ) -> dict[str, Any]:
        return self._promotion_policy.run_shadow_validation_gate(
            dna=dna,
            winner_fitness=winner_fitness,
            nightly_report=nightly_report,
            signed=signed,
            generation_ok=generation_ok,
            shadow_runner=shadow_runner,
        )

    def _resolve_shadow_day_bounds(self) -> tuple[int, int]:
        return self._promotion_policy.resolve_shadow_day_bounds()

    def _veto_window_for_days(self, days: int) -> Any:
        return self._promotion_policy.veto_window_for_days(days)

    def _load_shadow_runs(self) -> dict[str, Any]:
        return self._promotion_policy.load_shadow_runs()

    def _save_shadow_runs(self, payload: dict[str, Any]) -> None:
        self._promotion_policy.save_shadow_runs(payload)

    def _mark_shadow_promoted(self, *, dna_hash: str) -> None:
        self._promotion_policy.mark_shadow_promoted(dna_hash=dna_hash)


__all__ = ["OrchestratorPromotionMixin"]
