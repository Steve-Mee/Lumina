"""Shared Phase 2 test harness. Synthetic only, no network."""

from __future__ import annotations

from pathlib import Path

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_research.agents.generators import NoiseGenerator, PlantedEdgeGenerator
from lumina_research.agents.hypothesis import HypothesisAgent
from lumina_research.agents.loop import run_phase2_loop
from lumina_research.agents.promotion import PromotionAgent
from lumina_research.agents.provenance import ProvenanceAuthority
from lumina_research.agents.validation_agent import ValidationAgent
from lumina_research.risk_core.config import load_default_config
from lumina_research.risk_core.engine import RiskCore
from lumina_research.validation.cost_model import COST_MODEL_ID
from lumina_research.validation.trial_registry import TrialRegistry

VALIDATION_INTEGRITY: dict[str, object] = {
    "purge_applied": True,
    "embargo_applied": True,
    "cost_applied": True,
    "cost_contract_root": "MES",
    "cost_model_id": COST_MODEL_ID,
    "regimes_complete": True,
}


def with_integrity(fields: dict[str, object], **overrides: object) -> dict[str, object]:
    """Attach MAC-bound integrity flags. Overrides win."""
    merged: dict[str, object] = {**fields, **VALIDATION_INTEGRITY}
    merged.update(overrides)
    return merged


def make_bus() -> EventBus:
    return EventBus()


def make_board(tmp_path: Path) -> AgentBlackboard:
    return AgentBlackboard(persistence_path=tmp_path / "bb.jsonl")


def make_agents(
    tmp_path: Path,
    *,
    n_obs: int = 360,
    planted_quantity: float = 1.0,
    planted_price: float = 5_000.0,
    blackboard: AgentBlackboard | None = None,
    equity: float = 100_000.0,
    risk_equity: float | None = None,
    instrument: str = "MES",
) -> tuple[EventBus, TrialRegistry, ProvenanceAuthority, HypothesisAgent, ValidationAgent, PromotionAgent]:
    bus = EventBus()
    audit = tmp_path / "audit.jsonl"
    log_path = tmp_path / "experiments.jsonl"
    registry = TrialRegistry(audit)
    authority = ProvenanceAuthority()
    core = RiskCore(load_default_config(), equity=equity if risk_equity is None else risk_equity)
    hypothesis = HypothesisAgent(
        bus=bus,
        registry=registry,
        generators=(
            NoiseGenerator(n_obs=n_obs, instrument=instrument),
            PlantedEdgeGenerator(
                n_obs=n_obs,
                quantity=planted_quantity,
                price=planted_price,
                instrument=instrument,
            ),
        ),
        experiment_log_path=log_path,
        blackboard=blackboard,
    )
    validation = ValidationAgent(
        bus=bus,
        registry=registry,
        authority=authority,
        experiment_log_path=log_path,
        blackboard=blackboard,
        audit_path=audit,
        equity=equity,
    )
    promotion = PromotionAgent(
        bus=bus,
        core=core,
        authority=authority,
        experiment_log_path=log_path,
        blackboard=blackboard,
    )
    return bus, registry, authority, hypothesis, validation, promotion


def run_small_loop(tmp_path: Path, *, n_noise: int = 4, n_planted: int = 2, seed: int = 7) -> object:
    return run_phase2_loop(
        audit_path=tmp_path / "audit.jsonl",
        experiment_log_path=tmp_path / "exp.jsonl",
        n_noise=n_noise,
        n_planted=n_planted,
        seed=seed,
        report_dir=tmp_path / "reports",
    )
