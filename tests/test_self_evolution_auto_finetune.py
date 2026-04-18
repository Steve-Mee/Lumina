from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from lumina_core.engine.risk_controller import HardRiskController, RiskLimits
from lumina_core.engine.self_evolution_meta_agent import SelfEvolutionMetaAgent
from lumina_core.engine.valuation_engine import ValuationEngine
from lumina_core.evolution.dna_registry import DNARegistry


class _StubPPOTrainer:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.called = False
        self.last_len = 0

    def train(self, simulator_data, *, total_timesteps: int = 0, policy_path: str | None = None):
        self.called = True
        self.last_len = len(simulator_data)
        out = policy_path or str(self.output_path)
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text("stub-policy", encoding="utf-8")
        return out


def _seed_low_acceptance_log(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entries = [
        {
            "timestamp": "2026-04-07T10:00:00+00:00",
            "status": "proposed",
            "meta_review": {"rl_drift": 0.1, "regime_drift": 0.1},
        },
        {
            "timestamp": "2026-04-07T11:00:00+00:00",
            "status": "awaiting_human_approval",
            "meta_review": {"rl_drift": 0.1, "regime_drift": 0.1},
        },
        {
            "timestamp": "2026-04-08T09:00:00+00:00",
            "status": "proposed",
            "meta_review": {"rl_drift": 0.1, "regime_drift": 0.1},
        },
    ]
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def test_auto_fine_tune_triggered_by_low_acceptance(tmp_path: Path) -> None:
    log_path = tmp_path / "evolution_log.jsonl"
    _seed_low_acceptance_log(log_path)

    trainer = _StubPPOTrainer(tmp_path / "ppo" / "finetuned.zip")
    engine = SimpleNamespace(
        config=SimpleNamespace(
            risk_profile="balanced",
            max_risk_percent=1.0,
            drawdown_kill_percent=8.0,
            agent_styles={"risk": "r"},
        ),
        regime_history=[{"label": "TRENDING"}, {"label": "RANGING"}],
        emotional_twin=None,
        decision_log=None,
        ppo_trainer=trainer,
        rl_env=SimpleNamespace(name="rl-env"),
    )
    agent = SelfEvolutionMetaAgent(
        engine=cast(Any, engine),
        valuation_engine=ValuationEngine(),
        risk_controller=HardRiskController(RiskLimits(enforce_session_guard=False), enforce_rules=True),
        approval_required=True,
        runtime_mode="paper",
        log_path=log_path,
        auto_fine_tuning_enabled=True,
        min_acceptance_rate=0.4,
        drift_threshold=0.25,
        ppo_trainer=trainer,
        rl_environment=SimpleNamespace(name="rl-env"),
        dna_registry=DNARegistry(
            jsonl_path=tmp_path / "dna_registry.jsonl",
            sqlite_path=tmp_path / "dna_registry.sqlite3",
        ),
    )

    result = agent.run_nightly_evolution(
        nightly_report={
            "trades": 120,
            "wins": 64,
            "net_pnl": 900.0,
            "sharpe": 0.8,
            "samples": [{"close": 5000 + i, "reward": 0.2} for i in range(40)],
        },
        dry_run=False,
    )

    assert result["auto_fine_tune"]["triggered"] is True
    assert result["auto_fine_tune"]["executed"] is True
    assert trainer.called is True
    assert "champion_finetuned_" in result["auto_fine_tune"]["champion_candidate"]["name"]
    assert result["dna"]["active"]["version"] == "active"
    assert result["dna"]["candidate"]["version"] == "candidate"
    assert (tmp_path / "dna_registry.jsonl").exists()


@pytest.mark.safety_gate
def test_sim_mode_forces_nightly_apply_even_without_threshold(tmp_path: Path) -> None:
    """SIM mode must evaluate and apply nightly evolution unconditionally (unless dry_run)."""
    log_path = tmp_path / "evolution_log.jsonl"
    trainer = _StubPPOTrainer(tmp_path / "ppo" / "sim_forced_apply.zip")

    engine = SimpleNamespace(
        config=SimpleNamespace(
            risk_profile="balanced",
            max_risk_percent=1.0,
            drawdown_kill_percent=8.0,
            agent_styles={"risk": "r"},
        ),
        regime_history=[{"label": "RANGING"}],
        emotional_twin=None,
        decision_log=None,
        ppo_trainer=trainer,
        rl_env=SimpleNamespace(name="rl-env"),
    )
    agent = SelfEvolutionMetaAgent(
        engine=cast(Any, engine),
        valuation_engine=ValuationEngine(),
        risk_controller=HardRiskController(RiskLimits(enforce_session_guard=False), enforce_rules=False),
        approval_required=False,
        sim_mode=True,
        aggressive_evolution=True,
        max_mutation_depth="radical",
        log_path=log_path,
        auto_fine_tuning_enabled=False,
        dna_registry=DNARegistry(
            jsonl_path=tmp_path / "dna_registry.jsonl",
            sqlite_path=tmp_path / "dna_registry.sqlite3",
        ),
    )

    # Deliberately weak report so confidence/backtest thresholds are not required.
    result = agent.run_nightly_evolution(
        nightly_report={
            "trades": 8,
            "wins": 2,
            "net_pnl": -50.0,
            "sharpe": -0.4,
            "max_drawdown": 100.0,
            "samples": [{"close": 5000 + i, "reward": -0.2} for i in range(8)],
        },
        dry_run=False,
    )

    assert result["status"] in {"applied", "proposed"}
    assert result["proposal"]["forced_by_sim_mode"] is True
    assert result["governance"]["mode"] == "sim"
    assert result["governance"]["mutation_allowed"] is True
    assert result["proposal"]["would_auto_apply"] == result["proposal"]["signed_approval"]
    assert result["proposal"]["auto_apply_executed"] == (result["status"] == "applied")
    assert result["lifecycle"]["state"] in {"promoted", "rolled_back"}
    assert result["lifecycle"]["version_id"].startswith("evo-")
    assert result["ab_experiment"]["variant_count"] >= 5
    assert result["genetic_evolution"]["candidate_count"] >= 5
    assert result["dna"]["active"]["version"] == "active"


@pytest.mark.chaos_risk
@pytest.mark.chaos_ci_smoke
def test_auto_fine_tune_triggered_by_high_drift_chaos(tmp_path: Path) -> None:
    trainer = _StubPPOTrainer(tmp_path / "ppo" / "finetuned_drift.zip")
    log_path = tmp_path / "evolution_log.jsonl"

    engine = SimpleNamespace(
        config=SimpleNamespace(
            risk_profile="balanced",
            max_risk_percent=1.0,
            drawdown_kill_percent=8.0,
            agent_styles={"risk": "r"},
        ),
        regime_history=[{"label": "TRENDING"}, {"label": "NEWS_DRIVEN"}, {"label": "VOLATILE"}],
        emotional_twin=None,
        decision_log=None,
        ppo_trainer=trainer,
        rl_env=SimpleNamespace(name="rl-env"),
    )
    agent = SelfEvolutionMetaAgent(
        engine=cast(Any, engine),
        valuation_engine=ValuationEngine(),
        risk_controller=HardRiskController(RiskLimits(enforce_session_guard=False), enforce_rules=True),
        approval_required=True,
        log_path=log_path,
        auto_fine_tuning_enabled=True,
        min_acceptance_rate=0.4,
        drift_threshold=0.25,
        ppo_trainer=trainer,
    )

    result = agent.run_nightly_evolution(
        nightly_report={
            "trades": 100,
            "wins": 52,
            "net_pnl": 200.0,
            "sharpe": 0.4,
            "max_drawdown": 400.0,
            "samples": [{"close": 5000 + i, "reward": 2.5} for i in range(30)],
        },
        dry_run=False,
    )

    assert result["auto_fine_tune"]["triggered"] is True
    assert result["auto_fine_tune"]["executed"] is True
    assert trainer.called is True


def test_real_mode_blocks_mutation_governance(tmp_path: Path) -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(
            risk_profile="balanced",
            max_risk_percent=1.0,
            drawdown_kill_percent=8.0,
            agent_styles={"risk": "r"},
        ),
        regime_history=[{"label": "RANGING"}],
        emotional_twin=None,
        decision_log=None,
    )
    agent = SelfEvolutionMetaAgent(
        engine=cast(Any, engine),
        valuation_engine=ValuationEngine(),
        risk_controller=HardRiskController(RiskLimits(enforce_session_guard=False), enforce_rules=True),
        approval_required=False,
        runtime_mode="real",
        sim_mode=False,
    )

    result = agent.run_nightly_evolution(
        nightly_report={
            "trades": 80,
            "wins": 44,
            "net_pnl": 120.0,
            "sharpe": 0.3,
        },
        dry_run=False,
    )

    assert result["governance"]["mode"] == "real"
    assert result["governance"]["mutation_allowed"] is False
