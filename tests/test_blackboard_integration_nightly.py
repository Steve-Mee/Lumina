from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from lumina_core.engine.agent_blackboard import AgentBlackboard
from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.meta_agent_orchestrator import MetaAgentOrchestrator


class _NoOpSelfEvolution:
    def run_nightly_evolution(self, *, nightly_report, dry_run):
        return {
            "status": "proposed",
            "proposal": {
                "confidence": 90.0,
                "would_auto_apply": False,
            },
            "nightly_report": nightly_report,
            "dry_run": dry_run,
        }


def test_real_fail_closed_on_low_aggregate_confidence(tmp_path: Path) -> None:
    from lumina_core.engine.engine_config import EngineConfig

    cfg = EngineConfig()
    cfg.trade_mode = "real"
    engine = cast(Any, LuminaEngine)(config=cfg)

    bus = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    engine.bind_blackboard(bus)

    bus.publish_sync(
        topic="execution.aggregate",
        producer="test",
        payload={"signal": "BUY", "confluence_score": 0.55},
        confidence=0.55,
    )

    snapshot = engine.get_current_dream_snapshot()
    assert snapshot.get("signal") == "HOLD"
    assert snapshot.get("why_no_trade") == "fail_closed_low_blackboard_confidence"


def test_nightly_integration_emits_meta_topics(tmp_path: Path) -> None:
    bus = AgentBlackboard(persistence_path=tmp_path / "blackboard.jsonl")
    orchestrator = cast(Any, MetaAgentOrchestrator)(
        blackboard=bus,
        self_evolution_agent=cast(Any, _NoOpSelfEvolution()),
        ppo_trainer=None,
        bible_engine=SimpleNamespace(evolve=lambda *_a, **_k: None),
    )

    orchestrator.run_nightly_reflection(
        nightly_report={"trades": 10, "wins": 6, "net_pnl": 100.0, "mean_worker_sharpe": 0.9},
        dry_run=True,
    )

    assert bus.latest("meta.reflection") is not None
    assert bus.latest("meta.evolution_result") is not None
