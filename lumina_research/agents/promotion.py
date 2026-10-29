"""PromotionAgent: emit PromotionCandidate only after a sealed PASS and research Risk Core approval.

Never writes the live KEEP PromotionGate or the live Risk Core.
A PromotionCandidate is a proposal for a later phase.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
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
from lumina_research.agents.frozen import Frozen
from lumina_research.agents.objects import as_object_dict, as_object_list, mapping_get
from lumina_research.agents.payloads import dump_json
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.risk_core.engine import RiskCore
from lumina_research.risk_core.types import Decision, DecisionKind, OrderProposal, cluster_for
from lumina_research.validation.cost_model import COST_MODEL_ID
from lumina_research.validation.dsr import DSR_FORMULATION
from lumina_research.validation.pbo import PBO_FORMULATION
from lumina_research.validation.thresholds import (
    FLOOR_DSR_PROBABILITY_MIN,
    FLOOR_MIN_OOS_WINDOWS,
    FLOOR_PBO_HARD_REJECT,
    FLOOR_WFE_MIN,
)

logger = logging.getLogger(__name__)


class PromotionRefused(ValueError):
    """Direct emission or an unauthenticated / failing ValidationResult."""


class PromotionAgent(Frozen):
    """Fail-closed issuer. Scaled counts as approved, with the scaled size."""

    _bus: EventBus
    _core: RiskCore
    _authority: ProvenanceAuthority
    _log_path: Path
    _hypotheses: dict[str, object]
    _blackboard: AgentBlackboard | None
    _issued: list[PromotionCandidate]
    _consume_trial: Callable[[int], bool]

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
        self._bus = bus
        self._core = core
        self._authority = authority
        self._log_path = experiment_log_path
        self._hypotheses = dict(hypotheses or {})
        self._blackboard = blackboard
        self._issued = []
        seen: set[int] = set()

        def consume(trial_id: int) -> bool:
            if trial_id in seen:
                return False
            seen.add(trial_id)
            return True

        self._consume_trial = consume
        self._freeze()
        bus.register_topic_guard(RESEARCH_PROMOTION_TOPIC, self._guard_issue)
        if blackboard is not None:
            blackboard.register_topic_guard(RESEARCH_PROMOTION_TOPIC, self._guard_issue)
        bus.subscribe(RESEARCH_HYPOTHESIS_TOPIC, self._on_hypothesis)
        bus.subscribe(RESEARCH_VALIDATION_TOPIC, self._on_validation)

    def remember_hypothesis(self, hypothesis_id: str, payload: Mapping[str, object]) -> None:
        """Index a hypothesis so a later sealed ValidationResult can be bound to it."""
        self._hypotheses[hypothesis_id] = dict(payload)

    def issued(self) -> tuple[PromotionCandidate, ...]:
        """PromotionCandidates actually published on the bus (empty if none survived)."""
        return tuple(self._issued)

    def emit_candidate(self, candidate: PromotionCandidate) -> None:
        raise PromotionRefused("direct emission of PromotionCandidate is forbidden")

    def consider(self, event: DomainEvent | ValidationResult) -> PromotionCandidate | None:
        """Promote only a first-seen, MAC-valid PASS that research Risk Core approves."""
        payload = _payload_dict(event)
        verified = self._authority.verify_validation(payload)
        if verified is None:
            self._log_kill(payload, "provenance_invalid", ("provenance_invalid",))
            return None
        trial_id = _as_int(verified.get("trial_id"))
        if trial_id is None:
            self._log_kill(payload, "trial_id_invalid", ("trial_id_invalid",))
            return None
        if payload.get("trial_id") != trial_id:
            self._log_kill(payload, "trial_id_replay", ("trial_id_replay",))
            return None
        if not self._consume_trial(trial_id):
            self._log_kill(payload, "validation_replay", ("validation_replay",))
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
        horizon = hyp.get("expected_horizon_bars")
        if not isinstance(horizon, int) or isinstance(horizon, bool) or horizon < 1:
            self._log_kill(payload, "expected_horizon_missing", ("expected_horizon_missing",))
            return None
        decided = self._risk_decide(hyp)
        if decided is None:
            self._log_kill(payload, "hypothesis_malformed", ("hypothesis_malformed",))
            return None
        decision, proposal_side = decided
        if decision.kind is DecisionKind.REJECTED:
            self._log_kill(payload, f"risk:{decision.reason}", (f"risk:{decision.reason}",))
            return None
        if decision.kind is DecisionKind.APPROVED:
            scaled = False
        elif decision.kind is DecisionKind.SCALED:
            scaled = True
        else:
            assert_never(decision.kind)
        unsigned: dict[str, object] = {
            "schema_version": "research.promotion.candidate.v1",
            "hypothesis_id": hypothesis_id,
            "config_id": str(verified["config_id"]),
            "trial_id": trial_id,
            "agent_id": PROMOTION_AGENT_ID,
            "instrument": str(hyp["instrument"]),
            "direction": "BUY" if proposal_side == "buy" else "SELL",
            "decision_kind": "scaled" if scaled else "approved",
            "scaled": scaled,
            "quantity": float(decision.quantity),
            "notional": float(decision.notional),
            "risk_reason": decision.reason,
            "expected_horizon_bars": int(horizon),
            "validation_report_sha256": str(payload["report_sha256"]),
            "validation_mac": str(payload["provenance_mac"]),
        }
        issue_mac = self._authority.seal_issue(unsigned)
        candidate = PromotionCandidate.model_validate({**unsigned, "issue_mac": issue_mac})
        dumped = dump_json(candidate)
        self._bus.publish(
            topic=RESEARCH_PROMOTION_TOPIC,
            producer=PROMOTION_AGENT_ID,
            payload=dict(dumped),
        )
        if self._blackboard is not None:
            self._blackboard.publish_sync(
                topic=RESEARCH_PROMOTION_TOPIC,
                producer=PROMOTION_AGENT_ID,
                payload=dict(dumped),
                confidence=1.0,
            )
        self._issued.append(candidate)
        log_experiment(
            path=self._log_path,
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
        self.remember_hypothesis(hyp.hypothesis_id, dump_json(hyp))

    def _on_validation(self, event: DomainEvent) -> None:
        try:
            self.consider(event)
        except Exception:
            logger.exception("PromotionAgent.consider failed closed")
            self._log_kill(event.payload, "consider_error", ("consider_error",))

    def _guard_issue(self, producer: str, payload: dict[str, object]) -> bool:
        return self._authority.guard_promotion(producer, payload)

    def _lookup(self, hypothesis_id: str) -> dict[str, object] | None:
        return as_object_dict(self._hypotheses.get(hypothesis_id))

    def _risk_decide(self, hyp: Mapping[str, object]) -> tuple[Decision, str] | None:
        instrument = hyp.get("instrument")
        quantity = hyp.get("proposed_quantity")
        price = hyp.get("proposed_price")
        notional = hyp.get("proposed_notional")
        if not isinstance(instrument, str):
            return None
        qty = _as_float(quantity)
        px = _as_float(price)
        notion = _as_float(notional)
        if qty is None or px is None or notion is None:
            return None
        now = datetime.now(timezone.utc)
        self._core.heartbeat(now)
        proposal = OrderProposal(
            agent_id=PROMOTION_AGENT_ID,
            instrument=instrument,
            side="buy",
            quantity=qty,
            price=px,
            notional=notion,
            cluster_id=cluster_for(instrument),
            submitted_at_utc=now,
        )
        return self._core.propose_order(proposal), proposal.side

    def _log_kill(self, payload: Mapping[str, object], reason: str, checks: tuple[str, ...]) -> None:
        hypothesis_id = str(payload.get("hypothesis_id", "unknown"))
        log_experiment(
            path=self._log_path,
            agent_id=PROMOTION_AGENT_ID,
            event="kill",
            hypothesis_id=hypothesis_id,
            rationale=None,
            metrics=_kill_metrics(payload),
            reject_reason=reason,
            failed_checks=checks,
        )


def _payload_dict(event: DomainEvent | ValidationResult) -> dict[str, object]:
    if isinstance(event, ValidationResult):
        return dump_json(event)
    return dict(event.payload)


def _as_reasons(value: object) -> tuple[str, ...]:
    items = as_object_list(value)
    if items is None:
        return ()
    return tuple(str(item) for item in items)


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _kill_metrics(payload: Mapping[str, object]) -> dict[str, object]:
    return {
        "payload_trial_id": payload.get("trial_id"),
        "passed": payload.get("passed"),
        "oos_distribution": payload.get("oos_distribution"),
        "dsr": payload.get("dsr"),
        "pbo": payload.get("pbo"),
        "wfe": payload.get("wfe"),
        "regimes": payload.get("regimes"),
        "n_oos_windows": payload.get("n_oos_windows"),
        "median_oos_after_costs": payload.get("median_oos_after_costs"),
        "purge_applied": payload.get("purge_applied"),
        "embargo_applied": payload.get("embargo_applied"),
        "cost_applied": payload.get("cost_applied"),
        "cost_contract_root": payload.get("cost_contract_root"),
        "cost_model_id": payload.get("cost_model_id"),
        "regimes_complete": payload.get("regimes_complete"),
        "reject_reasons": payload.get("reject_reasons"),
    }


def _gate_pass(verified: Mapping[str, object]) -> bool:
    """Read pass/fail only from MAC-authenticated fields. Independent floor re-check."""
    if verified.get("passed") is not True:
        return False
    if _as_reasons(verified.get("reject_reasons")):
        return False
    if verified.get("purge_applied") is not True:
        return False
    if verified.get("embargo_applied") is not True:
        return False
    if verified.get("cost_applied") is not True:
        return False
    if verified.get("regimes_complete") is not True:
        return False
    root = mapping_get(verified, "cost_contract_root")
    if not isinstance(root, str) or root.strip() not in {"ES", "NQ", "MES", "MNQ"}:
        return False
    if mapping_get(verified, "cost_model_id") != COST_MODEL_ID:
        return False
    dsr = as_object_dict(mapping_get(verified, "dsr"))
    pbo = as_object_dict(mapping_get(verified, "pbo"))
    wfe = as_object_dict(mapping_get(verified, "wfe"))
    oos = as_object_dict(mapping_get(verified, "oos_distribution"))
    if dsr is None or pbo is None or wfe is None or oos is None:
        return False
    if mapping_get(dsr, "formulation") != DSR_FORMULATION:
        return False
    if mapping_get(pbo, "formulation") != PBO_FORMULATION:
        return False
    dsr_p = mapping_get(dsr, "probability")
    pbo_p = mapping_get(pbo, "pbo")
    wfe_v = mapping_get(wfe, "wfe")
    values = as_object_list(mapping_get(oos, "values"))
    if not isinstance(dsr_p, (int, float)) or isinstance(dsr_p, bool) or float(dsr_p) < FLOOR_DSR_PROBABILITY_MIN:
        return False
    if not isinstance(pbo_p, (int, float)) or isinstance(pbo_p, bool) or float(pbo_p) > FLOOR_PBO_HARD_REJECT:
        return False
    if not isinstance(wfe_v, (int, float)) or isinstance(wfe_v, bool) or float(wfe_v) < FLOOR_WFE_MIN:
        return False
    windows = mapping_get(verified, "n_oos_windows")
    if not isinstance(windows, int) or isinstance(windows, bool) or windows < FLOOR_MIN_OOS_WINDOWS:
        return False
    if values is None or len(values) < 1:
        return False
    median = mapping_get(verified, "median_oos_after_costs")
    if not isinstance(median, (int, float)) or isinstance(median, bool) or float(median) < 0.0:
        return False
    return True


def validation_gate_pass(verified: Mapping[str, object]) -> bool:
    """Independent floor re-check. Used by PromotionAgent and the live book."""
    return _gate_pass(verified)
