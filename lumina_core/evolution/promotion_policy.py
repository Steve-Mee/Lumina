from __future__ import annotations

import logging
from typing import Any, Protocol

from lumina_core.config_loader import ConfigLoader
from lumina_core.agent_orchestration.event_bus import ConstitutionViolation, EventBus

from .approval_twin_agent import ApprovalTwinAgent
from .fitness_evaluator import utcnow
from .promotion_gate import PromotionGateDecision
from .shadow_run_storage import load_shadow_runs, save_shadow_runs
from .veto_window import VetoWindow

# === Phase 2 Deliverable 5 (Aperture Hardening) — Integration Hook ===
# When a DNA/proposal change touches risk logic (policy, limits, gates, sizing, etc.),
# evolution code should validate it in shadow first using the official bridge.
#
# Ergonomic one-call pattern (recommended for most callers):
#
#   from lumina_core.evolution.risk_shadow_bridge import run_risk_shadow_experiment_for_proposal
#   result = run_risk_shadow_experiment_for_proposal(
#       proposal={"experiment_id": ..., "dna_hash": dna.hash, "signal": ..., ...},
#       engine=engine,
#       storage_path=some_registry_path,
#       auto_record_promotion=True,   # <-- new convenience: run + commit promotion decision
#   )
#
# If human review is required, the request will be visible to the shadow_review CLI.
#
# This is the concrete path toward the original requirement:
# "every evolution experiment that touches risk logic must run in a shadow aperture mode".
# ================================================================================


from lumina_core.evolution.promotion_shadow_gate import PromotionShadowGateMixin
from lumina_core.evolution.promotion_evidence import PromotionEvidenceMixin

class PromotionPolicyProtocol(Protocol):
    def mark_shadow_promoted(self, *, dna_hash: str) -> None: ...

    def load_shadow_runs(self) -> dict[str, Any]: ...

    def save_shadow_runs(self, payload: dict[str, Any]) -> None: ...


class _OrchestratorContext(Protocol):
    _guard: Any
    _approval_twin: ApprovalTwinAgent
    _telegram_notifier: Any
    _notification_scheduler: Any
    _veto_registry: Any
    _shadow_state_path: Any
    _promotion_gate: Any


class PromotionPolicy(PromotionEvidenceMixin, PromotionShadowGateMixin):
    def __init__(
        self,
        owner: _OrchestratorContext,
        logger: logging.Logger | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._owner = owner
        self._logger = logger or logging.getLogger(__name__)
        self._event_bus = event_bus

    @staticmethod
    def _as_float_list(values: Any) -> list[float]:
        if not isinstance(values, list):
            return []
        out: list[float] = []
        for item in values:
            try:
                out.append(float(item))
            except (TypeError, ValueError):
                continue
        return out


    def _publish_promotion_gate_violation(self, *, dna_hash: str, decision: PromotionGateDecision) -> None:
        if self._event_bus is None:
            return
        payload = ConstitutionViolation(
            principle_name="promotion_gate_failed",
            severity="fatal",
            description="REAL promotion blocked by PromotionGate",
            detail=";".join(list(decision.fail_reasons)),
            mode="real",
        ).model_dump(mode="json")
        payload["dna_hash"] = str(dna_hash)
        self._event_bus.publish_validated(
            topic="safety.constitution.violation",
            producer="evolution.promotion_policy",
            payload=payload,
            metadata={"dna_hash": str(dna_hash), "gate": "promotion_gate"},
        )

    def send_shadow_status_telegram(self, message: str) -> None:
        def _send() -> bool:
            return self._owner._telegram_notifier._send_telegram_message(message)

        try:
            self._owner._notification_scheduler.schedule_notification(
                callback=_send,
                description=f"shadow_status:{message[:50]}",
            )
        except Exception as exc:
            logging.exception("Unhandled broad exception fallback in lumina_core/evolution/promotion_policy.py:159")
            self._logger.warning("[SHADOWTWIN] Telegram notification failed: %s", exc)

    def send_promotion_status_telegram(self, *, dna_hash: str, promoted: bool, reason: str = "") -> None:
        status = "PROMOTED" if promoted else "VETOED"
        message = f"{status}\nDNA: {str(dna_hash)[:12]}"
        if reason:
            message = f"{message}\nReason: {reason}"
        self.send_shadow_status_telegram(message)

    def resolve_shadow_day_bounds(self) -> tuple[int, int]:
        evolution_cfg = ConfigLoader.section("evolution", default={})
        if not isinstance(evolution_cfg, dict):
            return 3, 7
        shadow_cfg = evolution_cfg.get("shadow_validation", {})
        if not isinstance(shadow_cfg, dict):
            return 3, 7
        min_days = max(1, int(shadow_cfg.get("min_days", 3) or 3))
        max_days = max(min_days, int(shadow_cfg.get("max_days", 7) or 7))
        return min_days, max_days

    def veto_window_for_days(self, days: int) -> VetoWindow:
        return VetoWindow(
            veto_registry=self._owner._veto_registry,
            window_seconds=max(1, int(days)) * 24 * 60 * 60,
        )

    def load_shadow_runs(self) -> dict[str, Any]:
        return load_shadow_runs(self._owner._shadow_state_path)

    def save_shadow_runs(self, payload: dict[str, Any]) -> None:
        save_shadow_runs(self._owner._shadow_state_path, payload)

    def mark_shadow_promoted(self, *, dna_hash: str) -> None:
        shadow_runs = self.load_shadow_runs()
        record = dict(shadow_runs.get(dna_hash, {}) or {})
        if not record:
            return
        record["status"] = "promoted"
        record["updated_at"] = utcnow()
        shadow_runs[dna_hash] = record
        self.save_shadow_runs(shadow_runs)


