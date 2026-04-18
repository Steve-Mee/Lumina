from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_core.engine.meta_agent_orchestrator import MetaAgentOrchestrator


class _SelfEvolutionStub:
    def __init__(self) -> None:
        self.calls = []

    def run_nightly_evolution(self, *, nightly_report, dry_run):
        self.calls.append((nightly_report, dry_run))
        return {
            "status": "proposed",
            "proposal": {"confidence": 88.0, "would_auto_apply": False},
            "dna": {
                "active": {
                    "hash": "active_hash_1",
                    "version": "active",
                    "lineage_hash": "lineage_hash_1",
                },
                "candidate": {
                    "hash": "candidate_hash_1",
                    "version": "candidate",
                    "lineage_hash": "lineage_hash_1",
                },
            },
        }


class _TrainerStub:
    def __init__(self) -> None:
        self.train_calls = 0

    def train(self, total_timesteps: int) -> None:
        self.train_calls += total_timesteps


class _BibleStub:
    def __init__(self) -> None:
        self.updates = []

    def evolve(self, updates):
        self.updates.append(dict(updates))


def test_meta_orchestrator_runs_reflection_and_evolution(tmp_path: Path) -> None:
    bus = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    bus.publish_sync(
        topic="execution.aggregate",
        producer="runtime",
        payload={"executed": True, "pnl": -10.0},
        confidence=0.62,
    )
    bus.publish_sync(
        topic="execution.aggregate",
        producer="runtime",
        payload={"executed": True, "pnl": 5.0},
        confidence=0.64,
    )

    self_evolution = _SelfEvolutionStub()
    trainer = _TrainerStub()
    bible = _BibleStub()
    orchestrator = MetaAgentOrchestrator(
        blackboard=bus,
        self_evolution_agent=self_evolution,
        ppo_trainer=trainer,
        bible_engine=bible,
    )

    result = orchestrator.run_nightly_reflection(
        nightly_report={"trades": 2, "wins": 1, "net_pnl": -5.0, "mean_worker_sharpe": 0.1},
        dry_run=False,
    )

    assert result["retraining"]["triggered"] is True
    assert trainer.train_calls == 50000
    assert len(self_evolution.calls) == 1
    assert len(bible.updates) == 1
    lineage = bus.latest("meta.dna_lineage")
    assert lineage is not None
    assert lineage.payload["active_hash"] == "active_hash_1"
    assert lineage.payload["lineage_hash"] == "lineage_hash_1"


def test_meta_orchestrator_dry_run_skips_training(tmp_path: Path) -> None:
    bus = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    self_evolution = _SelfEvolutionStub()
    trainer = _TrainerStub()
    orchestrator = MetaAgentOrchestrator(
        blackboard=bus,
        self_evolution_agent=self_evolution,
        ppo_trainer=trainer,
        bible_engine=SimpleNamespace(evolve=lambda *_a, **_k: None),
    )

    result = orchestrator.run_nightly_reflection(
        nightly_report={"trades": 0, "wins": 0, "net_pnl": 0.0, "mean_worker_sharpe": 0.0},
        dry_run=True,
    )

    assert result["retraining"]["executed"] is False
    assert trainer.train_calls == 0
