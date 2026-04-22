from __future__ import annotations

import inspect
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from lumina_core.evolution.simulator_data_support import (
    coerce_rl_training_bars,
    enrich_nightly_report_simulator_data,
)

from .agent_blackboard import AgentBlackboard
from .self_evolution_meta_agent import SelfEvolutionMetaAgent


@dataclass(slots=True)
class MetaAgentOrchestrator:
    """Coordinates nightly reflection and evolution through the blackboard."""

    blackboard: AgentBlackboard
    self_evolution_agent: SelfEvolutionMetaAgent
    ppo_trainer: Any | None = None
    bible_engine: Any | None = None

    def run_nightly_reflection(
        self,
        *,
        nightly_report: dict[str, Any],
        dry_run: bool = False,
    ) -> dict[str, Any]:
        reflection = self._build_24h_reflection(nightly_report=nightly_report)
        hyperparameter_updates = self._propose_hyperparameter_updates(reflection)
        should_retrain = self._should_retrain(reflection)

        self.blackboard.publish_sync(
            topic="meta.reflection",
            producer="meta_agent_orchestrator",
            payload=reflection,
            confidence=float(reflection.get("reflection_confidence", 0.8)),
        )
        self.blackboard.publish_sync(
            topic="meta.hyperparameters",
            producer="meta_agent_orchestrator",
            payload=hyperparameter_updates,
            confidence=0.85,
        )

        evolution_engine = getattr(self.self_evolution_agent, "engine", None)
        if should_retrain and not dry_run and self.ppo_trainer is not None and hasattr(self.ppo_trainer, "train"):
            try:
                train_report = dict(nightly_report)
                enrich_nightly_report_simulator_data(train_report, evolution_engine)
                sig = inspect.signature(self.ppo_trainer.train)
                params = list(sig.parameters.keys())
                if params and params[0] == "simulator_data":
                    bars = coerce_rl_training_bars(
                        evolution_engine,
                        train_report.get("simulator_data"),
                        nightly_context=train_report,
                    )
                    self.ppo_trainer.train(bars, total_timesteps=50000)
                else:
                    self.ppo_trainer.train(total_timesteps=50000)
                retrain_result = {"triggered": True, "executed": True, "reason": "nightly_drift_or_underperformance"}
            except Exception as exc:
                retrain_result = {"triggered": True, "executed": False, "reason": f"train_failed:{exc}"}
        else:
            retrain_result = {
                "triggered": bool(should_retrain),
                "executed": False,
                "reason": "dry_run" if dry_run else "not_required",
            }

        self.blackboard.publish_sync(
            topic="meta.retraining",
            producer="meta_agent_orchestrator",
            payload=retrain_result,
            confidence=0.8,
        )

        bible_update = self._build_bible_update(reflection)
        if bible_update and self.bible_engine is not None and hasattr(self.bible_engine, "evolve"):
            try:
                self.bible_engine.evolve(bible_update)
            except Exception:
                pass

        if bible_update:
            self.blackboard.publish_sync(
                topic="meta.bible_update",
                producer="meta_agent_orchestrator",
                payload=bible_update,
                confidence=0.82,
            )

        merged_report = dict(nightly_report)
        merged_report["meta_reflection"] = reflection
        merged_report["meta_hyperparameter_updates"] = hyperparameter_updates
        merged_report["meta_retraining"] = retrain_result

        enrich_nightly_report_simulator_data(merged_report, evolution_engine)

        evolution_result = self.self_evolution_agent.run_nightly_evolution(
            nightly_report=merged_report,
            dry_run=dry_run,
        )
        dna_payload = evolution_result.get("dna", {}) if isinstance(evolution_result.get("dna"), dict) else {}
        active_dna = dna_payload.get("active", {}) if isinstance(dna_payload.get("active"), dict) else {}
        candidate_dna = dna_payload.get("candidate", {}) if isinstance(dna_payload.get("candidate"), dict) else {}
        dna_lineage_payload = {
            "active_hash": str(active_dna.get("hash", "")),
            "active_version": str(active_dna.get("version", "")),
            "candidate_hash": str(candidate_dna.get("hash", "")),
            "candidate_version": str(candidate_dna.get("version", "")),
            "lineage_hash": str(active_dna.get("lineage_hash") or candidate_dna.get("lineage_hash") or ""),
            "evolution_status": str(evolution_result.get("status", "unknown")),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.blackboard.publish_sync(
            topic="meta.evolution_result",
            producer="meta_agent_orchestrator",
            payload={
                "status": str(evolution_result.get("status", "unknown")),
                "proposal": dict(evolution_result.get("proposal", {})),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            metadata={
                "dna_lineage": dict(dna_lineage_payload),
            },
            confidence=0.85,
        )
        self.blackboard.publish_sync(
            topic="meta.dna_lineage",
            producer="meta_agent_orchestrator",
            payload=dna_lineage_payload,
            confidence=0.84,
        )

        return {
            "reflection": reflection,
            "hyperparameter_updates": hyperparameter_updates,
            "retraining": retrain_result,
            "bible_update": bible_update,
            "evolution": evolution_result,
        }

    def _build_24h_reflection(self, *, nightly_report: dict[str, Any]) -> dict[str, Any]:
        events = self.blackboard.history("execution.aggregate", limit=2000, within_hours=24)
        confidences = [float(e.confidence) for e in events]
        aggregate_conf = sum(confidences) / len(confidences) if confidences else 0.0

        wins = 0
        trades = 0
        pnl = 0.0
        for event in events:
            payload = event.payload if isinstance(event.payload, dict) else {}
            if payload.get("executed") is True:
                trades += 1
            if float(payload.get("pnl", 0.0) or 0.0) > 0:
                wins += 1
            pnl += float(payload.get("pnl", 0.0) or 0.0)

        win_rate = (wins / trades) if trades > 0 else float(nightly_report.get("winrate", 0.0) or 0.0)
        net_pnl = pnl if trades > 0 else float(nightly_report.get("net_pnl", 0.0) or 0.0)
        sharpe = float(nightly_report.get("mean_worker_sharpe", nightly_report.get("sharpe", 0.0)) or 0.0)

        return {
            "window_hours": 24,
            "events_observed": len(events),
            "avg_aggregate_confidence": round(aggregate_conf, 4),
            "win_rate": round(win_rate, 4),
            "net_pnl": round(net_pnl, 4),
            "sharpe": round(sharpe, 4),
            "reflection_confidence": 0.9 if len(events) >= 20 else 0.75,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _propose_hyperparameter_updates(reflection: dict[str, Any]) -> dict[str, Any]:
        sharpe = float(reflection.get("sharpe", 0.0) or 0.0)
        win_rate = float(reflection.get("win_rate", 0.0) or 0.0)

        if sharpe < 0.3 or win_rate < 0.45:
            return {
                "risk_adjustment": "decrease",
                "max_risk_percent_multiplier": 0.9,
                "rl_confidence_threshold": 0.8,
            }
        if sharpe > 1.2 and win_rate > 0.55:
            return {
                "risk_adjustment": "increase",
                "max_risk_percent_multiplier": 1.05,
                "rl_confidence_threshold": 0.76,
            }
        return {
            "risk_adjustment": "keep",
            "max_risk_percent_multiplier": 1.0,
            "rl_confidence_threshold": 0.78,
        }

    @staticmethod
    def _should_retrain(reflection: dict[str, Any]) -> bool:
        win_rate = float(reflection.get("win_rate", 0.0) or 0.0)
        sharpe = float(reflection.get("sharpe", 0.0) or 0.0)
        avg_conf = float(reflection.get("avg_aggregate_confidence", 0.0) or 0.0)
        return bool(win_rate < 0.45 or sharpe < 0.2 or avg_conf < 0.7)

    @staticmethod
    def _build_bible_update(reflection: dict[str, Any]) -> dict[str, Any]:
        return {
            "last_reflection": (
                f"{datetime.now(timezone.utc).date()} | "
                f"win_rate={float(reflection.get('win_rate', 0.0)):.2%}, "
                f"net_pnl={float(reflection.get('net_pnl', 0.0)):.2f}, "
                f"sharpe={float(reflection.get('sharpe', 0.0)):.2f}"
            ),
            "meta_learning": {
                "avg_aggregate_confidence": float(reflection.get("avg_aggregate_confidence", 0.0) or 0.0),
                "events_observed": int(reflection.get("events_observed", 0) or 0),
            },
        }
