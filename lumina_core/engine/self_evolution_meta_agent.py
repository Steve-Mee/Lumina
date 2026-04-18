from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..evolution.dna_registry import DNARegistry, PolicyDNA
from ..evolution.evolution_guard import EvolutionGuard
from ..evolution.evolution_orchestrator import EvolutionOrchestrator
from ..evolution.genetic_operators import calculate_fitness, crossover, mutate_prompt
from .lumina_engine import LuminaEngine
from .evolution_lifecycle import EvolutionLifecycleManager
from .errors import ErrorSeverity, LuminaError
from .risk_controller import HardRiskController
from .valuation_engine import ValuationEngine
from lumina_core.experiments.ab_framework import ABExperimentFramework


@dataclass(slots=True)
class SelfEvolutionMetaAgent:
    """Nightly self-evolution orchestrator for Lumina v50.

    Safety contract:
    - Never disables or bypasses RiskController.
    - Auto-apply is blocked when risk enforcement is not active.
    - All decisions are append-only logged with hash chaining.
    """

    engine: LuminaEngine
    valuation_engine: ValuationEngine
    risk_controller: HardRiskController | None
    enabled: bool = True
    approval_required: bool = True
    sim_mode: bool = False
    aggressive_evolution: bool = False
    max_mutation_depth: str = "conservative"
    log_path: Path = field(default_factory=lambda: Path("state/evolution_log.jsonl"))
    obs_service: Any | None = None  # Optional ObservabilityService; injected at runtime
    auto_fine_tuning_enabled: bool = True
    min_acceptance_rate: float = 0.4
    drift_threshold: float = 0.25
    ppo_trainer: Any | None = None
    rl_environment: Any | None = None
    lifecycle_manager: EvolutionLifecycleManager | None = None
    blackboard: Any | None = None
    dna_registry: DNARegistry | None = None
    runtime_mode: str = "real"
    evolution_guard: EvolutionGuard | None = None

    @classmethod
    def from_container(
        cls,
        *,
        container: Any,
        enabled: bool = True,
        approval_required: bool = True,
        mode: str = "real",
        aggressive_evolution: bool = False,
        max_mutation_depth: str = "conservative",
        obs_service: Any | None = None,
        fine_tuning_cfg: dict[str, Any] | None = None,
    ) -> "SelfEvolutionMetaAgent":
        engine = getattr(container, "engine", None)
        if engine is None:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_ENGINE_MISSING",
                message="ApplicationContainer-like object must expose .engine",
            )

        valuation_engine = getattr(container, "valuation_engine", None)
        if not isinstance(valuation_engine, ValuationEngine):
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_VALUATION_ENGINE_MISSING",
                message="Container must expose .valuation_engine as ValuationEngine instance.",
            )

        risk_controller = getattr(container, "risk_controller", None)
        if risk_controller is None:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_RISK_CONTROLLER_MISSING",
                message="Container must expose .risk_controller.",
            )

        if not isinstance(fine_tuning_cfg, dict):
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_FINE_TUNING_CONFIG_MISSING",
                message="fine_tuning_cfg must be an explicit dict in dev-only runtime.",
            )
        ft_cfg = fine_tuning_cfg

        mode_key = str(mode).strip().lower()
        if mode_key not in {"sim", "paper", "real"}:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_MODE_INVALID",
                message=f"Unsupported evolution mode: {mode_key}",
            )

        return cls(
            engine=engine,
            valuation_engine=valuation_engine,
            risk_controller=risk_controller,
            enabled=enabled,
            approval_required=bool(False if mode_key == "sim" else approval_required),
            sim_mode=bool(mode_key == "sim"),
            aggressive_evolution=bool(aggressive_evolution or mode_key == "sim"),
            max_mutation_depth=str(max_mutation_depth).strip().lower(),
            obs_service=obs_service,
            auto_fine_tuning_enabled=bool(ft_cfg["auto_trigger"]),
            min_acceptance_rate=float(ft_cfg["min_acceptance"]),
            drift_threshold=float(ft_cfg["drift_threshold"]),
            ppo_trainer=getattr(container, "ppo_trainer"),
            rl_environment=getattr(container, "rl_environment"),
            blackboard=getattr(container, "blackboard"),
            runtime_mode=mode_key,
        )

    def run_nightly_evolution(self, *, nightly_report: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        nightly_report = self._hydrate_report_from_blackboard(dict(nightly_report))
        if not self.enabled:
            result = {
                "status": "disabled",
                "timestamp": now.isoformat(),
                "dry_run": dry_run,
            }
            self._append_immutable_log(result)
            return result

        meta_review = self._meta_review(nightly_report)
        mode_key = self._runtime_mode_key()
        guard = self.evolution_guard or EvolutionGuard()
        self.evolution_guard = guard
        mutation_allowed = guard.can_mutate(mode=mode_key)

        active_dna = self._register_active_dna(nightly_report=nightly_report, meta_review=meta_review)
        top_dna = self._top_ranked_dna(active_dna=active_dna)
        fine_tune_trigger = self._auto_fine_tuning_trigger(meta_review=meta_review)
        fine_tune_result = (
            self._execute_auto_fine_tune(nightly_report, dry_run=dry_run)
            if fine_tune_trigger["triggered"]
            else {
                "triggered": False,
                "executed": False,
                "reason": fine_tune_trigger["reason"],
            }
        )
        champion = self._current_champion()
        if fine_tune_result.get("executed") and fine_tune_result.get("champion_candidate"):
            champion = dict(fine_tune_result["champion_candidate"])
        challengers = self._build_challengers(champion, meta_review) if mutation_allowed else []
        genetic_candidates, genetic_candidate_map = (
            self._build_genetic_candidates(
                champion=champion,
                top_dna=top_dna,
                nightly_report=nightly_report,
                meta_review=meta_review,
            )
            if mutation_allowed
            else ([], {})
        )
        candidate_pool = challengers + genetic_candidates
        scored = [
            self._score_challenger(champion, candidate, nightly_report, meta_review) for candidate in candidate_pool
        ]

        ab_result: dict[str, Any] | None = None
        if self.sim_mode and mutation_allowed and candidate_pool:
            ab_framework = ABExperimentFramework(min_forks=5, max_forks=10, max_workers=10)
            base_candidate = dict(candidate_pool[0])
            experiment = ab_framework.run_auto_forks(
                base_agent=base_candidate,
                score_fn=lambda fork: self._score_challenger(champion, fork, nightly_report, meta_review),
                promote_fn=self._apply_candidate,
                seed=int(now.timestamp()),
                candidate_pool=candidate_pool,
            )
            scored = list(experiment.variants)
            ab_result = {
                "experiment_id": str(experiment.experiment_id),
                "selected_variant": dict(experiment.selected_variant),
                "variant_count": len(experiment.variants),
                "genetic_candidates": len(genetic_candidates),
            }

        best = max(scored, key=lambda item: float(item.get("score", 0.0))) if scored else None
        candidate_dna = None
        if isinstance(best, dict):
            candidate_dna = genetic_candidate_map.get(str(best.get("dna_hash", "")))
        if candidate_dna is None and mutation_allowed:
            candidate_dna = self._register_candidate_dna(
                active_dna=active_dna,
                best=best,
                nightly_report=nightly_report,
                meta_review=meta_review,
            )

        confidence = float(best.get("confidence", 0.0)) if best else 0.0
        backtest_green = self._backtest_green(nightly_report)
        safety_ok = self._safety_contract_ok()
        stability_gate = bool(float(meta_review.get("win_rate", 0.0) or 0.0) >= 0.45)
        realism_gate = bool(float(meta_review.get("emotional_twin_accuracy", 0.0) or 0.0) >= 0.4)
        consistency_gate = bool(float(meta_review.get("regime_drift", 1.0) or 1.0) <= 0.75)
        external_release_gates = self._external_release_gates_ok()
        shadow_evidence = self._shadow_rollout_evidence_ok()
        gates = {
            "stability": stability_gate,
            "risk": bool(safety_ok),
            "realism": realism_gate,
            "consistency": consistency_gate,
            "backtest_green": bool(backtest_green),
            "external_release_gates": bool(external_release_gates),
            "shadow_evidence": bool(shadow_evidence),
            "live_promotion_eligible": bool(not self.sim_mode),
        }

        current_guard_fitness = float(active_dna.fitness_score) if active_dna is not None else float("-inf")
        candidate_guard_fitness = float(best.get("score", float("-inf"))) if isinstance(best, dict) else float("-inf")
        signed_approval = guard.has_signed_approval(
            confidence=confidence,
            candidate_fitness=candidate_guard_fitness,
            current_fitness=current_guard_fitness,
        )

        forced_sim_apply = bool(self.sim_mode and best is not None)
        baseline_auto_apply = bool(forced_sim_apply or (confidence > 85.0 and backtest_green and safety_ok))
        should_auto_apply = bool(mutation_allowed and baseline_auto_apply and signed_approval)
        approval_blocked = bool(self.approval_required and should_auto_apply)
        promoted_active_dna = self._promote_winning_dna(
            active_dna=active_dna,
            winner_dna=candidate_dna,
            should_promote=bool(should_auto_apply and not approval_blocked and not dry_run),
        )

        promoted_at = now if bool(should_auto_apply and not approval_blocked and not dry_run) else None
        guard_decision = guard.evaluate(
            mode=mode_key,
            confidence=confidence,
            candidate_fitness=candidate_guard_fitness,
            previous_fitness=current_guard_fitness,
            current_hash=active_dna.hash if active_dna is not None else None,
            promoted_at=promoted_at,
            now=now,
        )
        if guard_decision.rollback_required:
            promoted_active_dna = active_dna
            should_auto_apply = False
            approval_blocked = False

        lifecycle = self._build_lifecycle(best=best, gates=gates)
        outcome = {
            "status": "awaiting_human_approval"
            if approval_blocked
            else ("proposed" if not should_auto_apply else "applied"),
            "timestamp": now.isoformat(),
            "dry_run": dry_run,
            "meta_review": meta_review,
            "auto_fine_tune": fine_tune_result,
            "champion": champion,
            "challengers": scored,
            "best_candidate": best,
            "proposal": {
                "confidence": round(confidence, 2),
                "backtest_green": backtest_green,
                "safety_ok": safety_ok,
                "approval_required": self.approval_required,
                "forced_by_sim_mode": forced_sim_apply,
                "sim_live_readiness": "not_live_eligible" if self.sim_mode else "eligible_after_gates",
                "would_auto_apply": should_auto_apply,
                "auto_apply_executed": bool(should_auto_apply and not self.approval_required and not dry_run),
                "signed_approval": bool(signed_approval),
                "mutation_allowed": bool(mutation_allowed),
                "candidate_fitness": round(candidate_guard_fitness, 6)
                if math.isfinite(candidate_guard_fitness)
                else None,
                "current_fitness": round(current_guard_fitness, 6) if math.isfinite(current_guard_fitness) else None,
                "external_release_gates": bool(external_release_gates),
                "shadow_evidence": bool(shadow_evidence),
            },
            "lifecycle": lifecycle,
            "governance": {
                "mode": mode_key,
                "mutation_allowed": bool(guard_decision.mutation_allowed),
                "signed_approval": bool(guard_decision.signed_approval),
                "rollback_triggered": bool(guard_decision.rollback_required),
                "revert_to_hash": guard_decision.revert_to_hash,
            },
        }
        if active_dna is not None or candidate_dna is not None:
            outcome["dna"] = {
                "active": self._dna_summary(promoted_active_dna or active_dna),
                "candidate": self._dna_summary(candidate_dna),
            }
        if top_dna or genetic_candidates:
            outcome["genetic_evolution"] = {
                "top_dna_count": len(top_dna),
                "candidate_count": len(genetic_candidates),
                "promoted_hash": str((promoted_active_dna or active_dna).hash)
                if (promoted_active_dna or active_dna)
                else "",
            }
        if isinstance(ab_result, dict):
            outcome["ab_experiment"] = ab_result

        if should_auto_apply and not self.approval_required and not dry_run and best is not None:
            self._apply_candidate(best)

        # Record proposal to observability metrics (no-op when obs_service is None)
        if self.obs_service is not None:
            best_name = str(best.get("name")) if best else None
            self.obs_service.record_evolution_proposal(
                status=str(outcome.get("status", "unknown")),
                confidence=confidence,
                best_candidate=best_name,
            )

        # Multi-generation orchestrator cycle (runs in sim/paper modes only).
        if mutation_allowed and not dry_run:
            orchestrator = EvolutionOrchestrator()
            sim_duration_hours = int(nightly_report.get("sim_duration_hours", 24) or 24)
            orch_result = orchestrator.run_nightly_evolution_cycle(
                generations=3,
                sim_duration_hours=sim_duration_hours,
                nightly_report=nightly_report,
                blackboard=self.blackboard,
                mode=mode_key,
            )
            outcome["multi_gen_cycle"] = orch_result
            if self.obs_service is not None:
                self.obs_service.record_evolution_proposal(
                    status=f"multi_gen:{orch_result.get('status', 'unknown')}",
                    confidence=float(outcome.get("proposal", {}).get("confidence", 0.0) or 0.0),
                    best_candidate=str(outcome.get("best_candidate", {}).get("name", "unknown")),
                )

        self._append_immutable_log(outcome)
        self._log_agent_decision(
            raw_input={"nightly_report": nightly_report, "dry_run": dry_run},
            raw_output=outcome,
            confidence=float(outcome.get("proposal", {}).get("confidence", 0.0) or 0.0),
            policy_outcome=str(outcome.get("status", "unknown")),
            decision_context_id="nightly_evolution",
            evolution_log_hash=str(outcome.get("hash", "")) if isinstance(outcome, dict) else None,
        )
        if self.blackboard is not None and hasattr(self.blackboard, "add_proposal"):
            self.blackboard.add_proposal(
                topic="agent.meta.proposal",
                producer="self_evolution_meta_agent",
                payload={
                    "status": str(outcome.get("status", "unknown")),
                    "proposal": dict(outcome.get("proposal", {})),
                    "dna": dict(outcome.get("dna", {})) if isinstance(outcome.get("dna"), dict) else {},
                    "timestamp": now.isoformat(),
                },
                confidence=max(
                    0.0, min(1.0, float(outcome.get("proposal", {}).get("confidence", 0.0) or 0.0) / 100.0)
                ),
            )
        return outcome

    def _hydrate_report_from_blackboard(self, report: dict[str, Any]) -> dict[str, Any]:
        if self.blackboard is None or not hasattr(self.blackboard, "history"):
            return report
        if int(report.get("trades", 0) or 0) > 0:
            return report

        try:
            recent = self.blackboard.history("execution.aggregate", limit=2000, within_hours=24)
        except Exception:
            return report

        trades = 0
        wins = 0
        net_pnl = 0.0
        for event in recent:
            payload = event.payload if isinstance(getattr(event, "payload", None), dict) else {}
            if payload.get("executed") is True:
                trades += 1
            pnl = float(payload.get("pnl", 0.0) or 0.0)
            if pnl > 0:
                wins += 1
            net_pnl += pnl

        report.setdefault("trades", trades)
        report.setdefault("wins", wins)
        report.setdefault("net_pnl", net_pnl)
        return report

    def _log_agent_decision(
        self,
        *,
        raw_input: dict[str, Any],
        raw_output: dict[str, Any],
        confidence: float,
        policy_outcome: str,
        decision_context_id: str,
        evolution_log_hash: str | None = None,
    ) -> None:
        decision_log = getattr(self.engine, "decision_log", None)
        if decision_log is None or not hasattr(decision_log, "log_decision"):
            return
        try:
            decision_log.log_decision(
                agent_id="SelfEvolutionMetaAgent",
                raw_input=raw_input,
                raw_output=raw_output,
                confidence=float(confidence),
                policy_outcome=policy_outcome,
                decision_context_id=decision_context_id,
                model_version="self-evolution-v51",
                prompt_hash=hashlib.sha256(
                    json.dumps(raw_input, sort_keys=True, ensure_ascii=True).encode("utf-8")
                ).hexdigest(),
                evolution_log_hash=evolution_log_hash,
                prompt_version="self-evolution-v1",
                policy_version="evolution-lifecycle-v1",
                provider_route=["self-evolution-engine"],
                calibration_factor=1.0,
            )
        except Exception:
            return

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

    def _external_release_gates_ok(self) -> bool:
        golden = Path("state/golden_path_baseline.json")
        slo = Path("state/slo_report.json")
        try:
            if not golden.exists() or not slo.exists():
                return False
            golden_payload = json.loads(golden.read_text(encoding="utf-8"))
            slo_payload = json.loads(slo.read_text(encoding="utf-8"))
            return int(golden_payload.get("return_code", 1)) == 0 and str(slo_payload.get("status", "")).lower() in {
                "ok",
                "pass",
                "green",
            }
        except Exception:
            return False

    def _shadow_rollout_evidence_ok(self) -> bool:
        report = Path("state/validation/shadow_rollout_report.json")
        if not report.exists():
            return False
        try:
            payload = json.loads(report.read_text(encoding="utf-8"))
            return bool(payload.get("ready_for_promotion", False))
        except Exception:
            return False

    def _auto_fine_tuning_trigger(self, *, meta_review: dict[str, Any]) -> dict[str, Any]:
        if not self.auto_fine_tuning_enabled:
            return {
                "triggered": False,
                "reason": "auto fine-tuning disabled",
                "acceptance_rate_3d": 1.0,
                "drift_3d": 0.0,
            }

        acceptance_rate = self._acceptance_rate_3d()
        drift_3d = max(
            float(meta_review.get("rl_drift", 0.0) or 0.0),
            float(meta_review.get("regime_drift", 0.0) or 0.0),
            self._max_drift_3d_from_log(),
        )
        low_acceptance = acceptance_rate < self.min_acceptance_rate
        high_drift = drift_3d > self.drift_threshold
        return {
            "triggered": bool(low_acceptance or high_drift),
            "reason": (
                f"acceptance_rate_3d={acceptance_rate:.3f} < {self.min_acceptance_rate:.3f}"
                if low_acceptance
                else f"drift_3d={drift_3d:.3f} > {self.drift_threshold:.3f}"
                if high_drift
                else "thresholds healthy"
            ),
            "acceptance_rate_3d": round(acceptance_rate, 4),
            "drift_3d": round(drift_3d, 4),
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
                    pass
            if hasattr(trainer, "set_dna_version"):
                try:
                    active = self._dna_registry().get_latest_dna(version="active")
                    trainer.set_dna_version(str(active.hash if active is not None else "GENESIS"))
                except Exception:
                    pass
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
            return {
                "triggered": True,
                "executed": False,
                "reason": f"fine-tune failed: {exc}",
                "trigger_details": trigger,
            }

    def _entries_last_3_days(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=3)
        if not self.log_path.exists():
            return []
        out: list[dict[str, Any]] = []
        try:
            with self.log_path.open("r", encoding="utf-8") as handle:
                for raw in handle:
                    raw = raw.strip()
                    if not raw:
                        continue
                    parsed = json.loads(raw)
                    ts = str(parsed.get("timestamp", ""))
                    if not ts:
                        continue
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    if dt >= cutoff:
                        out.append(parsed)
        except Exception:
            return []
        return out

    def _acceptance_rate_3d(self) -> float:
        entries = self._entries_last_3_days()
        if not entries:
            return 1.0
        accepted = 0
        total = 0
        for item in entries:
            status = str(item.get("status", "")).lower()
            if status in {"proposed", "awaiting_human_approval", "applied", "approved", "auto_applied"}:
                total += 1
                if status in {"applied", "approved", "auto_applied"}:
                    accepted += 1
        return float(accepted / total) if total > 0 else 1.0

    def _max_drift_3d_from_log(self) -> float:
        entries = self._entries_last_3_days()
        max_drift = 0.0
        for item in entries:
            meta_review = item.get("meta_review", {}) if isinstance(item.get("meta_review"), dict) else {}
            max_drift = max(
                max_drift,
                float(meta_review.get("rl_drift", 0.0) or 0.0),
                float(meta_review.get("regime_drift", 0.0) or 0.0),
            )
        return max_drift

    def _meta_review(self, report: dict[str, Any]) -> dict[str, Any]:
        trades = int(report.get("trades", 0) or 0)
        wins = int(report.get("wins", 0) or 0)
        win_rate = float(wins / trades) if trades > 0 else 0.0
        net_pnl = float(report.get("net_pnl", 0.0) or 0.0)
        sharpe = float(report.get("sharpe", 0.0) or 0.0)

        regime_history = list(getattr(self.engine, "regime_history", []) or [])
        regime_drift = self._compute_regime_drift(regime_history)
        rl_drift = self._compute_rl_drift(report)
        emotional_twin_accuracy = self._compute_emotional_twin_accuracy(report)

        return {
            "trades": trades,
            "wins": wins,
            "win_rate": round(win_rate, 4),
            "net_pnl": round(net_pnl, 4),
            "sharpe": round(sharpe, 4),
            "regime_drift": regime_drift,
            "regime_breakdown": self._regime_breakdown(report),
            "rl_drift": rl_drift,
            "emotional_twin_accuracy": emotional_twin_accuracy,
        }

    def _current_champion(self) -> dict[str, Any]:
        cfg = self.engine.config
        return {
            "name": "champion",
            "prompt_fingerprint": self._prompt_fingerprint(),
            "hyperparams": {
                "risk_profile": str(getattr(cfg, "risk_profile", "balanced")),
                "max_risk_percent": float(getattr(cfg, "max_risk_percent", 1.0)),
                "drawdown_kill_percent": float(getattr(cfg, "drawdown_kill_percent", 8.0)),
                "fast_path_threshold": float(
                    getattr(cfg, "rl_confidence_threshold", 0.78) if hasattr(cfg, "rl_confidence_threshold") else 0.78
                ),
            },
        }

    def _build_challengers(self, champion: dict[str, Any], meta_review: dict[str, Any]) -> list[dict[str, Any]]:
        h = dict(champion.get("hyperparams", {}))
        base_threshold = float(h.get("fast_path_threshold", 0.78))
        base_risk = float(h.get("max_risk_percent", 1.0))
        base_dd = float(h.get("drawdown_kill_percent", 8.0))
        weakest_regime = self._weakest_regime(meta_review)

        challengers: list[dict[str, Any]] = [
            {
                "name": "challenger_a",
                "prompt_tweak": f"More conservative under regime drift; prioritize HOLD when confidence split detected in {weakest_regime}.",
                "regime_focus": weakest_regime,
                "hyperparam_suggestion": {
                    "fast_path_threshold": round(min(0.9, base_threshold + 0.04), 3),
                    "max_risk_percent": round(max(0.3, base_risk * 0.9), 3),
                    "drawdown_kill_percent": round(max(2.0, base_dd * 0.95), 3),
                },
            },
            {
                "name": "challenger_b",
                "prompt_tweak": f"Increase trend-following bias when sharpe positive and RL drift low, but only outside weak regime {weakest_regime}.",
                "regime_focus": weakest_regime,
                "hyperparam_suggestion": {
                    "fast_path_threshold": round(max(0.6, base_threshold - 0.03), 3),
                    "max_risk_percent": round(min(2.0, base_risk * 1.05), 3),
                    "drawdown_kill_percent": round(min(15.0, base_dd * 1.02), 3),
                },
            },
            {
                "name": "challenger_c",
                "prompt_tweak": f"Hybrid mode: strict risk gate + adaptive execution latency guard optimized for {weakest_regime}.",
                "regime_focus": weakest_regime,
                "hyperparam_suggestion": {
                    "fast_path_threshold": round(base_threshold, 3),
                    "max_risk_percent": round(base_risk, 3),
                    "drawdown_kill_percent": round(max(2.0, base_dd * 0.98), 3),
                },
            },
        ]

        # SIM mode or aggressive evolution: allow radical mutation family.
        if self.sim_mode or self.aggressive_evolution or self.max_mutation_depth == "radical":
            challengers.extend(
                [
                    {
                        "name": "challenger_radical_indicators",
                        "prompt_tweak": (
                            f"RADICAL MUTATION: add/remove indicators dynamically for {weakest_regime}; "
                            "permit structural feature set changes and aggressively reweight signal stack."
                        ),
                        "regime_focus": weakest_regime,
                        "hyperparam_suggestion": {
                            "fast_path_threshold": round(max(0.5, base_threshold - 0.08), 3),
                            "max_risk_percent": round(min(3.0, base_risk * 1.25), 3),
                            "drawdown_kill_percent": round(min(25.0, base_dd * 1.25), 3),
                        },
                    },
                    {
                        "name": "challenger_radical_prompts",
                        "prompt_tweak": (
                            "RADICAL MUTATION: rewrite confluence rules and prompt scaffolding end-to-end; "
                            "allow hard prompt rewrites and non-linear decision-policy restructuring."
                        ),
                        "regime_focus": weakest_regime,
                        "hyperparam_suggestion": {
                            "fast_path_threshold": round(max(0.45, base_threshold - 0.1), 3),
                            "max_risk_percent": round(min(3.5, base_risk * 1.35), 3),
                            "drawdown_kill_percent": round(min(30.0, base_dd * 1.4), 3),
                        },
                    },
                ]
            )

        return challengers

    def _score_challenger(
        self,
        champion: dict[str, Any],
        challenger: dict[str, Any],
        report: dict[str, Any],
        meta_review: dict[str, Any],
    ) -> dict[str, Any]:
        del champion

        win_rate = float(meta_review.get("win_rate", 0.0))
        sharpe = float(meta_review.get("sharpe", 0.0))
        regime_drift = float(meta_review.get("regime_drift", 0.5))
        rl_drift = float(meta_review.get("rl_drift", 0.5))
        emotional_accuracy = float(meta_review.get("emotional_twin_accuracy", 0.5))
        net_pnl = float(report.get("net_pnl", 0.0) or 0.0)

        quality = (
            (win_rate * 30.0)
            + (max(-1.0, min(2.0, sharpe)) * 8.0)
            + ((1.0 - regime_drift) * 12.0)
            + ((1.0 - rl_drift) * 12.0)
            + (emotional_accuracy * 10.0)
            + (8.0 if net_pnl > 0 else -8.0)
        )

        suggestion = challenger.get("hyperparam_suggestion", {})
        risk_penalty = 0.0
        if float(suggestion.get("max_risk_percent", 1.0)) > float(getattr(self.engine.config, "max_risk_percent", 1.0)):
            risk_penalty += 2.5
        if float(suggestion.get("drawdown_kill_percent", 8.0)) > float(
            getattr(self.engine.config, "drawdown_kill_percent", 8.0)
        ):
            risk_penalty += 2.0

        score = max(0.0, quality - risk_penalty)
        confidence = max(0.0, min(99.0, 50.0 + score))

        out = dict(challenger)
        out["score"] = round(score, 4)
        out["confidence"] = round(confidence, 2)
        out["risk_penalty"] = round(risk_penalty, 2)
        return out

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

    def _apply_candidate(self, candidate: dict[str, Any]) -> None:
        suggestion = dict(candidate.get("hyperparam_suggestion", {}))
        cfg = self.engine.config
        if "max_risk_percent" in suggestion:
            cfg.max_risk_percent = float(suggestion["max_risk_percent"])
        if "drawdown_kill_percent" in suggestion:
            cfg.drawdown_kill_percent = float(suggestion["drawdown_kill_percent"])

    def _dna_registry(self) -> DNARegistry:
        registry = self.dna_registry or DNARegistry()
        self.dna_registry = registry
        return registry

    def _dna_lineage_hash(self) -> str:
        if self.blackboard is None or not hasattr(self.blackboard, "latest"):
            return self._prompt_fingerprint()

        lineage_parts: list[str] = []
        for topic in ("meta.reflection", "meta.hyperparameters", "agent.meta.proposal", "execution.aggregate"):
            try:
                event = self.blackboard.latest(topic)
            except Exception:
                event = None
            if event is None:
                continue
            lineage_parts.append(str(getattr(event, "event_hash", "GENESIS") or "GENESIS"))

        if not lineage_parts:
            return self._prompt_fingerprint()
        return hashlib.sha256("|".join(lineage_parts).encode("utf-8")).hexdigest()

    def _dna_fitness(self, meta_review: dict[str, Any]) -> float:
        return round(
            float(meta_review.get("sharpe", 0.0) or 0.0)
            + float(meta_review.get("win_rate", 0.0) or 0.0)
            + float(meta_review.get("emotional_twin_accuracy", 0.0) or 0.0)
            - float(meta_review.get("regime_drift", 0.0) or 0.0)
            - float(meta_review.get("rl_drift", 0.0) or 0.0),
            6,
        )

    def _top_ranked_dna(self, *, active_dna: PolicyDNA | None) -> list[PolicyDNA]:
        registry = self._dna_registry()
        ranked = registry.get_ranked_dna(limit=3, versions=("active", "candidate"))
        if ranked:
            return ranked
        return [active_dna] if active_dna is not None else []

    def _genetic_fitness(self, nightly_report: dict[str, Any]) -> float:
        fitness = calculate_fitness(
            float(nightly_report.get("net_pnl", 0.0) or 0.0),
            float(nightly_report.get("max_drawdown", 0.0) or 0.0),
            float(nightly_report.get("sharpe", 0.0) or 0.0),
            capital_preservation_threshold=max(
                5000.0,
                float(getattr(self.engine.config, "drawdown_kill_percent", 8.0) or 8.0) * 3000.0,
            ),
        )
        if not math.isfinite(fitness):
            return -1_000_000_000.0
        return round(float(fitness), 6)

    def _build_genetic_candidates(
        self,
        *,
        champion: dict[str, Any],
        top_dna: list[PolicyDNA],
        nightly_report: dict[str, Any],
        meta_review: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, PolicyDNA]]:
        if not top_dna:
            return [], {}

        registry = self._dna_registry()
        weakest_regime = self._weakest_regime(meta_review)
        lineage_hash = self._dna_lineage_hash()
        fitness_score = self._genetic_fitness(nightly_report)
        candidates: list[dict[str, Any]] = []
        candidate_map: dict[str, PolicyDNA] = {}
        mutation_rates = [0.12, 0.18, 0.24, 0.3, 0.36]

        for index, parent in enumerate(top_dna[:3]):
            mutation_rate = mutation_rates[index % len(mutation_rates)]
            mutated_prompt = mutate_prompt(self._prompt_source_from_dna(parent), mutation_rate)
            draft = registry.mutate(
                parent=parent,
                mutation_rate=mutation_rate,
                content={
                    "candidate_name": f"genetic_mutant_{index + 1}",
                    "prompt_tweak": mutated_prompt,
                    "regime_focus": weakest_regime,
                    "hyperparam_suggestion": self._mutated_hyperparams(
                        parent=parent, scale=mutation_rate, champion=champion
                    ),
                },
                fitness_score=fitness_score,
                version="candidate",
                lineage_hash=lineage_hash,
            )
            draft = registry.register_dna(draft)
            candidate = self._candidate_from_dna(draft)
            candidates.append(candidate)
            candidate_map[draft.hash] = draft

        crossover_pairs = [(0, 1), (0, 2), (1, 2)]
        for left_index, right_index in crossover_pairs:
            if left_index >= len(top_dna) or right_index >= len(top_dna):
                continue
            left_parent = top_dna[left_index]
            right_parent = top_dna[right_index]
            crossed_prompt = crossover(left_parent, right_parent)
            draft = registry.mutate(
                parent=left_parent,
                crossover=right_parent,
                mutation_rate=0.22,
                content={
                    "candidate_name": f"genetic_crossover_{left_index + 1}_{right_index + 1}",
                    "prompt_tweak": crossed_prompt,
                    "regime_focus": weakest_regime,
                    "hyperparam_suggestion": self._blended_hyperparams(
                        left_parent=left_parent, right_parent=right_parent, champion=champion
                    ),
                },
                fitness_score=fitness_score,
                version="candidate",
                lineage_hash=lineage_hash,
            )
            draft = registry.register_dna(draft)
            candidate = self._candidate_from_dna(draft)
            candidates.append(candidate)
            candidate_map[draft.hash] = draft

        if len(candidates) < 5 and top_dna:
            filler_parent = top_dna[0]
            while len(candidates) < 5:
                mutation_rate = mutation_rates[len(candidates) % len(mutation_rates)]
                mutated_prompt = mutate_prompt(self._prompt_source_from_dna(filler_parent), mutation_rate)
                draft = registry.mutate(
                    parent=filler_parent,
                    mutation_rate=mutation_rate,
                    content={
                        "candidate_name": f"genetic_filler_{len(candidates) + 1}",
                        "prompt_tweak": mutated_prompt,
                        "regime_focus": weakest_regime,
                        "hyperparam_suggestion": self._mutated_hyperparams(
                            parent=filler_parent, scale=mutation_rate, champion=champion
                        ),
                    },
                    fitness_score=fitness_score,
                    version="candidate",
                    lineage_hash=lineage_hash,
                )
                draft = registry.register_dna(draft)
                candidate = self._candidate_from_dna(draft)
                candidates.append(candidate)
                candidate_map[draft.hash] = draft

        return candidates[:10], candidate_map

    def _promote_winning_dna(
        self,
        *,
        active_dna: PolicyDNA | None,
        winner_dna: PolicyDNA | None,
        should_promote: bool,
    ) -> PolicyDNA | None:
        if not should_promote or winner_dna is None:
            return active_dna
        registry = self._dna_registry()
        promoted = PolicyDNA.create(
            prompt_id=winner_dna.prompt_id,
            version="active",
            content=winner_dna.content,
            fitness_score=winner_dna.fitness_score,
            generation=max(int(winner_dna.generation), int(active_dna.generation) + 1 if active_dna else 1),
            parent_ids=[winner_dna.hash],
            mutation_rate=0.0,
            lineage_hash=self._dna_lineage_hash(),
        )
        return registry.register_dna(promoted)

    def _content_from_dna(self, dna: PolicyDNA) -> dict[str, Any]:
        try:
            payload = json.loads(dna.content)
        except Exception:
            return {"prompt_tweak": dna.content}
        if not isinstance(payload, dict):
            return {"prompt_tweak": dna.content}
        return payload

    def _prompt_source_from_dna(self, dna: PolicyDNA) -> str:
        payload = self._content_from_dna(dna)
        for key in ("prompt_tweak", "candidate_name", "prompt_fingerprint"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return dna.content

    def _normalized_hyperparams(self, dna: PolicyDNA, champion: dict[str, Any]) -> dict[str, float]:
        payload = self._content_from_dna(dna)
        source = payload.get("hyperparam_suggestion") or payload.get("hyperparams") or champion.get("hyperparams", {})
        return {
            "fast_path_threshold": float(
                source.get("fast_path_threshold", source.get("rl_confidence_threshold", 0.78)) or 0.78
            ),
            "max_risk_percent": float(source.get("max_risk_percent", 1.0) or 1.0),
            "drawdown_kill_percent": float(source.get("drawdown_kill_percent", 8.0) or 8.0),
        }

    def _mutated_hyperparams(self, *, parent: PolicyDNA, scale: float, champion: dict[str, Any]) -> dict[str, float]:
        base = self._normalized_hyperparams(parent, champion)
        return {
            "fast_path_threshold": round(max(0.45, min(0.95, base["fast_path_threshold"] + (scale / 4.0))), 3),
            "max_risk_percent": round(max(0.2, min(3.5, base["max_risk_percent"] * (1.0 - (scale / 3.0)))), 3),
            "drawdown_kill_percent": round(
                max(2.0, min(20.0, base["drawdown_kill_percent"] * (1.0 - (scale / 5.0)))), 3
            ),
        }

    def _blended_hyperparams(
        self, *, left_parent: PolicyDNA, right_parent: PolicyDNA, champion: dict[str, Any]
    ) -> dict[str, float]:
        left = self._normalized_hyperparams(left_parent, champion)
        right = self._normalized_hyperparams(right_parent, champion)
        return {
            "fast_path_threshold": round((left["fast_path_threshold"] + right["fast_path_threshold"]) / 2.0, 3),
            "max_risk_percent": round((left["max_risk_percent"] + right["max_risk_percent"]) / 2.0, 3),
            "drawdown_kill_percent": round((left["drawdown_kill_percent"] + right["drawdown_kill_percent"]) / 2.0, 3),
        }

    def _candidate_from_dna(self, dna: PolicyDNA) -> dict[str, Any]:
        payload = self._content_from_dna(dna)
        return {
            "name": str(payload.get("candidate_name", "candidate")),
            "prompt_tweak": str(payload.get("prompt_tweak", self._prompt_source_from_dna(dna))),
            "regime_focus": str(payload.get("regime_focus", "neutral")),
            "hyperparam_suggestion": dict(payload.get("hyperparam_suggestion", {})),
            "dna_hash": dna.hash,
            "dna_generation": dna.generation,
            "mutation_rate": dna.mutation_rate,
        }

    def _register_active_dna(self, *, nightly_report: dict[str, Any], meta_review: dict[str, Any]) -> PolicyDNA | None:
        registry = self._dna_registry()
        if registry.get_latest_dna("active") is None:
            registry.load_from_blackboard(self.blackboard, prompt_id="self_evolution_blackboard", version="bootstrap")

        payload = {
            "prompt_fingerprint": self._prompt_fingerprint(),
            "agent_styles": dict(getattr(self.engine.config, "agent_styles", {}) or {}),
            "hyperparams": dict(self._current_champion().get("hyperparams", {})),
            "nightly_report": {
                "trades": int(nightly_report.get("trades", 0) or 0),
                "wins": int(nightly_report.get("wins", 0) or 0),
                "net_pnl": float(nightly_report.get("net_pnl", 0.0) or 0.0),
                "sharpe": float(nightly_report.get("sharpe", 0.0) or 0.0),
            },
            "meta_review": dict(meta_review),
        }
        previous = registry.get_latest_dna("active")
        generation = 0 if previous is None else int(previous.generation)
        parent_ids = [] if previous is None else [previous.hash]
        dna = PolicyDNA.create(
            prompt_id="self_evolution_policy",
            version="active",
            content=payload,
            fitness_score=self._dna_fitness(meta_review),
            generation=generation,
            parent_ids=parent_ids,
            mutation_rate=0.0,
            lineage_hash=self._dna_lineage_hash(),
        )
        return registry.register_dna(dna)

    def _register_candidate_dna(
        self,
        *,
        active_dna: PolicyDNA | None,
        best: dict[str, Any] | None,
        nightly_report: dict[str, Any],
        meta_review: dict[str, Any],
    ) -> PolicyDNA | None:
        if active_dna is None or best is None:
            return None
        registry = self._dna_registry()
        mutation_rate = 0.35 if self.sim_mode else 0.1
        content = {
            "candidate_name": str(best.get("name", "candidate")),
            "prompt_tweak": str(best.get("prompt_tweak", "")),
            "regime_focus": str(best.get("regime_focus", "neutral")),
            "hyperparam_suggestion": dict(best.get("hyperparam_suggestion", {})),
            "score": float(best.get("score", 0.0) or 0.0),
            "confidence": float(best.get("confidence", 0.0) or 0.0),
            "nightly_report": {
                "trades": int(nightly_report.get("trades", 0) or 0),
                "wins": int(nightly_report.get("wins", 0) or 0),
                "net_pnl": float(nightly_report.get("net_pnl", 0.0) or 0.0),
            },
            "meta_review": dict(meta_review),
        }
        dna = registry.mutate(
            parent=active_dna,
            mutation_rate=mutation_rate,
            content=content,
            fitness_score=self._dna_fitness(meta_review),
            version="candidate",
            lineage_hash=self._dna_lineage_hash(),
        )
        return registry.register_dna(dna)

    @staticmethod
    def _dna_summary(dna: PolicyDNA | None) -> dict[str, Any] | None:
        if dna is None:
            return None
        return {
            "prompt_id": dna.prompt_id,
            "version": dna.version,
            "hash": dna.hash,
            "generation": dna.generation,
            "fitness_score": dna.fitness_score,
            "lineage_hash": dna.lineage_hash,
        }

    def _prompt_fingerprint(self) -> str:
        agent_styles = dict(getattr(self.engine.config, "agent_styles", {}) or {})
        payload = json.dumps(agent_styles, sort_keys=True, ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _compute_regime_drift(regime_history: list[Any]) -> float:
        if not regime_history:
            return 0.5
        normalized = []
        for item in regime_history:
            if isinstance(item, dict):
                normalized.append(str(item.get("label") or item.get("regime") or item).upper())
            else:
                normalized.append(str(item).upper())
        unique = len(set(normalized))
        return min(1.0, unique / max(1.0, len(normalized) * 0.5))

    @staticmethod
    def _regime_breakdown(report: dict[str, Any]) -> dict[str, Any]:
        attribution = report.get("regime_attribution", {})
        if not isinstance(attribution, dict):
            return {}
        return {
            str(regime): {
                "trades": float(stats.get("trades", 0.0) or 0.0),
                "net_pnl": float(stats.get("net_pnl", 0.0) or 0.0),
                "winrate": float(stats.get("winrate", 0.0) or 0.0),
            }
            for regime, stats in attribution.items()
            if isinstance(stats, dict)
        }

    @staticmethod
    def _weakest_regime(meta_review: dict[str, Any]) -> str:
        breakdown = meta_review.get("regime_breakdown", {})
        if not isinstance(breakdown, dict) or not breakdown:
            return "neutral"
        weakest = min(
            breakdown.items(),
            key=lambda item: (float(item[1].get("net_pnl", 0.0)), float(item[1].get("winrate", 0.0))),
        )
        return str(weakest[0]).lower()

    @staticmethod
    def _compute_rl_drift(report: dict[str, Any]) -> float:
        samples = report.get("samples", [])
        if not isinstance(samples, list) or not samples:
            return 0.5
        rewards = [float(item.get("reward", 0.0)) for item in samples if isinstance(item, dict)]
        if not rewards:
            return 0.5
        mean_abs = sum(abs(v) for v in rewards) / len(rewards)
        return max(0.0, min(1.0, mean_abs / 5.0))

    def _compute_emotional_twin_accuracy(self, report: dict[str, Any]) -> float:
        et = getattr(self.engine, "emotional_twin", None)
        if et is not None and hasattr(et, "last_accuracy"):
            try:
                return max(0.0, min(1.0, float(getattr(et, "last_accuracy"))))
            except Exception:
                pass
        wins = int(report.get("wins", 0) or 0)
        trades = int(report.get("trades", 0) or 0)
        if trades <= 0:
            return 0.5
        return max(0.0, min(1.0, wins / trades))

    def _append_immutable_log(self, entry: dict[str, Any]) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        prev_hash = self._last_log_hash()
        payload = dict(entry)
        payload["prev_hash"] = prev_hash
        payload["log_version"] = "v1"
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
        payload_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        payload["hash"] = payload_hash
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _last_log_hash(self) -> str:
        if not self.log_path.exists():
            return "GENESIS"
        try:
            with self.log_path.open("r", encoding="utf-8") as handle:
                lines = [line.strip() for line in handle if line.strip()]
            if not lines:
                return "GENESIS"
            last = json.loads(lines[-1])
            return str(last.get("hash", "GENESIS"))
        except Exception:
            return "GENESIS"


def load_evolution_config(config_path: str = "config.yaml") -> dict[str, Any]:
    import yaml

    if not os.path.exists(config_path):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="EVOLUTION_CONFIG_FILE_MISSING",
            message=f"Required evolution config file not found: {config_path}",
        )

    with open(config_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    if not isinstance(data, dict):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="EVOLUTION_CONFIG_INVALID",
            message="Top-level config.yaml payload must be a mapping.",
        )

    evo = data.get("evolution")
    fine_tuning = data.get("fine_tuning")
    sim_cfg = data.get("sim")
    real_cfg = data.get("real")
    if not isinstance(evo, dict) or not isinstance(fine_tuning, dict):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="EVOLUTION_CONFIG_SECTIONS_MISSING",
            message="Config requires 'evolution' and 'fine_tuning' mapping sections.",
        )
    if not isinstance(sim_cfg, dict) or not isinstance(real_cfg, dict):
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="EVOLUTION_MODE_CONFIG_MISSING",
            message="Config requires both 'sim' and 'real' mapping sections.",
        )

    mode = str(os.getenv("LUMINA_MODE", data["mode"]))
    mode = mode.strip().lower()
    if mode not in {"sim", "paper", "real"}:
        raise LuminaError(
            severity=ErrorSeverity.FATAL_MODE_VIOLATION,
            code="EVOLUTION_MODE_INVALID",
            message=f"Unsupported mode in evolution config: {mode}",
        )

    mode_cfg = sim_cfg if mode == "sim" else real_cfg
    return {
        "enabled": bool(evo["enabled"]),
        "approval_required": bool(mode_cfg["approval_required"]),
        "mode": mode,
        "aggressive_evolution": bool(mode_cfg["aggressive_evolution"]),
        "max_mutation_depth": str(mode_cfg["max_mutation_depth"]),
        "fine_tuning": {
            "auto_trigger": bool(fine_tuning["auto_trigger"]),
            "min_acceptance": float(fine_tuning["min_acceptance"]),
            "drift_threshold": float(fine_tuning["drift_threshold"]),
        },
    }
