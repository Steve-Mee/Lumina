"""Nightly lifecycle + auto fine-tune helpers for SelfEvolutionMetaAgent."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any

from lumina_core.agent_orchestration.schemas import (
    TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,
    TradingEngineExecutionAggregate,
    typed_payload_from_event,
)
from .evolution_lifecycle import EvolutionLifecycleManager
from .errors import ErrorSeverity, LuminaError

logger = logging.getLogger(__name__)


class MetaAgentNightlyMixin:
    """Lifecycle build + auto fine-tune methods mixed into SelfEvolutionMetaAgent."""

    __slots__ = ()

    def _hydrate_report_from_blackboard(self, report: dict[str, Any]) -> dict[str, Any]:
        if int(report.get("trades", 0) or 0) > 0:
            return report

        recent: list[Any] = []
        event_bus = getattr(self.engine, "event_bus", None)
        if event_bus is not None and hasattr(event_bus, "history_within_hours"):
            try:
                recent = event_bus.history_within_hours(
                    TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC,
                    within_hours=24,
                    limit=2000,
                )
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/engine/meta_agent_core.py:491")
                return report
        else:
            return report

        trades = 0
        wins = 0
        net_pnl = 0.0
        for event in recent:
            try:
                agg = typed_payload_from_event(event, TradingEngineExecutionAggregate)
            except Exception:
                continue
            if agg.executed is True:
                trades += 1
            pnl = float(agg.pnl or 0.0)
            if pnl > 0:
                wins += 1
            net_pnl += pnl

        report.setdefault("trades", trades)
        report.setdefault("wins", wins)
        report.setdefault("net_pnl", net_pnl)
        return report

    def _build_lifecycle(self, *, best: dict[str, Any] | None, gates: dict[str, bool]) -> dict[str, Any]:
        manager = self.lifecycle_manager or EvolutionLifecycleManager()
        self.lifecycle_manager = manager
        parent_id = self._prompt_fingerprint()
        metadata = {
            "best_candidate": str(best.get("name", "none")) if isinstance(best, dict) else "none",
            "max_mutation_depth": str(self.max_mutation_depth),
            "sim_mode": bool(self.sim_mode),
            "live_readiness": "not_live_eligible" if self.sim_mode else "eligible_after_gates",
        }
        version_id = manager.create_version(parent_version_id=parent_id, metadata=metadata)
        transitions: list[dict[str, Any]] = []

        transitions.append(
            manager.transition(
                version_id=version_id,
                state="shadow",
                parent_version_id=parent_id,
                metadata=metadata,
                gates=gates,
            )
        )

        if all(bool(v) for v in gates.values()):
            transitions.append(
                manager.transition(
                    version_id=version_id,
                    state="canary",
                    parent_version_id=parent_id,
                    metadata=metadata,
                    gates=gates,
                )
            )
            transitions.append(
                manager.transition(
                    version_id=version_id,
                    state="promoted",
                    parent_version_id=parent_id,
                    metadata=metadata,
                    gates=gates,
                )
            )
            current_state = "promoted"
        else:
            transitions.append(
                manager.transition(
                    version_id=version_id,
                    state="quarantined",
                    parent_version_id=parent_id,
                    metadata=metadata,
                    gates=gates,
                )
            )
            transitions.append(
                manager.transition(
                    version_id=version_id,
                    state="rolled_back",
                    parent_version_id=parent_id,
                    metadata=metadata,
                    gates=gates,
                )
            )
            current_state = "rolled_back"

        return {
            "version_id": version_id,
            "parent_version_id": parent_id,
            "state": current_state,
            "gates": gates,
            "transitions": transitions,
        }

    def _execute_auto_fine_tune(self, nightly_report: dict[str, Any], *, dry_run: bool) -> dict[str, Any]:
        trigger = self._auto_fine_tuning_trigger(meta_review=self._meta_review(nightly_report))
        if not trigger.get("triggered"):
            return {"triggered": False, "executed": False, "reason": trigger.get("reason", "no-trigger")}

        data = nightly_report.get("simulator_data")
        if not isinstance(data, list) or not data:
            data = nightly_report.get("samples") if isinstance(nightly_report.get("samples"), list) else []

        if not isinstance(data, list) or not data:
            return {
                "triggered": True,
                "executed": False,
                "reason": "no training data available",
                "trigger_details": trigger,
            }

        if dry_run:
            return {
                "triggered": True,
                "executed": False,
                "reason": "dry_run",
                "trigger_details": trigger,
                "champion_candidate": {
                    "name": "champion_finetuned_dry_run",
                    "source": "ppo_fine_tune",
                },
            }

        trainer = self.ppo_trainer or getattr(self.engine, "ppo_trainer", None)
        if trainer is None or not hasattr(trainer, "train"):
            return {
                "triggered": True,
                "executed": False,
                "reason": "ppo_trainer unavailable",
                "trigger_details": trigger,
            }

        try:
            if self.rl_environment is not None:
                try:
                    setattr(self.engine, "rl_env", self.rl_environment)
                except Exception:
                    logger.exception("SelfEvolutionMetaAgent failed to attach rl_env to engine")
            if hasattr(trainer, "set_dna_version"):
                try:
                    active = self._dna_registry().get_latest_dna(version="active")
                    trainer.set_dna_version(str(active.hash if active is not None else "GENESIS"))
                except Exception:
                    logger.exception("SelfEvolutionMetaAgent failed to set trainer DNA version")
            policy_path = trainer.train(data, total_timesteps=50_000)
            champion_candidate = {
                "name": f"champion_finetuned_{datetime.now(timezone.utc).strftime('%Y%m%d')}",
                "source": "ppo_fine_tune",
                "policy_path": str(policy_path),
                "trigger": trigger,
            }
            return {
                "triggered": True,
                "executed": True,
                "reason": trigger.get("reason", "triggered"),
                "policy_path": str(policy_path),
                "champion_candidate": champion_candidate,
                "trigger_details": trigger,
            }
        except Exception as exc:
            logging.exception("Unhandled broad exception fallback in lumina_core/engine/meta_agent_core.py:742")
            return {
                "triggered": True,
                "executed": False,
                "reason": f"fine-tune failed: {exc}",
                "trigger_details": trigger,
            }

    def _backtest_green(self, report: dict[str, Any]) -> bool:
        trades = int(report.get("trades", 0) or 0)
        wins = int(report.get("wins", 0) or 0)
        win_rate = (wins / trades) if trades > 0 else 0.0
        net_pnl = float(report.get("net_pnl", 0.0) or 0.0)
        sharpe = float(report.get("sharpe", 0.0) or 0.0)
        return bool(trades >= 50 and win_rate >= 0.45 and net_pnl > 0 and sharpe >= 0.2)

    def _safety_contract_ok(self) -> bool:
        # SIM mode intentionally allows unconstrained evolution experimentation.
        if self.sim_mode:
            return True
        if self.risk_controller is None:
            return False
        if not bool(getattr(self.risk_controller, "enforce_rules", False)):
            return False
        return True

    def _runtime_mode_key(self) -> str:
        if self.sim_mode:
            return "sim"
        mode = str(self.runtime_mode).strip().lower()
        if mode in {"sim", "paper", "real"}:
            return mode
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="EVOLUTION_RUNTIME_MODE_INVALID",
            message=f"Unsupported runtime mode: {mode}",
        )

    def _dna_lineage_hash(self) -> str:
        if self.blackboard is None or not hasattr(self.blackboard, "latest"):
            return self._prompt_fingerprint()

        lineage_parts: list[str] = []
        exec_topic = TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC
        for topic in ("meta.reflection", "meta.hyperparameters", "agent.meta.proposal", exec_topic):
            event = None
            try:
                if topic == exec_topic:
                    eb = getattr(self.engine, "event_bus", None)
                    if eb is not None and hasattr(eb, "latest"):
                        event = eb.latest(exec_topic)
                else:
                    event = self.blackboard.latest(topic)
            except Exception:
                logging.exception("Unhandled broad exception fallback in lumina_core/engine/meta_agent_core.py:1054")
                event = None
            if event is None:
                continue
            ev_hash = getattr(event, "event_hash", None)
            if not ev_hash and hasattr(event, "to_dict"):
                ev_hash = hashlib.sha256(
                    json.dumps(event.to_dict(), sort_keys=True, default=str).encode("utf-8")
                ).hexdigest()
            lineage_parts.append(str(ev_hash or "GENESIS"))

        if not lineage_parts:
            return self._prompt_fingerprint()
        return hashlib.sha256("|".join(lineage_parts).encode("utf-8")).hexdigest()


__all__ = ["MetaAgentNightlyMixin"]
