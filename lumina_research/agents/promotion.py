"""PromotionAgent: emit PromotionCandidate only after a sealed PASS and research Risk Core approval.

Never writes the live PromotionGate (`lumina_core/evolution/promotion_gate.py`) or the
live Risk Core (`lumina_core/risk/`). A PromotionCandidate is a proposal for a later phase.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, assert_never

from lumina_core.agent_orchestration.event_bus import DomainEvent, EventBus
from lumina_core.agent_orchestration.schemas_research import (
    PROMOTION_AGENT_ID,
    RESEARCH_HYPOTHESIS_TOPIC,
    RESEARCH_PROMOTION_TOPIC,
    RESEARCH_VALIDATION_TOPIC,
    HypothesisProposed,
    PromotionCandidate,
    ValidationResult,
)
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.experiment_log import log_experiment
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.risk_core.engine import RiskCore
from lumina_research.risk_core.types import Decision, DecisionKind, OrderProposal, cluster_for
from lumina_research.validation.thresholds import (
    FLOOR_DSR_PROBABILITY_MIN,
    FLOOR_MIN_OOS_WINDOWS,
    FLOOR_PBO_HARD_REJECT,
    FLOOR_WFE_MIN,
)

logger = logging.getLogger(__name__)


class PromotionRefused(ValueError):
    """Direct emission or an unauthenticated / failing ValidationResult."""


class PromotionAgent:
    """Fail-closed issuer. Scaled counts as approved, with the scaled size."""

    def __init_subclass__(cls) -> None:
        raise TypeError("PromotionAgent cannot be subclassed")

    def __init__(
        self,
        *,
        bus: EventBus,
        core: RiskCore,
        authority: ProvenanceAuthority,
        experiment_log_path: Path,
        hypotheses: Mapping[str, object] | None = None,
        blackboard: AgentBlackboard | None = None,
    ) -> None:
        object.__setattr__(self, "_bus", bus)
        object.__setattr__(self, "_core", core)
        object.__setattr__(self, "_authority", authority)
        object.__setattr__(self, "_log_path", experiment_log_path)
        object.__setattr__(self, "_hypotheses", dict(hypotheses or {}))
        object.__setattr__(self, "_blackboard", blackboard)
        object.__setattr__(self, "_issued", [])
        bus.register_topic_guard(RESEARCH_PROMOTION_TOPIC, self._guard_issue)
        if blackboard is not None:
            blackboard.register_topic_guard(RESEARCH_PROMOTION_TOPIC, self._guard_issue)
        bus.subscribe(RESEARCH_HYPOTHESIS_TOPIC, self._on_hypothesis)
        bus.subscribe(RESEARCH_VALIDATION_TOPIC, self._on_validation)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("PromotionAgent attributes are frozen")

    def remember_hypothesis(self, hypothesis_id: str, payload: Mapping[str, object]) -> None:
        store: dict[str, object] = self._hypotheses  # type: ignore[attr-defined]
        store[hypothesis_id] = dict(payload)

    def issued(self) -> tuple[PromotionCandidate, ...]:
        issued: list[PromotionCandidate] = self._issued  # type: ignore[attr-defined]
        return tuple(issued)

    def emit_candidate(self, candidate: PromotionCandidate) -> None:
        raise PromotionRefused("direct emission of PromotionCandidate is forbidden")

    def consider(self, event: DomainEvent | ValidationResult) -> PromotionCandidate | None:
        payload = _payload_dict(event)
        authority: ProvenanceAuthority = self._authority  # type: ignore[attr-defined]
        verified = authority.verify_validation(payload)
        if verified is None:
            self._log_kill(payload, "provenance_invalid", ("provenance_invalid",))
            return None
        replayed = payload.get("trial_id") != verified.get("trial_id")
        if replayed:
            self._log_kill(payload, "trial_id_replay", ("trial_id_replay",))
            return None
        if not _gate_pass(verified):
            reasons = _as_reasons(verified.get("reject_reasons"))
            self._log_kill(payload, reasons[0] if reasons else "gate_failed", reasons)
            return None
        hypothesis_id = str(verified["hypothesis_id"])
        hyp = self._lookup(hypothesis_id)
        if hyp is None:
            self._log_kill(payload, "hypothesis_unknown", ("hypothesis_unknown",))
            return None
        decision = self._risk_decide(hyp)
        if decision.kind is DecisionKind.REJECTED:
            self._log_kill(payload, f"risk:{decision.reason}", (f"risk:{decision.reason}",))
            return None
        if decision.kind is DecisionKind.APPROVED:
            scaled = False
        elif decision.kind is DecisionKind.SCALED:
            scaled = True
        else:
            assert_never(decision.kind)
        unsigned = {
            "schema_version": "research.promotion.candidate.v1",
            "hypothesis_id": hypothesis_id,
            "config_id": str(verified["config_id"]),
            "trial_id": int(verified["trial_id"]),
            "agent_id": PROMOTION_AGENT_ID,
            "instrument": str(hyp["instrument"]),
            "decision_kind": "scaled" if scaled else "approved",
            "scaled": scaled,
            "quantity": float(decision.quantity),
            "notional": float(decision.notional),
            "risk_reason": decision.reason,
            "validation_report_sha256": str(payload["report_sha256"]),
            "validation_mac": str(payload["provenance_mac"]),
        }
        issue_mac = authority.seal_issue(unsigned)
        candidate = PromotionCandidate.model_validate({**unsigned, "issue_mac": issue_mac})
        dumped = candidate.model_dump(mode="json", exclude_none=False)
        bus: EventBus = self._bus  # type: ignore[attr-defined]
        bus.publish(
            topic=RESEARCH_PROMOTION_TOPIC,
            producer=PROMOTION_AGENT_ID,
            payload=dumped,
        )
        board: AgentBlackboard | None = self._blackboard  # type: ignore[attr-defined]
        if board is not None:
            board.publish_sync(
                topic=RESEARCH_PROMOTION_TOPIC,
                producer=PROMOTION_AGENT_ID,
                payload=dumped,
                confidence=1.0,
            )
        issued: list[PromotionCandidate] = self._issued  # type: ignore[attr-defined]
        issued.append(candidate)
        log_experiment(
            path=self._log_path,  # type: ignore[attr-defined]
            agent_id=PROMOTION_AGENT_ID,
            event="promotion",
            hypothesis_id=hypothesis_id,
            rationale=None,
            metrics=dumped,
            reject_reason=None,
            failed_checks=(),
        )
        return candidate

    def _on_hypothesis(self, event: DomainEvent) -> None:
        hyp = event.typed_payload(HypothesisProposed)
        self.remember_hypothesis(hyp.hypothesis_id, hyp.model_dump(mode="json"))

    def _on_validation(self, event: DomainEvent) -> None:
        try:
            self.consider(event)
        except Exception:
            logger.exception("PromotionAgent.consider failed closed")
            self._log_kill(event.payload, "consider_error", ("consider_error",))

    def _guard_issue(self, producer: str, payload: dict[str, object]) -> bool:
        authority: ProvenanceAuthority = self._authority  # type: ignore[attr-defined]
        return authority.guard_promotion(producer, payload)

    def _lookup(self, hypothesis_id: str) -> dict[str, object] | None:
        store: dict[str, object] = self._hypotheses  # type: ignore[attr-defined]
        raw = store.get(hypothesis_id)
        if not isinstance(raw, dict):
            return None
        return raw

    def _risk_decide(self, hyp: Mapping[str, object]) -> Decision:
        instrument = str(hyp["instrument"])
        quantity = float(hyp["proposed_quantity"])
        price = float(hyp["proposed_price"])
        notional = float(hyp["proposed_notional"])
        proposal = OrderProposal(
            agent_id=PROMOTION_AGENT_ID,
            instrument=instrument,
            side="buy",
            quantity=quantity,
            price=price,
            notional=notional,
            cluster_id=cluster_for(instrument),
            submitted_at_utc=datetime.now(timezone.utc),
        )
        core: RiskCore = self._core  # type: ignore[attr-defined]
        core.heartbeat(datetime.now(timezone.utc))
        return core.propose_order(proposal)

    def _log_kill(self, payload: Mapping[str, object], reason: str, checks: tuple[str, ...]) -> None:
        hypothesis_id = str(payload.get("hypothesis_id", "unknown"))
        log_experiment(
            path=self._log_path,  # type: ignore[attr-defined]
            agent_id=PROMOTION_AGENT_ID,
            event="kill",
            hypothesis_id=hypothesis_id,
            rationale=None,
            metrics={"payload_trial_id": payload.get("trial_id"), "passed": payload.get("passed")},
            reject_reason=reason,
            failed_checks=checks,
        )


def _payload_dict(event: DomainEvent | ValidationResult) -> dict[str, object]:
    if isinstance(event, ValidationResult):
        return event.model_dump(mode="json", exclude_none=False)
    return dict(event.payload)


def _as_reasons(value: object) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    return ()


def _gate_pass(verified: Mapping[str, object]) -> bool:
    """Read pass/fail only from MAC-authenticated fields. Independent floor re-check."""
    if verified.get("passed") is not True:
        return False
    if _as_reasons(verified.get("reject_reasons")):
        return False
    dsr = verified.get("dsr")
    pbo = verified.get("pbo")
    wfe = verified.get("wfe")
    oos = verified.get("oos_distribution")
    if not isinstance(dsr, dict) or not isinstance(pbo, dict) or not isinstance(wfe, dict):
        return False
    if not isinstance(oos, dict):
        return False
    dsr_p = dsr.get("probability")
    pbo_p = pbo.get("pbo")
    wfe_v = wfe.get("wfe")
    values = oos.get("values")
    if not isinstance(dsr_p, (int, float)) or float(dsr_p) < FLOOR_DSR_PROBABILITY_MIN:
        return False
    if not isinstance(pbo_p, (int, float)) or float(pbo_p) > FLOOR_PBO_HARD_REJECT:
        return False
    if not isinstance(wfe_v, (int, float)) or float(wfe_v) < FLOOR_WFE_MIN:
        return False
    windows = verified.get("n_oos_windows")
    if not isinstance(windows, int) or windows < FLOOR_MIN_OOS_WINDOWS:
        return False
    if not isinstance(values, list) or len(values) < 1:
        return False
    median = verified.get("median_oos_after_costs")
    if not isinstance(median, (int, float)) or float(median) < 0.0:
        return False
    return True
