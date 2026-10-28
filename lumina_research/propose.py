"""Research propose path: Validation Gate first, then the research Risk Core.

This module is the only wiring from gate → fitness → research-time propose_order.
It imports both layers; `risk_core` still imports neither validation nor this file.
"""

from __future__ import annotations

from lumina_research.risk_core.types import Decision, OrderProposal
from lumina_research.risk_core.engine import RiskCore
from lumina_research.validation.audit import write_event
from lumina_research.validation.pipeline import CandidateEvaluation


def propose_research_order(
    proposal: OrderProposal,
    *,
    core: RiskCore,
    evaluation: CandidateEvaluation,
) -> Decision:
    """Reject when the gate failed; otherwise apply the research Risk Core."""
    if not evaluation.passed:
        write_event(
            path=evaluation.results.audit_path,
            agent_id=proposal.agent_id,
            event="reject",
            metrics={
                "reason": "validation_gate",
                "instrument": proposal.instrument,
                "notional": proposal.notional,
                **evaluation.report.to_audit_metrics(),
            },
        )
        return Decision.rejected(proposal, "validation_gate")
    return core.propose_order(proposal)
