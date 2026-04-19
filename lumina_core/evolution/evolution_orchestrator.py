"""EvolutionOrchestrator – closed-loop multi-generation DNA evolution engine.

One nightly cycle:
  1. Fetch top-3 ranked DNA from registry.
  2. Generate 5-8 mutants + crossovers via genetic_operators.
  3. Score every candidate with calculate_fitness (seeded sim).
  4. Guard: never promote if fitness < previous generation.
  5. Promote winner to "active" via register_dna.
  6. Append entry to logs/evolution_metrics.jsonl.
  7. Publish summary to blackboard (if provided).

No backward compat, no over-engineering.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError
from lumina_core.config_loader import ConfigLoader
from lumina_core.notifications.notification_scheduler import NotificationScheduler
from .approval_twin_agent import ApprovalTwinAgent
from .approval_gym_scheduler import ApprovalGymScheduler
from .dna_registry import DNARegistry, PolicyDNA
from .evolution_guard import EvolutionGuard
from .genetic_operators import calculate_fitness, crossover, mutate_prompt
from .multi_day_sim_runner import MultiDaySimRunner, SimResult
from .steve_values_registry import SteveValuesRegistry
from .veto_registry import VetoRegistry
from .veto_window import VetoWindow
from lumina_core.notifications.telegram_notifier import TelegramNotifier
from lumina_core.experiments.ab_framework import ABExperimentFramework


_METRICS_PATH = Path("logs/evolution_metrics.jsonl")
_SHADOW_STATE_PATH = Path("state/evolution_shadow_runs.json")
_CAPITAL_GUARD_DD = 25_000.0  # mirrors calculate_fitness hard guard
logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed_from_hash(h: str) -> int:
    return int(hashlib.sha256(h.encode()).hexdigest()[:8], 16)


def _score_candidate(dna: PolicyDNA, base_metrics: dict[str, Any], generation: int) -> float:
    """Derive a deterministic-seeded fitness score for a DNA candidate.

    Uses the nightly_report base metrics (PnL, drawdown, Sharpe) perturbed by
    a seed derived from the DNA hash so that identical DNA always gets the same
    score within one run.  The perturbation represents exploration variance.
    """
    rng = random.Random(_seed_from_hash(dna.hash + str(generation)))

    base_pnl = float(base_metrics.get("net_pnl", 0.0) or 0.0)
    base_dd = abs(float(base_metrics.get("max_drawdown", 0.0) or 0.0))
    base_sharpe = float(base_metrics.get("sharpe", 0.0) or 0.0)

    # Mutation exploration: ±15 % perturbation on each metric
    pnl = base_pnl * (1.0 + rng.uniform(-0.15, 0.15))
    dd = base_dd * (1.0 + rng.uniform(-0.10, 0.10))
    sharpe = base_sharpe * (1.0 + rng.uniform(-0.15, 0.15))

    return calculate_fitness(pnl, dd, sharpe, capital_preservation_threshold=_CAPITAL_GUARD_DD)


def _resolve_dashboard_url() -> str:
    value = str(os.getenv("LUMINA_DASHBOARD_URL", "")).strip()
    if value:
        return value
    monitoring_cfg = ConfigLoader.section("monitoring", default={})
    if isinstance(monitoring_cfg, dict):
        value = str(monitoring_cfg.get("dashboard_url", "")).strip()
        if value:
            return value
    return ""


@dataclass(slots=True)
class GenerationResult:
    generation: int
    candidate_count: int
    winner_hash: str
    winner_fitness: float
    previous_fitness: float
    promoted: bool
    timestamp: str = field(default_factory=_utcnow)


class EvolutionOrchestrator:
    """Singleton closed-loop evolution engine."""

    _instance: EvolutionOrchestrator | None = None
    _lock = threading.RLock()

    def __new__(cls) -> "EvolutionOrchestrator":
        with cls._lock:
            if cls._instance is None:
                obj = super().__new__(cls)
                obj._initialized = False  # type: ignore[attr-defined]
                cls._instance = obj
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._registry = DNARegistry()
        self._guard = EvolutionGuard()
        self._values_registry = SteveValuesRegistry()
        self._approval_twin = ApprovalTwinAgent(registry=self._values_registry)
        self._veto_registry = VetoRegistry()
        self._veto_window = VetoWindow(veto_registry=self._veto_registry, window_seconds=1800)
        self._telegram_notifier = TelegramNotifier(veto_registry=self._veto_registry)
        self._notification_scheduler = NotificationScheduler()
        self._sim_runner = MultiDaySimRunner(max_workers=8, drawdown_limit_ratio=0.02)
        self._metrics_path = _METRICS_PATH
        self._shadow_state_path = _SHADOW_STATE_PATH
        # FASE 3: ApprovalGymScheduler – Telegram-only UI, Brussels waking hours
        self._approval_gym_scheduler = ApprovalGymScheduler(
            telegram_notifier=self._telegram_notifier,
            notification_scheduler=self._notification_scheduler,
        )
        self._initialized = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_nightly_evolution_cycle(
        self,
        *,
        generations: int = 3,
        sim_duration_hours: int = 24,
        nightly_report: dict[str, Any] | None = None,
        explicit_human_approval: bool = False,
        blackboard: Any | None = None,
        mode: str = "sim",
    ) -> dict[str, Any]:
        """Run ``generations`` rounds of mutation/selection and return summary."""
        if not isinstance(nightly_report, dict):
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_REPORT_REQUIRED",
                message="run_nightly_evolution_cycle requires nightly_report: dict[str, Any].",
            )
        normalized_mode = str(mode or "sim").strip().lower()
        if normalized_mode in {"paper", "sim"} and not self._guard.can_mutate(mode=normalized_mode):
            return {
                "status": "blocked",
                "reason": f"mutations_not_allowed_in_mode:{mode}",
                "timestamp": _utcnow(),
            }
        report: dict[str, Any] = dict(nightly_report)
        gen_results: list[GenerationResult] = []
        self._append_metrics(
            {
                "event": "evolution_cycle_started",
                "timestamp": _utcnow(),
                "generations": max(1, int(generations)),
                "sim_duration_hours": max(1, int(sim_duration_hours)),
                "mode": str(mode),
            }
        )

        all_candidates: list[PolicyDNA] = []
        sim_days = max(1, int(round(max(1, int(sim_duration_hours)) / 24.0)))

        # FASE 2 Meta-RL: override sim_days from multiweek_fitness config when enabled
        evolution_cfg = ConfigLoader.section("evolution", default={}) or {}
        mw_cfg = evolution_cfg.get("multiweek_fitness", {}) if isinstance(evolution_cfg, dict) else {}
        if isinstance(mw_cfg, dict) and mw_cfg.get("enabled"):
            sim_days = max(sim_days, int(mw_cfg.get("days", 14) or 14))
            logger.info("[META-RL] multiweek_fitness enabled – sim_days=%d", sim_days)

        for gen_idx in range(max(1, int(generations))):
            result = self._run_single_generation(
                generation_offset=gen_idx,
                base_metrics=report,
                sim_days=sim_days,
                mode=normalized_mode,
                explicit_human_approval=bool(explicit_human_approval),
            )
            gen_results.append(result)
            if result.promoted:
                winner = self._registry.get_latest_dna(version="active")
                if winner is not None:
                    all_candidates.append(winner)

        summary = self._build_summary(gen_results, all_candidates)
        self._append_metrics(summary)

        if blackboard is not None:
            self._publish_to_blackboard(blackboard, summary)

        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_single_generation(
        self,
        *,
        generation_offset: int,
        mode: str,
        explicit_human_approval: bool,
        base_metrics: dict[str, Any],
        sim_days: int,
    ) -> GenerationResult:
        top_dna = self._registry.get_ranked_dna(limit=3)
        active_dna = self._registry.get_latest_dna(version="active")
        if not top_dna and active_dna is None:
            active_dna = self._bootstrap_active_dna(base_metrics=base_metrics)
            top_dna = [active_dna]
        previous_fitness = float(active_dna.fitness_score) if active_dna is not None else float("-inf")

        candidates = self._generate_candidates(
            top_dna=top_dna,
            active_dna=active_dna,
            generation_offset=generation_offset,
        )

        if not candidates:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_UNRECOVERABLE,
                code="EVOLUTION_CANDIDATE_GENERATION_EMPTY",
                message=f"No candidates generated for generation {generation_offset}.",
            )

        sim_results = self._sim_runner.evaluate_variants(candidates, days=sim_days, nightly_report=base_metrics)
        if not sim_results:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_UNRECOVERABLE,
                code="EVOLUTION_SIM_RESULTS_EMPTY",
                message=f"Simulation returned no results for generation {generation_offset}.",
            )

        candidate_pool = [self._candidate_to_ab_variant(item, sim_results=sim_results) for item in candidates]
        ab_framework = ABExperimentFramework(min_forks=5, max_forks=8, max_workers=8)
        selected: dict[str, Any] = {}

        def _score_variant(variant: dict[str, Any]) -> dict[str, Any]:
            payload = dict(variant)
            dna_hash = str(payload.get("dna_hash", ""))
            match = next((r for r in sim_results if r.dna_hash == dna_hash), None)
            payload["score"] = float(match.fitness) if match is not None else float("-inf")
            payload["confidence"] = 0.9
            return payload

        experiment = ab_framework.run_auto_forks(
            base_agent=dict(candidate_pool[0]),
            score_fn=_score_variant,
            promote_fn=lambda _: None,
            seed=_seed_from_hash(f"gen:{generation_offset}"),
            mode="sim",
            candidate_pool=candidate_pool,
        )
        selected = dict(experiment.selected_variant or {})

        winner_hash = str(selected.get("dna_hash", ""))
        winner_dna = next((item for item in candidates if item.hash == winner_hash), candidates[0])
        winner_fitness = float(selected.get("score", float("-inf")))

        twin_decision: dict[str, Any] = {
            "recommendation": mode != "real",
            "confidence": 0.9,
            "risk_flags": [],
            "explanation": "sim/paper path uses guard-only approval",
        }
        if mode == "real":
            twin_decision = self._approval_twin.evaluate_dna_promotion(winner_dna)

        # Guard: in REAL mode, signed approval additionally requires twin recommendation.
        signed = self._guard.has_signed_approval(
            confidence=0.9,  # orchestrator always runs with high synthetic confidence
            candidate_fitness=winner_fitness,
            current_fitness=previous_fitness,
            mode=mode,
            approval_twin_recommendation=bool(twin_decision.get("recommendation", False)),
        )
        generation_ok = self._guard.allows_generation_progress(
            candidate_fitness=winner_fitness,
            previous_generation_fitness=previous_fitness,
        )

        promoted = False
        veto_check: dict[str, Any] = {"is_blocked": False, "reason": "no_veto", "active_veto_records": []}
        veto_blocked = False
        shadow_status = "not_required"
        shadow_days_completed = 0
        shadow_days_target = 0
        shadow_total_pnl = 0.0

        if mode == "real":
            shadow_decision = self._run_shadow_validation_gate(
                dna=winner_dna,
                winner_fitness=winner_fitness,
                nightly_report=base_metrics,
                signed=signed,
                generation_ok=generation_ok,
            )
            promoted = bool(shadow_decision.get("promote_now", False))
            veto_check = dict(shadow_decision.get("veto_check", veto_check) or veto_check)
            veto_blocked = bool(shadow_decision.get("veto_blocked", False))
            shadow_status = str(shadow_decision.get("shadow_status", shadow_status))
            shadow_days_completed = int(shadow_decision.get("shadow_days_completed", 0) or 0)
            shadow_days_target = int(shadow_decision.get("shadow_days_target", 0) or 0)
            shadow_total_pnl = float(shadow_decision.get("shadow_total_pnl", 0.0) or 0.0)
        else:
            promoted = bool(signed and generation_ok)

        if promoted:
            promoted_dna = self._registry.mutate(
                parent=winner_dna,
                mutation_rate=0.1,
                fitness_score=winner_fitness,
                version="active",
                lineage_hash=winner_dna.lineage_hash,
            )
            self._registry.register_dna(promoted_dna)
            if mode == "real":
                self._mark_shadow_promoted(dna_hash=winner_dna.hash)
        self._append_metrics(
            {
                "event": "generation_completed",
                "timestamp": _utcnow(),
                "generation": generation_offset,
                "candidate_count": len(candidates),
                "winner_hash": winner_dna.hash,
                "winner_fitness": winner_fitness,
                "previous_fitness": previous_fitness,
                "promoted": promoted,
                "mode": mode,
                "explicit_human_approval": bool(explicit_human_approval),
                "approval_twin_recommendation": bool(twin_decision.get("recommendation", False)),
                "approval_twin_confidence": float(twin_decision.get("confidence", 0.0) or 0.0),
                "approval_twin_risk_flags": list(twin_decision.get("risk_flags", []) or []),
                "veto_blocked": veto_blocked,
                "veto_reason": veto_check.get("reason", ""),
                "veto_active_records": len(veto_check.get("active_veto_records", [])),
                "shadow_status": shadow_status,
                "shadow_days_completed": shadow_days_completed,
                "shadow_days_target": shadow_days_target,
                "shadow_total_pnl": shadow_total_pnl,
                "ab_experiment_id": str(experiment.experiment_id),
                "sim_days": sim_days,
            }
        )

        return GenerationResult(
            generation=generation_offset,
            candidate_count=len(candidates),
            winner_hash=winner_dna.hash,
            winner_fitness=winner_fitness,
            previous_fitness=previous_fitness,
            promoted=promoted,
        )

    def _send_shadow_status_telegram(self, message: str) -> None:
        """Send shadow-gate status to Steve via Telegram, respecting Brussels waking hours."""
        def _send() -> bool:
            return self._telegram_notifier._send_telegram_message(message)
        try:
            self._notification_scheduler.schedule_notification(
                callback=_send,
                description=f"shadow_status:{message[:50]}",
            )
        except Exception as exc:
            logger.warning("[SHADOWTWIN] Telegram notification failed: %s", exc)

    def _run_shadow_validation_gate(
        self,
        *,
        dna: PolicyDNA,
        winner_fitness: float,
        nightly_report: dict[str, Any],
        signed: bool,
        generation_ok: bool,
    ) -> dict[str, Any]:
        if not signed or not generation_ok:
            return {
                "promote_now": False,
                "veto_blocked": False,
                "veto_check": {"is_blocked": False, "reason": "guard_not_satisfied", "active_veto_records": []},
                "shadow_status": "guard_blocked",
                "shadow_days_completed": 0,
                "shadow_days_target": 0,
                "shadow_total_pnl": 0.0,
            }

        shadow_runs = self._load_shadow_runs()
        record = dict(shadow_runs.get(dna.hash, {}) or {})

        if not record:
            min_days, max_days = self._resolve_shadow_day_bounds()
            target_days = self._guard.resolve_shadow_days(minimum_days=min_days, maximum_days=max_days)
            record = {
                "dna_hash": dna.hash,
                "lineage_hash": str(dna.lineage_hash),
                "started_at": _utcnow(),
                "updated_at": _utcnow(),
                "target_days": target_days,
                "status": "pending",
                "winner_fitness": float(winner_fitness),
                "daily_pnl": [],
                "daily_fill_count": [],
                "shadow_total_pnl": 0.0,
            }
            shadow_runs[dna.hash] = record
            self._save_shadow_runs(shadow_runs)
            # FASE 3: notify Steve that shadow run has started
            self._send_shadow_status_telegram(
                f"SHADOWTWIN started\nDNA: {dna.hash[:12]}\nTarget: {target_days} days\n"
                f"Reply VETO {dna.hash[:12]} to block promotion."
            )
            return {
                "promote_now": False,
                "veto_blocked": False,
                "veto_check": {"is_blocked": False, "reason": "shadow_started", "active_veto_records": []},
                "shadow_status": "pending",
                "shadow_days_completed": 0,
                "shadow_days_target": int(target_days),
                "shadow_total_pnl": 0.0,
            }

        status = str(record.get("status", "pending")).strip().lower()
        if status == "promoted":
            return {
                "promote_now": False,
                "veto_blocked": False,
                "veto_check": {"is_blocked": False, "reason": "already_promoted", "active_veto_records": []},
                "shadow_status": "promoted",
                "shadow_days_completed": len(list(record.get("daily_pnl", []) or [])),
                "shadow_days_target": int(record.get("target_days", 0) or 0),
                "shadow_total_pnl": float(record.get("shadow_total_pnl", 0.0) or 0.0),
            }

        if status in {"failed", "vetoed"}:
            vetoed = status == "vetoed"
            return {
                "promote_now": False,
                "veto_blocked": vetoed,
                "veto_check": {
                    "is_blocked": vetoed,
                    "reason": "shadow_failed_or_vetoed",
                    "active_veto_records": [],
                },
                "shadow_status": status,
                "shadow_days_completed": len(list(record.get("daily_pnl", []) or [])),
                "shadow_days_target": int(record.get("target_days", 0) or 0),
                "shadow_total_pnl": float(record.get("shadow_total_pnl", 0.0) or 0.0),
            }

        target_days = max(1, int(record.get("target_days", 3) or 3))
        daily_pnl = [float(item) for item in list(record.get("daily_pnl", []) or [])]
        daily_fill_count = [int(item) for item in list(record.get("daily_fill_count", []) or [])]

        if len(daily_pnl) < target_days:
            # FASE 3: Poll Telegram for VETO from Steve before running next shadow day
            try:
                self._telegram_notifier.poll_for_replies()
            except Exception as exc:
                logger.warning("[SHADOWTWIN] Telegram poll failed: %s", exc)
            if self._telegram_notifier.is_vetoed_or_expired(dna.hash):
                record["status"] = "vetoed"
                record["updated_at"] = _utcnow()
                shadow_runs[dna.hash] = record
                self._save_shadow_runs(shadow_runs)
                self._send_shadow_status_telegram(
                    f"SHADOWTWIN VETOED by Steve\nDNA: {dna.hash[:12]}\n"
                    f"Days completed: {len(daily_pnl)}/{target_days}"
                )
                return {
                    "promote_now": False,
                    "veto_blocked": True,
                    "veto_check": {"is_blocked": True, "reason": "telegram_veto", "active_veto_records": []},
                    "shadow_status": "vetoed",
                    "shadow_days_completed": len(daily_pnl),
                    "shadow_days_target": target_days,
                    "shadow_total_pnl": float(sum(daily_pnl)),
                }

            shadow_results = self._sim_runner.evaluate_variants(
                [dna],
                days=1,
                nightly_report=nightly_report,
                shadow_mode=True,
            )
            latest = shadow_results[0] if shadow_results else None
            day_pnl = float(latest.avg_pnl) if latest is not None else 0.0
            fill_count = len(list(latest.hypothetical_fills or [])) if latest is not None else 0
            daily_pnl.append(day_pnl)
            daily_fill_count.append(fill_count)
            record["daily_pnl"] = daily_pnl
            record["daily_fill_count"] = daily_fill_count
            record["shadow_total_pnl"] = float(sum(daily_pnl))
            record["updated_at"] = _utcnow()
            shadow_runs[dna.hash] = record
            self._save_shadow_runs(shadow_runs)
            # FASE 3: daily progress update to Steve
            self._send_shadow_status_telegram(
                f"SHADOWTWIN Day {len(daily_pnl)}/{target_days}\n"
                f"DNA: {dna.hash[:12]}\n"
                f"Day PnL: ${day_pnl:+.2f} | Total: ${float(sum(daily_pnl)):+.2f}"
            )

        shadow_total_pnl = float(sum(daily_pnl))
        veto_check = self._veto_window_for_days(target_days).check_with_details(dna_id=dna.hash)
        veto_blocked = bool(veto_check.get("is_blocked", False))

        if len(daily_pnl) < target_days:
            return {
                "promote_now": False,
                "veto_blocked": veto_blocked,
                "veto_check": veto_check,
                "shadow_status": "pending",
                "shadow_days_completed": len(daily_pnl),
                "shadow_days_target": target_days,
                "shadow_total_pnl": shadow_total_pnl,
            }

        shadow_twin = self._approval_twin.evaluate_shadow_promotion(
            dna=dna,
            shadow_total_pnl=shadow_total_pnl,
            veto_blocked=veto_blocked,
        )
        risk_flags = list(shadow_twin.get("risk_flags", []) or [])
        shadow_passed = self._guard.shadow_validation_passed(
            shadow_total_pnl=shadow_total_pnl,
            veto_blocked=veto_blocked,
            risk_flags=risk_flags,
        )

        record["status"] = "passed" if shadow_passed else ("vetoed" if veto_blocked else "failed")
        record["shadow_total_pnl"] = shadow_total_pnl
        record["updated_at"] = _utcnow()
        record["shadow_decision"] = {
            "recommendation": bool(shadow_twin.get("recommendation", False)),
            "confidence": float(shadow_twin.get("confidence", 0.0) or 0.0),
            "risk_flags": risk_flags,
            "explanation": str(shadow_twin.get("explanation", "")),
        }
        shadow_runs[dna.hash] = record
        self._save_shadow_runs(shadow_runs)

        # FASE 3: final shadow verdict to Steve
        if shadow_passed:
            self._send_shadow_status_telegram(
                f"SHADOWTWIN PASSED – promoting\nDNA: {dna.hash[:12]}\n"
                f"Total PnL: ${shadow_total_pnl:+.2f} over {len(daily_pnl)} days"
            )
        else:
            reason = "veto" if veto_blocked else "negative PnL"
            self._send_shadow_status_telegram(
                f"SHADOWTWIN FAILED ({reason})\nDNA: {dna.hash[:12]}\n"
                f"Total PnL: ${shadow_total_pnl:+.2f} over {len(daily_pnl)} days"
            )

        return {
            "promote_now": shadow_passed,
            "veto_blocked": veto_blocked,
            "veto_check": veto_check,
            "shadow_status": str(record.get("status", "pending")),
            "shadow_days_completed": len(daily_pnl),
            "shadow_days_target": target_days,
            "shadow_total_pnl": shadow_total_pnl,
        }

    def _resolve_shadow_day_bounds(self) -> tuple[int, int]:
        evolution_cfg = ConfigLoader.section("evolution", default={})
        if not isinstance(evolution_cfg, dict):
            return 3, 7
        shadow_cfg = evolution_cfg.get("shadow_validation", {})
        if not isinstance(shadow_cfg, dict):
            return 3, 7
        min_days = max(1, int(shadow_cfg.get("min_days", 3) or 3))
        max_days = max(min_days, int(shadow_cfg.get("max_days", 7) or 7))
        return min_days, max_days

    def _veto_window_for_days(self, days: int) -> VetoWindow:
        return VetoWindow(
            veto_registry=self._veto_registry,
            window_seconds=max(1, int(days)) * 24 * 60 * 60,
        )

    def _load_shadow_runs(self) -> dict[str, Any]:
        path = self._shadow_state_path
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_shadow_runs(self, payload: dict[str, Any]) -> None:
        path = self._shadow_state_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def _mark_shadow_promoted(self, *, dna_hash: str) -> None:
        shadow_runs = self._load_shadow_runs()
        record = dict(shadow_runs.get(dna_hash, {}) or {})
        if not record:
            return
        record["status"] = "promoted"
        record["updated_at"] = _utcnow()
        shadow_runs[dna_hash] = record
        self._save_shadow_runs(shadow_runs)

    def _bootstrap_active_dna(self, *, base_metrics: dict[str, Any]) -> PolicyDNA:
        """Create an initial active DNA so generation zero can run on a clean registry."""
        fitness = _score_candidate(
            PolicyDNA.create(
                prompt_id="bootstrap_seed",
                version="candidate",
                content={
                    "candidate_name": "bootstrap_seed",
                    "prompt_tweak": "Bootstrap evolution seed policy",
                    "regime_focus": "neutral",
                    "hyperparam_suggestion": {
                        "fast_path_threshold": 0.78,
                        "max_risk_percent": 1.0,
                        "drawdown_kill_percent": 8.0,
                    },
                },
                fitness_score=0.0,
                generation=0,
                lineage_hash="GENESIS",
            ),
            base_metrics=base_metrics,
            generation=0,
        )
        seed = PolicyDNA.create(
            prompt_id="bootstrap_seed",
            version="active",
            content={
                "candidate_name": "bootstrap_seed",
                "prompt_tweak": "Bootstrap evolution seed policy",
                "regime_focus": "neutral",
                "hyperparam_suggestion": {
                    "fast_path_threshold": 0.78,
                    "max_risk_percent": 1.0,
                    "drawdown_kill_percent": 8.0,
                },
            },
            fitness_score=fitness,
            generation=0,
            lineage_hash="GENESIS",
        )
        return self._registry.register_dna(seed)

    @staticmethod
    def _candidate_to_ab_variant(candidate: PolicyDNA, *, sim_results: list[SimResult]) -> dict[str, Any]:
        match = next((item for item in sim_results if item.dna_hash == candidate.hash), None)
        return {
            "name": f"dna_{candidate.hash[:8]}",
            "dna_hash": candidate.hash,
            "score": float(match.fitness) if match is not None else float("-inf"),
            "confidence": 0.9,
        }

    def _generate_candidates(
        self,
        *,
        top_dna: list[PolicyDNA],
        active_dna: PolicyDNA | None,
        generation_offset: int,
    ) -> list[PolicyDNA]:
        """Produce 5-8 mutant/crossover candidates from top ranked DNA."""
        if not top_dna and active_dna is None:
            return []

        seed_pool = list(top_dna) or []
        if active_dna is not None and not any(d.hash == active_dna.hash for d in seed_pool):
            seed_pool.insert(0, active_dna)

        target_count = random.randint(5, 8)
        candidates: list[PolicyDNA] = []
        base = seed_pool[0]
        for i in range(target_count):
            rate = round(0.1 + (i * 0.1), 2)
            if i < 4 or len(seed_pool) < 2:
                # Pure mutation
                new_content = mutate_prompt(base.content, rate)
                candidate = self._registry.mutate(
                    parent=base,
                    mutation_rate=rate,
                    content=new_content,
                    fitness_score=base.fitness_score,
                    version="candidate",
                    lineage_hash=base.lineage_hash,
                )
            else:
                # Crossover between top parents
                other = seed_pool[i % len(seed_pool)]
                new_content = crossover(base, other)
                candidate = self._registry.mutate(
                    parent=base,
                    mutation_rate=rate,
                    content=new_content,
                    fitness_score=(base.fitness_score + other.fitness_score) / 2.0,
                    version="candidate",
                    lineage_hash=base.lineage_hash,
                    crossover=other,
                )
            self._registry.register_dna(candidate)
            candidates.append(candidate)

        return candidates

    def _build_summary(
        self,
        gen_results: list[GenerationResult],
        promoted_dna: list[PolicyDNA],
    ) -> dict[str, Any]:
        total_candidates = sum(r.candidate_count for r in gen_results)
        promotions = sum(1 for r in gen_results if r.promoted)
        if not gen_results:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_UNRECOVERABLE,
                code="EVOLUTION_RESULTS_EMPTY",
                message="No generation results available to build summary.",
            )
        best_fitness = max(r.winner_fitness for r in gen_results)
        return {
            "status": "complete",
            "timestamp": _utcnow(),
            "generations_run": len(gen_results),
            "total_candidates_evaluated": total_candidates,
            "promotions": promotions,
            "best_fitness": round(best_fitness, 6) if best_fitness != float("-inf") else None,
            "generations": [
                {
                    "generation": r.generation,
                    "candidates": r.candidate_count,
                    "winner_hash": r.winner_hash,
                    "winner_fitness": round(r.winner_fitness, 6) if r.winner_fitness != float("-inf") else None,
                    "previous_fitness": round(r.previous_fitness, 6) if r.previous_fitness != float("-inf") else None,
                    "promoted": r.promoted,
                    "timestamp": r.timestamp,
                }
                for r in gen_results
            ],
        }

    def _append_metrics(self, summary: dict[str, Any]) -> None:
        self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with self._metrics_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(summary, ensure_ascii=False) + "\n")

    def _publish_to_blackboard(self, blackboard: Any, summary: dict[str, Any]) -> None:
        if not hasattr(blackboard, "publish_sync"):
            raise LuminaError(
                severity=ErrorSeverity.FATAL_MODE_VIOLATION,
                code="EVOLUTION_BLACKBOARD_PUBLISH_UNAVAILABLE",
                message="Blackboard does not expose publish_sync for evolution result publishing.",
            )
        blackboard.publish_sync(
            topic="meta.evolution_result",
            producer="evolution_orchestrator",
            payload={
                "status": summary.get("status"),
                "generations_run": summary.get("generations_run"),
                "promotions": summary.get("promotions"),
                "best_fitness": summary.get("best_fitness"),
                "timestamp": summary.get("timestamp"),
            },
            confidence=0.85,
        )
