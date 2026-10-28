"""End-to-end research loop: HypothesisProposed → Validation Gate → PromotionCandidate."""

from __future__ import annotations

from pathlib import Path

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.generators import NoiseGenerator, PlantedEdgeGenerator
from lumina_research.agents.hypothesis import HypothesisAgent
from lumina_research.agents.promotion import PromotionAgent
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.agents.report import KillRateReport, build_kill_rate_report, write_kill_rate_reports
from lumina_research.agents.validation_agent import ValidationAgent
from lumina_research.risk_core.config import load_default_config
from lumina_research.risk_core.engine import RiskCore
from lumina_research.validation.trial_registry import TrialRegistry

DEFAULT_SEED = 20261028
DEFAULT_N_NOISE = 23
DEFAULT_N_PLANTED = 2


def run_phase2_loop(
    *,
    audit_path: Path,
    experiment_log_path: Path,
    n_noise: int = DEFAULT_N_NOISE,
    n_planted: int = DEFAULT_N_PLANTED,
    seed: int = DEFAULT_SEED,
    report_dir: Path | None = None,
    bus: EventBus | None = None,
    blackboard: AgentBlackboard | None = None,
    equity: float = 100_000.0,
    authority: ProvenanceAuthority | None = None,
) -> KillRateReport:
    """Generate hypotheses, run the full Phase 1 gate, promote only sealed survivors."""
    event_bus = bus if bus is not None else EventBus()
    registry = TrialRegistry(audit_path)
    sealer = authority if authority is not None else ProvenanceAuthority()
    core = RiskCore(load_default_config(), equity=equity)
    hypothesis_agent = HypothesisAgent(
        bus=event_bus,
        registry=registry,
        generators=(NoiseGenerator(), PlantedEdgeGenerator()),
        experiment_log_path=experiment_log_path,
        blackboard=blackboard,
    )
    validation_agent = ValidationAgent(
        bus=event_bus,
        registry=registry,
        authority=sealer,
        experiment_log_path=experiment_log_path,
        blackboard=blackboard,
        audit_path=audit_path,
    )
    promotion_agent = PromotionAgent(
        bus=event_bus,
        core=core,
        authority=sealer,
        experiment_log_path=experiment_log_path,
        blackboard=blackboard,
    )
    generated = hypothesis_agent.generate(seed=seed, counts=(n_noise, n_planted))
    results = validation_agent.flush()
    planted_ids = tuple(item.hypothesis_id for item in generated if item.planted)
    planted_flags = {item.hypothesis_id: item.planted for item in generated}
    report = build_kill_rate_report(
        seed=seed,
        planted_ids=planted_ids,
        results=results,
        promotions=promotion_agent.issued(),
        planted_flags=planted_flags,
    )
    if report_dir is not None:
        write_kill_rate_reports(report, report_dir)
    return report
