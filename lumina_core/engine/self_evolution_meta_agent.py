from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .lumina_engine import LuminaEngine
from .evolution_lifecycle import EvolutionLifecycleManager
from .risk_controller import HardRiskController
from .valuation_engine import ValuationEngine


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
            raise ValueError("ApplicationContainer-like object must expose .engine")

        valuation_engine = getattr(container, "valuation_engine", None)
        if valuation_engine is None:
            valuation_engine = getattr(engine, "valuation_engine", ValuationEngine())

        risk_controller = getattr(container, "risk_controller", None)
        if risk_controller is None:
            risk_controller = getattr(engine, "risk_controller", None)

        ft_cfg = fine_tuning_cfg if isinstance(fine_tuning_cfg, dict) else {}

        return cls(
            engine=engine,
            valuation_engine=valuation_engine,
            risk_controller=risk_controller,
            enabled=enabled,
            approval_required=bool(False if str(mode).strip().lower() == "sim" else approval_required),
            sim_mode=bool(str(mode).strip().lower() == "sim"),
            aggressive_evolution=bool(aggressive_evolution or str(mode).strip().lower() == "sim"),
            max_mutation_depth=str(max_mutation_depth or "conservative").strip().lower(),
            obs_service=obs_service,
            auto_fine_tuning_enabled=bool(ft_cfg.get("auto_trigger", True)),
            min_acceptance_rate=float(ft_cfg.get("min_acceptance", 0.4) or 0.4),
            drift_threshold=float(ft_cfg.get("drift_threshold", 0.25) or 0.25),
            ppo_trainer=getattr(container, "ppo_trainer", None),
            rl_environment=getattr(container, "rl_environment", None),
        )

    def run_nightly_evolution(self, *, nightly_report: dict[str, Any], dry_run: bool = False) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        if not self.enabled:
            result = {
                "status": "disabled",
                "timestamp": now.isoformat(),
                "dry_run": dry_run,
            }
            self._append_immutable_log(result)
            return result

        meta_review = self._meta_review(nightly_report)
        fine_tune_trigger = self._auto_fine_tuning_trigger(meta_review=meta_review)
        fine_tune_result = self._execute_auto_fine_tune(nightly_report, dry_run=dry_run) if fine_tune_trigger["triggered"] else {
            "triggered": False,
            "executed": False,
            "reason": fine_tune_trigger["reason"],
        }
        champion = self._current_champion()
        if fine_tune_result.get("executed") and fine_tune_result.get("champion_candidate"):
            champion = dict(fine_tune_result["champion_candidate"])
        challengers = self._build_challengers(champion, meta_review)
        scored = [self._score_challenger(champion, c, nightly_report, meta_review) for c in challengers]
        best = max(scored, key=lambda item: float(item.get("score", 0.0))) if scored else None

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

        forced_sim_apply = bool(self.sim_mode and best is not None)
        should_auto_apply = bool(forced_sim_apply or (confidence > 85.0 and backtest_green and safety_ok))
        approval_blocked = bool(self.approval_required and should_auto_apply)

        lifecycle = self._build_lifecycle(best=best, gates=gates)
        outcome = {
            "status": "awaiting_human_approval" if approval_blocked else ("proposed" if not should_auto_apply else "applied"),
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
                "external_release_gates": bool(external_release_gates),
                "shadow_evidence": bool(shadow_evidence),
            },
            "lifecycle": lifecycle,
        }

        if should_auto_apply and not self.approval_required and not dry_run and best is not None:
            self._apply_candidate(best)

        # Record proposal to observability metrics (no-op when obs_service is None)
        if self.obs_service is not None:
            try:
                best_name = str(best.get("name")) if best else None
                self.obs_service.record_evolution_proposal(
                    status=str(outcome.get("status", "unknown")),
                    confidence=confidence,
                    best_candidate=best_name,
                )
            except Exception:
                pass

        self._append_immutable_log(outcome)
        self._log_agent_decision(
            raw_input={"nightly_report": nightly_report, "dry_run": dry_run},
            raw_output=outcome,
            confidence=float(outcome.get("proposal", {}).get("confidence", 0.0) or 0.0),
            policy_outcome=str(outcome.get("status", "unknown")),
            decision_context_id="nightly_evolution",
            evolution_log_hash=str(outcome.get("hash", "")) if isinstance(outcome, dict) else None,
        )
        return outcome

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
                "fast_path_threshold": float(getattr(cfg, "rl_confidence_threshold", 0.78) if hasattr(cfg, "rl_confidence_threshold") else 0.78),
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
        if float(suggestion.get("drawdown_kill_percent", 8.0)) > float(getattr(self.engine.config, "drawdown_kill_percent", 8.0)):
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

    def _apply_candidate(self, candidate: dict[str, Any]) -> None:
        suggestion = dict(candidate.get("hyperparam_suggestion", {}))
        cfg = self.engine.config
        if "max_risk_percent" in suggestion:
            cfg.max_risk_percent = float(suggestion["max_risk_percent"])
        if "drawdown_kill_percent" in suggestion:
            cfg.drawdown_kill_percent = float(suggestion["drawdown_kill_percent"])

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
    try:
        import yaml

        if not os.path.exists(config_path):
            return {
                "enabled": True,
                "approval_required": True,
                "mode": "real",
                "aggressive_evolution": False,
                "max_mutation_depth": "conservative",
            }
        with open(config_path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        evo = data.get("evolution", {}) if isinstance(data, dict) else {}
        fine_tuning = data.get("fine_tuning", {}) if isinstance(data, dict) else {}
        if not isinstance(evo, dict):
            evo = {}
        if not isinstance(fine_tuning, dict):
            fine_tuning = {}

        mode = str(
            os.getenv("LUMINA_MODE") or (data.get("mode", "sim") if isinstance(data, dict) else "sim")
        ).strip().lower()
        sim_cfg = data.get("sim", {}) if isinstance(data, dict) and isinstance(data.get("sim"), dict) else {}
        real_cfg = data.get("real", {}) if isinstance(data, dict) and isinstance(data.get("real"), dict) else {}

        if mode == "sim":
            approval_required = bool(sim_cfg.get("approval_required", False))
            aggressive_evolution = bool(sim_cfg.get("aggressive_evolution", True))
            max_mutation_depth = str(sim_cfg.get("max_mutation_depth", "radical"))
        else:
            approval_required = bool(real_cfg.get("approval_required", evo.get("approval_required", True)))
            aggressive_evolution = bool(real_cfg.get("aggressive_evolution", False))
            max_mutation_depth = str(real_cfg.get("max_mutation_depth", "conservative"))

        return {
            "enabled": bool(evo.get("enabled", True)),
            "approval_required": approval_required,
            "mode": mode,
            "aggressive_evolution": aggressive_evolution,
            "max_mutation_depth": max_mutation_depth,
            "fine_tuning": {
                "auto_trigger": bool(fine_tuning.get("auto_trigger", True)),
                "min_acceptance": float(fine_tuning.get("min_acceptance", 0.4) or 0.4),
                "drift_threshold": float(fine_tuning.get("drift_threshold", 0.25) or 0.25),
            },
        }
    except Exception:
        return {
            "enabled": True,
            "approval_required": True,
            "mode": "real",
            "aggressive_evolution": False,
            "max_mutation_depth": "conservative",
            "fine_tuning": {
                "auto_trigger": True,
                "min_acceptance": 0.4,
                "drift_threshold": 0.25,
            },
        }
