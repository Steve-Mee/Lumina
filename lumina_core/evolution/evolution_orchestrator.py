"""EvolutionOrchestrator – closed-loop multi-generation DNA evolution engine.

One nightly cycle:
  1. Fetch top-3 ranked DNA from registry.
  2. Dream Engine + Community Knowledge (shadow+twin vetted) before mutants + crossovers.
  3. Score every candidate with calculate_fitness (seeded sim).
  4. Guard: never promote if fitness < previous generation; REAL zero-touch needs twin ≥ 0.97, clean flags, shadow + backtest.
  5. MetaSwarm (five agents) deliberates and may block promotion after neuro/gen cycles.
  6. Promote winner to "active" via register_dna.
  7. Append entry to logs/evolution_metrics.jsonl.
  8. Publish summary to blackboard (if provided).

No backward compat, no over-engineering.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from .lumina_bible import LuminaBible
from .community_knowledge import run_community_knowledge_nightly
from .dream_engine import (
    dream_engine_config,
    enrich_nightly_report_with_dream,
    merge_dream_hyperparam_nudges,
    run_dream_batch,
)
from .meta_swarm import MetaSwarm, SwarmConsensus, meta_swarm_governance_enabled, parallel_realities_from_config
from .multi_day_sim_runner import MultiDaySimRunner, SimResult
from .neuroevolution import evaluate_weight_population
from .bot_stress_choices import resolve_neuro_ohlc_stress_rollouts
from .reality_generator import aggregate_ppo_eval_worst_reality, stress_simulator_ohlc
from .simulator_data_support import resolve_neuro_simulator_rows_for_neuro_cycle
from .strategy_generator import StrategyGenerator
from .steve_values_registry import SteveValuesRegistry
from .veto_registry import VetoRegistry
from .veto_window import VetoWindow
from lumina_core.notifications.telegram_notifier import TelegramNotifier
from lumina_core.experiments.ab_framework import ABExperimentFramework
from lumina_core.engine.constitutional_principles import ConstitutionalChecker, ConstitutionalViolationError
from .mutation_sandbox import MutationSandbox, SandboxResult
# New canonical safety layer — preferred over direct ConstitutionalChecker usage.
from lumina_core.safety.constitutional_guard import ConstitutionalGuard
from lumina_core.safety.trading_constitution import TRADING_CONSTITUTION


_METRICS_PATH = Path("logs/evolution_metrics.jsonl")
_SHADOW_STATE_PATH = Path("state/evolution_shadow_runs.json")
_NEURO_WEIGHTS_PATH = Path("state/neuro_weights")
_CAPITAL_GUARD_DD = 25_000.0  # mirrors calculate_fitness hard guard
logger = logging.getLogger(__name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_file_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _seed_from_hash(h: str) -> int:
    return int(hashlib.sha256(h.encode()).hexdigest()[:8], 16)


def _apply_dream_learnings_to_dna_content(
    content: Any,
    dream_report: dict[str, Any] | None,
    *,
    evolution_mode: str = "sim",
) -> Any:
    """Fold dream tail stress + hints into candidate DNA so evolution can align with learnings."""
    if not dream_report or not dream_report.get("enabled", True):
        return content
    hints = [str(x) for x in (dream_report.get("rule_hints") or []) if str(x).strip()]
    br = float(dream_report.get("breach_rate", 0.0) or 0.0)
    wdd = float(dream_report.get("worst_dd_ratio", 0.0) or 0.0)
    blurb = (
        f" [dream_learn: stress_breach={br:.3f} worst_dd~={wdd:.3f}"
        f"{'; focus: ' + ', '.join(hints) if hints else ''}]"
    )
    c = str(content or "").strip()
    if c.startswith("{") and c.endswith("}"):
        try:
            d = json.loads(c)
        except Exception:
            return c + blurb
        if isinstance(d, dict):
            d2 = dict(d)
            d2["dream_learnings"] = {
                "breach_rate": br,
                "worst_dd_ratio": wdd,
                "rule_hints": hints,
            }
            base_hs: dict[str, float]
            raw_hs = d2.get("hyperparam_suggestion")
            if isinstance(raw_hs, dict):
                base_hs = {
                    "max_risk_percent": float(raw_hs.get("max_risk_percent", 1.0) or 1.0),
                    "drawdown_kill_percent": float(raw_hs.get("drawdown_kill_percent", 8.0) or 8.0),
                }
            else:
                base_hs = {
                    "max_risk_percent": 1.0,
                    "drawdown_kill_percent": 8.0,
                }
            nudged = merge_dream_hyperparam_nudges(
                base_hs, dream_report, evolution_mode=evolution_mode
            )
            d2["hyperparam_suggestion"] = {
                "max_risk_percent": float(nudged["max_risk_percent"]),
                "drawdown_kill_percent": float(nudged["drawdown_kill_percent"]),
            }
            if nudged.get("_nudged"):
                d2["dream_risk_nudge"] = {
                    "applied": True,
                    "evolution_mode": str(evolution_mode),
                    "source_hints": list(hints),
                }
            base_pt = str(d2.get("prompt_tweak", "") or "")
            d2["prompt_tweak"] = (base_pt + blurb)[:8000]
            return json.dumps(d2, sort_keys=True, ensure_ascii=True)
    return c + blurb


def _dream_engine_commit_hints_to_bible() -> bool:
    evo = ConfigLoader.section("evolution", default={}) or {}
    if not isinstance(evo, dict):
        return True
    de = evo.get("dream_engine", {})
    if not isinstance(de, dict):
        return True
    return bool(de.get("commit_hints_to_bible", True))


def _resolve_parallel_realities_count() -> int:
    """SIM stress universes per candidate (1 = disabled, up to 50 for nightly robustness)."""
    return parallel_realities_from_config()


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
    generated_tested: int = 0
    generated_winners: int = 0
    neuro_tested: int = 0
    neuro_winners: int = 0
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
        # FASE 2: Initialize sim_runner with real_market_data support if configured
        self._sim_runner = self._create_sim_runner()
        self._strategy_generator = StrategyGenerator()
        self._lumina_bible = LuminaBible()
        self._metrics_path = _METRICS_PATH
        self._shadow_state_path = _SHADOW_STATE_PATH
        self._generated_bible_path = self._lumina_bible.path
        self._neuro_weights_path = _NEURO_WEIGHTS_PATH
        self._ppo_trainer: Any | None = None
        # FASE 3: ApprovalGymScheduler – Telegram-only UI, Brussels waking hours
        self._approval_gym_scheduler = ApprovalGymScheduler(
            telegram_notifier=self._telegram_notifier,
            notification_scheduler=self._notification_scheduler,
        )
        self._meta_swarm = MetaSwarm()
        self._vector_collection: Any | None = None
        # AGI Safety: single guard instance shared across all generation cycles.
        self._constitutional_guard = ConstitutionalGuard()
        self._initialized = True

    def bind_ppo_trainer(self, ppo_trainer: Any | None) -> None:
        self._ppo_trainer = ppo_trainer

    def bind_vector_collection(self, collection: Any | None) -> None:
        """Optional Chroma collection for vetted community knowledge upserts."""
        self._vector_collection = collection

    def _resolve_ppo_trainer(self) -> Any | None:
        return self._ppo_trainer

    def _create_sim_runner(self) -> MultiDaySimRunner:
        """Create MultiDaySimRunner with real-market and true-backtest modes when configured."""
        evolution_cfg = ConfigLoader.section("evolution", default={}) or {}
        mw_cfg = evolution_cfg.get("multiweek_fitness", {}) if isinstance(evolution_cfg, dict) else {}
        use_real_data = bool(mw_cfg.get("use_real_market_data", False)) if isinstance(mw_cfg, dict) else False
        use_backtest_mode = bool(mw_cfg.get("backtest_mode", False)) if isinstance(mw_cfg, dict) else False

        market_data_service = None
        if use_real_data:
            try:
                # Attempt to get market_data_service from runtime
                from lumina_core.runtime_context import RuntimeContext

                rt_ctx = getattr(RuntimeContext, "_current_runtime", None)
                if rt_ctx is not None and hasattr(rt_ctx, "market_data_service"):
                    market_data_service = rt_ctx.market_data_service
                if market_data_service is None:
                    logger.warning("[EVOLUTION] real_market_data enabled but market_data_service unavailable")
            except Exception as exc:
                logger.warning("[EVOLUTION] Could not initialize market_data_service: %s", exc)

        return MultiDaySimRunner(
            max_workers=8,
            drawdown_limit_ratio=0.02,
            real_market_data=use_real_data,
            true_backtest_mode=use_backtest_mode,
            market_data_service=market_data_service,
        )

    def _run_meta_swarm_deliberation(
        self,
        *,
        winner_dna: PolicyDNA,
        winner_fitness: float,
        previous_fitness: float,
        base_metrics: dict[str, Any],
        mode: str,
        generation_offset: int,
        parallel_realities: int,
        sim_days: int,
        neuro_summary: dict[str, Any],
    ) -> SwarmConsensus:
        if not meta_swarm_governance_enabled():
            return SwarmConsensus(True, 0.9, False)
        br = dict(base_metrics or {})
        de = br.get("dream_engine") if isinstance(br.get("dream_engine"), dict) else None
        ctx: dict[str, Any] = {
            "winner_fitness": float(winner_fitness),
            "previous_fitness": float(previous_fitness),
            "nightly_report": dict(base_metrics),
            "mode": str(mode),
            "sim_days": max(1, int(sim_days)),
            "parallel_realities": max(1, int(parallel_realities)),
            "generation": int(generation_offset),
            "neuro_winner_accepted": bool(neuro_summary.get("winner_accepted", False)),
            "winner_prompt_id": str(getattr(winner_dna, "prompt_id", "") or ""),
        }
        if de:
            ctx["dream_engine"] = dict(de)
        return self._meta_swarm.deliberate(ctx)

    def _run_dream_engine_batch(
        self,
        *,
        base_metrics: dict[str, Any],
        sim_days: int,
        generation_offset: int,
    ) -> dict[str, Any]:
        enabled, count, horizon_cfg, ddr = dream_engine_config()
        if not enabled:
            return {
                "enabled": False,
                "dream_count": 0,
                "breach_count": 0,
                "breach_rate": 0.0,
                "worst_dd_ratio": 0.0,
                "median_terminal_equity_delta": 0.0,
                "rule_hints": [],
            }
        horizon = max(1, min(int(horizon_cfg), int(sim_days)))
        seed = _seed_from_hash(f"dream:{generation_offset}")
        report = run_dream_batch(
            base_metrics,
            dream_count=count,
            horizon_days=horizon,
            seed=seed,
            drawdown_limit_ratio=ddr,
        )
        if report.rule_hints and _dream_engine_commit_hints_to_bible():
            br = float(report.breach_rate)
            for raw_hint in report.rule_hints:
                try:
                    self._lumina_bible.append_dream_rule_hint(
                        hint=str(raw_hint),
                        generation=int(generation_offset),
                        breach_rate=br,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[DREAM_ENGINE] could not append rule hint to bible: %s", exc)
        payload = {
            "enabled": True,
            "dream_count": report.dream_count,
            "breach_count": report.breach_count,
            "breach_rate": round(float(report.breach_rate), 6),
            "worst_dd_ratio": round(float(report.worst_dd_ratio), 6),
            "median_terminal_equity_delta": round(float(report.median_terminal_equity_delta), 6),
            "rule_hints": list(report.rule_hints),
        }
        self._append_metrics(
            {
                "event": "dream_engine_batch",
                "timestamp": _utcnow(),
                "generation": generation_offset,
                **payload,
            }
        )
        return payload

    def _run_community_knowledge_cycle(
        self,
        *,
        base_metrics: dict[str, Any],
        active_dna: PolicyDNA | None,
        generation_offset: int,
    ) -> dict[str, Any]:
        summary = run_community_knowledge_nightly(
            bible=self._lumina_bible,
            sim_runner=self._sim_runner,
            approval_twin=self._approval_twin,
            guard=self._guard,
            active_dna=active_dna,
            base_metrics=base_metrics,
            generation_offset=generation_offset,
            vector_collection=getattr(self, "_vector_collection", None),
        )
        if summary.get("enabled") and int(summary.get("examined", 0) or 0) + int(summary.get("committed", 0) or 0) > 0:
            self._append_metrics(
                {
                    "event": "community_knowledge_cycle",
                    "timestamp": _utcnow(),
                    "generation": generation_offset,
                    **summary,
                }
            )
        return summary

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
                "parallel_realities": int(parallel_realities_from_config()),
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

        dream_summary = self._run_dream_engine_batch(
            base_metrics=base_metrics,
            sim_days=sim_days,
            generation_offset=generation_offset,
        )
        generation_metrics = enrich_nightly_report_with_dream(base_metrics, dream_summary)

        community_summary = self._run_community_knowledge_cycle(
            base_metrics=generation_metrics,
            active_dna=active_dna,
            generation_offset=generation_offset,
        )

        candidates = self._generate_candidates(
            top_dna=top_dna,
            active_dna=active_dna,
            generation_offset=generation_offset,
            dream_report=dream_summary,
            evolution_mode=mode,
        )

        if not candidates:
            raise LuminaError(
                severity=ErrorSeverity.FATAL_UNRECOVERABLE,
                code="EVOLUTION_CANDIDATE_GENERATION_EMPTY",
                message=f"No candidates generated for generation {generation_offset}.",
            )

        parallel_realities = _resolve_parallel_realities_count()

        # FASE 2: Pass real-market and true-backtest flags to evaluate_variants
        use_real_data = bool(getattr(self._sim_runner, "real_market_data", False))
        use_backtest_mode = bool(getattr(self._sim_runner, "true_backtest_mode", False))
        try:
            sim_results = self._sim_runner.evaluate_variants(
                candidates,
                days=sim_days,
                nightly_report=generation_metrics,
                real_market_data=use_real_data,
                true_backtest_mode=use_backtest_mode,
                parallel_realities=parallel_realities,
            )
        except TypeError:
            sim_results = self._sim_runner.evaluate_variants(
                candidates,
                days=sim_days,
                nightly_report=generation_metrics,
                real_market_data=use_real_data,
            )
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

        # Dedicated shadow runner for REAL promotion validation.
        shadow_runner: Any = MultiDaySimRunner(max_workers=8, drawdown_limit_ratio=0.02)
        # Keep compatibility with injected/custom runners in tests and dev overrides.
        if hasattr(self._sim_runner, "evaluate_variants") and not isinstance(self._sim_runner, MultiDaySimRunner):
            shadow_runner = self._sim_runner

        twin_confidence = float(twin_decision.get("confidence", 0.0) or 0.0)
        twin_risk_flags = [str(x) for x in list(twin_decision.get("risk_flags", []) or [])]
        signed_confidence = twin_confidence if str(mode).strip().lower() == "real" else 0.9

        # Guard: REAL uses twin confidence (0–1 or 0–100) for ultra zero-touch floor + shadow.
        signed = self._guard.has_signed_approval(
            confidence=signed_confidence,
            candidate_fitness=winner_fitness,
            current_fitness=previous_fitness,
            mode=mode,
            approval_twin_recommendation=bool(twin_decision.get("recommendation", False)),
            approval_twin=self._approval_twin,
            dna=winner_dna,
            shadow_runner=shadow_runner,
            twin_risk_flags=twin_risk_flags,
        )
        generation_ok = self._guard.allows_generation_progress(
            candidate_fitness=winner_fitness,
            previous_generation_fitness=previous_fitness,
        )

        promoted = False
        veto_check: dict[str, Any] = {"is_blocked": False, "reason": "no_veto", "active_veto_records": []}
        veto_blocked = False
        shadow_status = "not_required"
        shadow_passed = False
        shadow_days_completed = 0
        shadow_days_target = 0
        shadow_total_pnl = 0.0

        if mode == "real":
            shadow_decision = self._run_shadow_validation_gate(
                dna=winner_dna,
                winner_fitness=winner_fitness,
                nightly_report=generation_metrics,
                signed=signed,
                generation_ok=generation_ok,
                shadow_runner=shadow_runner,
            )
            promoted = bool(shadow_decision.get("promote_now", False))
            veto_check = dict(shadow_decision.get("veto_check", veto_check) or veto_check)
            veto_blocked = bool(shadow_decision.get("veto_blocked", False))
            shadow_status = str(shadow_decision.get("shadow_status", shadow_status))
            shadow_passed = bool(shadow_decision.get("shadow_passed", False))
            shadow_days_completed = int(shadow_decision.get("shadow_days_completed", 0) or 0)
            shadow_days_target = int(shadow_decision.get("shadow_days_target", 0) or 0)
            shadow_total_pnl = float(shadow_decision.get("shadow_total_pnl", 0.0) or 0.0)

            gated_promotion = self._guard.is_confidence_gated_promotion(
                winner_dna,
                twin_confidence,
                shadow_passed,
                winner_fitness,
                previous_fitness,
                twin_risk_flags=twin_risk_flags,
            )
            promoted = bool(promoted and gated_promotion)

            if shadow_status in {"passed", "failed", "vetoed"}:
                self._send_promotion_status_telegram(dna_hash=winner_dna.hash, promoted=promoted)
        else:
            promoted = bool(signed and generation_ok)

        # ── Constitutional Guard (pre-promotion) ─────────────────────────────
        # The ConstitutionalGuard is the single authoritative safety gate.
        # It checks all 15 principles, writes an audit record, and is
        # fail-closed: any unexpected error blocks promotion.
        constitutional_violations: list[str] = []
        if promoted:
            guard_result = self._constitutional_guard.check_pre_promotion(
                winner_dna.content, mode=mode, raise_on_fatal=False
            )
            if not guard_result.passed:
                constitutional_violations = guard_result.violation_names
                logger.error(
                    "ConstitutionalGuard BLOCKED promotion dna=%s mode=%s violations=%s",
                    winner_dna.hash[:12],
                    mode,
                    constitutional_violations,
                )
                promoted = False
            elif guard_result.warn_violations:
                logger.warning(
                    "ConstitutionalGuard WARN dna=%s mode=%s warns=%s",
                    winner_dna.hash[:12],
                    mode,
                    [v.principle_name for v in guard_result.warn_violations],
                )

        base_promoted = promoted

        neuro_summary = self._run_neuroevolution_cycle(
            generation_offset=generation_offset,
            mode=mode,
            baseline_fitness=max(float(previous_fitness), float(winner_fitness)),
            anchor_dna=winner_dna,
            nightly_report=generation_metrics,
            sim_days=sim_days,
        )
        if bool(neuro_summary.get("winner_accepted", False)):
            winner_fitness = max(float(winner_fitness), float(neuro_summary.get("winner_fitness", float("-inf"))))

        generated_summary = self._run_generated_strategy_cycle(
            generation_offset=generation_offset,
            mode=mode,
            base_metrics=generation_metrics,
            baseline_fitness=max(float(previous_fitness), float(winner_fitness)),
            anchor_dna=winner_dna,
        )

        swarm_consensus = self._run_meta_swarm_deliberation(
            winner_dna=winner_dna,
            winner_fitness=winner_fitness,
            previous_fitness=previous_fitness,
            base_metrics=generation_metrics,
            mode=mode,
            generation_offset=generation_offset,
            parallel_realities=parallel_realities,
            sim_days=sim_days,
            neuro_summary=neuro_summary,
        )
        promoted = bool(base_promoted and swarm_consensus.allow_promotion)

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
                "generated_ideas": int(generated_summary.get("ideas", 0) or 0),
                "generated_tested": int(generated_summary.get("tested", 0) or 0),
                "generated_winners": int(generated_summary.get("winners", 0) or 0),
                "neuro_tested": int(neuro_summary.get("tested", 0) or 0),
                "neuro_winners": int(neuro_summary.get("winners", 0) or 0),
                "neuro_best_fitness": (
                    float(neuro_summary.get("winner_fitness", 0.0) or 0.0)
                    if bool(neuro_summary.get("winner_accepted", False))
                    else None
                ),
                "neuro_winner_path": str(neuro_summary.get("winner_path", "") or ""),
                "neuro_simulator_data_source": str(neuro_summary.get("neuro_simulator_data_source", "") or ""),
                "ab_experiment_id": str(experiment.experiment_id),
                "sim_days": sim_days,
                "parallel_realities": int(parallel_realities),
                "dream_engine": dict(dream_summary),
                "community_knowledge": dict(community_summary),
                "meta_swarm": {
                    "enabled": bool(meta_swarm_governance_enabled()),
                    "allow_promotion": bool(swarm_consensus.allow_promotion),
                    "collective_score": round(float(swarm_consensus.collective_score), 6),
                    "risk_veto": bool(swarm_consensus.risk_veto),
                    "round_two": [
                        {
                            "agent": v.agent_id,
                            "approve": bool(v.approve),
                            "score": round(float(v.score), 4),
                            "veto": bool(v.veto),
                        }
                        for v in swarm_consensus.round_two
                    ],
                },
            }
        )

        return GenerationResult(
            generation=generation_offset,
            candidate_count=(
                len(candidates)
                + int(generated_summary.get("tested", 0) or 0)
                + int(neuro_summary.get("tested", 0) or 0)
            ),
            winner_hash=winner_dna.hash,
            winner_fitness=winner_fitness,
            previous_fitness=previous_fitness,
            promoted=promoted,
            generated_tested=int(generated_summary.get("tested", 0) or 0),
            generated_winners=int(generated_summary.get("winners", 0) or 0),
            neuro_tested=int(neuro_summary.get("tested", 0) or 0),
            neuro_winners=int(neuro_summary.get("winners", 0) or 0),
        )

    def _run_neuroevolution_cycle(
        self,
        *,
        generation_offset: int,
        mode: str,
        baseline_fitness: float,
        anchor_dna: PolicyDNA,
        nightly_report: dict[str, Any],
        sim_days: int,
    ) -> dict[str, Any]:
        _ = baseline_fitness  # DNA baseline; neuro promotion uses rollout_baseline from RL env only
        if str(mode).strip().lower() == "real":
            # Fail-closed: no autonomous weight mutation in REAL runtime.
            return {"tested": 0, "winners": 0, "winner_accepted": False, "reason": "real_mode_fail_closed"}

        ppo_trainer = self._resolve_ppo_trainer()
        if ppo_trainer is None:
            return {"tested": 0, "winners": 0, "winner_accepted": False, "reason": "ppo_trainer_unbound"}

        if not hasattr(ppo_trainer, "evaluate_policy_zip_rollouts"):
            return {"tested": 0, "winners": 0, "winner_accepted": False, "reason": "ppo_trainer_missing_rollout_eval"}

        engine = getattr(ppo_trainer, "engine", None)
        base_model = getattr(engine, "rl_policy_model", None)
        if base_model is None:
            return {"tested": 0, "winners": 0, "winner_accepted": False, "reason": "no_active_ppo_model"}

        cfg = ConfigLoader.section("evolution", "neuroevolution", default={})
        cfg = cfg if isinstance(cfg, dict) else {}
        simulator_data, neuro_data_source, strict_skip = resolve_neuro_simulator_rows_for_neuro_cycle(
            dict(nightly_report),
            engine=engine,
            neuro_cfg=cfg,
        )
        if strict_skip:
            logger.warning("[NEURO] skipped weight population: %s (source=%s)", strict_skip, neuro_data_source)
            return {
                "tested": 0,
                "winners": 0,
                "winner_accepted": False,
                "reason": strict_skip,
                "neuro_simulator_data_source": neuro_data_source,
            }
        logger.info(
            "[NEURO] rollout data source=%s bars=%d",
            neuro_data_source,
            len(simulator_data),
        )
        pr_cfg = int(parallel_realities_from_config())
        stress_universa_enabled = bool(cfg.get("stress_universa_enabled", True))
        stress_universa_max = max(1, min(50, int(cfg.get("stress_universa_max", 12) or 12)))
        if not stress_universa_enabled:
            eff_neuro_stress = 1
        else:
            eff_neuro_stress = max(1, min(stress_universa_max, pr_cfg, 50))
        neuro_stress_seed = f"neuro:{anchor_dna.hash}:{generation_offset}"

        use_ohlc_stress_rollouts = bool(resolve_neuro_ohlc_stress_rollouts()) and eff_neuro_stress >= 2
        _neuro_meta = {
            "neuro_simulator_data_source": neuro_data_source,
            "neuro_stress_universa": eff_neuro_stress,
            "neuro_stress_universa_enabled": stress_universa_enabled,
            "neuro_ohlc_stress_rollouts": use_ohlc_stress_rollouts,
        }
        population_size = max(5, min(8, int(cfg.get("population_size", 6) or 6)))
        mutation_std = float(cfg.get("mutation_std", 0.01) or 0.01)
        mutation_rate = float(cfg.get("mutation_rate", 0.08) or 0.08)
        crossover_ratio = float(cfg.get("crossover_ratio", 0.5) or 0.5)
        shadow_max_steps = max(32, int(cfg.get("shadow_max_steps", 256) or 256))
        backtest_max_steps = max(256, int(cfg.get("backtest_max_steps", 2048) or 2048))
        backtest_max_steps = min(5000, max(backtest_max_steps, max(256, int(sim_days) * 120)))

        baseline_snapshot = self._neuro_weights_path / f"baseline_gen{generation_offset}_{_utc_file_stamp()}.zip"
        baseline_snapshot.parent.mkdir(parents=True, exist_ok=True)
        try:
            ppo_trainer.save_weights(baseline_snapshot)
        except Exception:
            return {
                "tested": 0,
                "winners": 0,
                "winner_accepted": False,
                "reason": "baseline_save_failed",
                **_neuro_meta,
            }

        def _ppo_worst_across_ohlc_bars(
            policy_path: Path,
            raw_bars: list[dict[str, Any]],
        ) -> dict[str, Any]:
            if not use_ohlc_stress_rollouts:
                raise RuntimeError("ohlc rollouts not active")
            evals: list[dict[str, Any]] = []
            for i in range(int(eff_neuro_stress)):
                bars_i = stress_simulator_ohlc(raw_bars, i, stress_seed=neuro_stress_seed)
                m = ppo_trainer.evaluate_policy_zip_rollouts(
                    policy_path,
                    bars_i,
                    dna_hash=anchor_dna.hash,
                    shadow_max_steps=shadow_max_steps,
                    backtest_max_steps=backtest_max_steps,
                )
                if m.get("ok"):
                    m["_reality_id"] = i
                    evals.append(m)
            if not evals:
                return {"ok": False, "backtest_fitness": float("-inf"), "shadow_equity_delta": 0.0}
            return min(
                evals,
                key=lambda x: float(x.get("backtest_fitness", float("-inf")) or float("-inf")),
            )

        if use_ohlc_stress_rollouts:
            base_eval = _ppo_worst_across_ohlc_bars(baseline_snapshot, list(simulator_data))
        else:
            base_eval = ppo_trainer.evaluate_policy_zip_rollouts(
                baseline_snapshot,
                simulator_data,
                dna_hash=anchor_dna.hash,
                shadow_max_steps=shadow_max_steps,
                backtest_max_steps=backtest_max_steps,
            )
        if not base_eval.get("ok"):
            return {
                "tested": 0,
                "winners": 0,
                "winner_accepted": False,
                "reason": "baseline_rollout_failed",
                **_neuro_meta,
            }

        if not use_ohlc_stress_rollouts:
            base_eval = aggregate_ppo_eval_worst_reality(
                base_eval,
                eff_neuro_stress,
                stress_seed=neuro_stress_seed,
            )
        rollout_baseline = float(base_eval.get("backtest_fitness", float("-inf")))

        def _evaluate_candidate(weight_path: Path, _meta: dict[str, Any]) -> dict[str, Any]:
            if use_ohlc_stress_rollouts:
                metrics = _ppo_worst_across_ohlc_bars(weight_path, list(simulator_data))
            else:
                metrics = ppo_trainer.evaluate_policy_zip_rollouts(
                    weight_path,
                    simulator_data,
                    dna_hash=anchor_dna.hash,
                    shadow_max_steps=shadow_max_steps,
                    backtest_max_steps=backtest_max_steps,
                )
            if not metrics.get("ok"):
                return {"fitness": float("-inf"), "confidence": 0.0, "shadow_passed": False, "backtest_passed": False}

            if not use_ohlc_stress_rollouts:
                metrics = aggregate_ppo_eval_worst_reality(
                    metrics,
                    eff_neuro_stress,
                    stress_seed=neuro_stress_seed,
                )
            shadow_pnl = float(metrics.get("shadow_equity_delta", 0.0) or 0.0)
            candidate_fitness = float(metrics.get("backtest_fitness", float("-inf")))

            shadow_passed = self._guard.shadow_validation_passed(
                shadow_total_pnl=shadow_pnl,
                veto_blocked=False,
                risk_flags=[],
            )
            backtest_passed = bool(candidate_fitness > rollout_baseline)
            confidence = float(0.90 if backtest_passed else 0.80)

            return {
                "fitness": candidate_fitness,
                "confidence": confidence,
                "shadow_passed": shadow_passed,
                "backtest_passed": backtest_passed,
            }

        try:
            population_result = evaluate_weight_population(
                base_model,
                evaluator=_evaluate_candidate,
                population_size=population_size,
                mutation_std=mutation_std,
                mutation_rate=mutation_rate,
                crossover_ratio=crossover_ratio,
                output_dir=self._neuro_weights_path,
                max_workers=1,
                seed=_seed_from_hash(f"neuro:{anchor_dna.hash}:{generation_offset}"),
            )
        except Exception:
            ppo_trainer.load_weights(str(baseline_snapshot))
            return {
                "tested": 0,
                "winners": 0,
                "winner_accepted": False,
                "reason": "population_eval_failed",
                **_neuro_meta,
            }

        winner = population_result.get("winner") if isinstance(population_result, dict) else None
        if not isinstance(winner, dict):
            ppo_trainer.load_weights(str(baseline_snapshot))
            return {
                "tested": len(list(population_result.get("evaluations", []) or [])),
                "winners": 0,
                "winner_accepted": False,
                "reason": "no_passing_weight_candidate",
                **_neuro_meta,
            }

        winner_fitness = float(winner.get("fitness", float("-inf")) or float("-inf"))
        winner_confidence = float(winner.get("confidence", 0.0) or 0.0)
        accepted = self._guard.allows_neuroevolution_winner(
            candidate_confidence=winner_confidence,
            candidate_fitness=winner_fitness,
            current_fitness=rollout_baseline,
        )
        if not accepted:
            ppo_trainer.load_weights(str(baseline_snapshot))
            return {
                "tested": len(list(population_result.get("evaluations", []) or [])),
                "winners": 0,
                "winner_accepted": False,
                "winner_fitness": winner_fitness,
                "winner_confidence": winner_confidence,
                "reason": "guard_rejected_winner",
                **_neuro_meta,
            }

        winner_path = str(winner.get("path", "") or "")
        loaded_winner = ppo_trainer.load_weights(winner_path) if winner_path else None
        if loaded_winner is None:
            ppo_trainer.load_weights(str(baseline_snapshot))
            return {
                "tested": len(list(population_result.get("evaluations", []) or [])),
                "winners": 0,
                "winner_accepted": False,
                "reason": "winner_load_failed",
                **_neuro_meta,
            }

        return {
            "tested": len(list(population_result.get("evaluations", []) or [])),
            "winners": 1,
            "winner_accepted": True,
            "winner_fitness": winner_fitness,
            "winner_confidence": winner_confidence,
            "winner_path": winner_path,
            "evaluations": list(population_result.get("evaluations", []) or []),
            **_neuro_meta,
        }

    def _run_generated_strategy_cycle(
        self,
        *,
        generation_offset: int,
        mode: str,
        base_metrics: dict[str, Any],
        baseline_fitness: float,
        anchor_dna: PolicyDNA,
    ) -> dict[str, Any]:
        if not hasattr(self._sim_runner, "_test_generated_strategy"):
            return {"ideas": 0, "tested": 0, "winners": 0}

        cfg = ConfigLoader.section("evolution", "generated_strategies", default={})
        cfg = cfg if isinstance(cfg, dict) else {}
        min_ideas = max(3, int(cfg.get("min_ideas", 3) or 3))
        max_ideas = max(min_ideas, int(cfg.get("max_ideas", 5) or 5))
        idea_count = random.randint(min_ideas, max_ideas)
        min_backtest_fitness = float(cfg.get("min_backtest_fitness", 0.25) or 0.25)
        min_improvement = float(cfg.get("min_improvement", 0.10) or 0.10)

        generated: list[dict[str, Any]] = []
        for index in range(idea_count):
            hypothesis = self._build_generated_hypothesis(index=index, generation_offset=generation_offset)
            try:
                code = self._strategy_generator.generate_new_strategy(hypothesis)
                sandbox = self._strategy_generator.compile_and_validate(code)
            except Exception:
                continue
            generated.append(
                {
                    "hypothesis": hypothesis,
                    "code": sandbox.code,
                    "metadata": dict(sandbox.metadata),
                }
            )

        if not generated:
            return {"ideas": idea_count, "tested": 0, "winners": 0}

        test_fn = getattr(self._sim_runner, "_test_generated_strategy")
        use_real_data = bool(getattr(self._sim_runner, "real_market_data", False))
        use_backtest_mode = bool(getattr(self._sim_runner, "true_backtest_mode", False))
        evaluated: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(5, len(generated))) as pool:
            future_map = {pool.submit(test_fn, item["code"]): item for item in generated}
            for future in as_completed(future_map):
                item = future_map[future]
                try:
                    fitness = float(future.result())
                except Exception:
                    fitness = float("-inf")
                evaluated.append({**item, "fitness": fitness})

        winners: list[dict[str, Any]] = []
        for item in evaluated:
            metadata = dict(item.get("metadata", {}) or {})
            confidence = float(metadata.get("confidence", 0.0) or 0.0)
            fitness = float(item.get("fitness", float("-inf")) or float("-inf"))
            payload = {
                "strategy_type": "generated",
                "hypothesis": str(item.get("hypothesis", "") or ""),
                "generated_code": str(item.get("code", "") or ""),
                "name": str(metadata.get("name", "generated_strategy") or "generated_strategy"),
                "regime_focus": str(metadata.get("regime_focus", "neutral") or "neutral"),
                "signal_bias": str(metadata.get("signal_bias", "neutral") or "neutral"),
                "confidence": confidence,
            }
            generated_dna = self._registry.mutate(
                parent=anchor_dna,
                mutation_rate=1.0,
                content=payload,
                fitness_score=fitness,
                version="generated_winner",
                lineage_hash=anchor_dna.lineage_hash,
            )

            try:
                shadow_results = self._sim_runner.evaluate_variants(
                    [generated_dna],
                    days=1,
                    nightly_report=base_metrics,
                    shadow_mode=True,
                    real_market_data=use_real_data,
                    true_backtest_mode=use_backtest_mode,
                    parallel_realities=1,
                )
            except TypeError:
                shadow_results = self._sim_runner.evaluate_variants(
                    [generated_dna],
                    days=1,
                    nightly_report=base_metrics,
                    shadow_mode=True,
                    real_market_data=use_real_data,
                    true_backtest_mode=use_backtest_mode,
                )
            shadow_total_pnl = float(shadow_results[0].avg_pnl) if shadow_results else 0.0

            twin_recommendation = True
            twin_risk_flags: list[str] = []
            if str(mode).strip().lower() == "real":
                twin_result = self._approval_twin.evaluate_dna_promotion(generated_dna)
                twin_recommendation = bool(twin_result.get("recommendation", False))
                twin_risk_flags = [str(flag) for flag in list(twin_result.get("risk_flags", []) or [])]

            if not self._guard.generated_strategy_survives(
                mode=mode,
                candidate_confidence=confidence,
                candidate_fitness=fitness,
                current_fitness=baseline_fitness,
                shadow_total_pnl=shadow_total_pnl,
                shadow_risk_flags=twin_risk_flags,
                approval_twin_recommendation=twin_recommendation,
                min_backtest_fitness=min_backtest_fitness,
                min_improvement=min_improvement,
            ):
                continue

            self._registry.register_dna(generated_dna)
            self._append_generated_bible_entry(
                dna=generated_dna,
                hypothesis=payload["hypothesis"],
                code=payload["generated_code"],
                fitness=fitness,
            )
            winners.append({"hash": generated_dna.hash, "fitness": fitness})

        self._append_metrics(
            {
                "event": "generated_strategy_cycle",
                "timestamp": _utcnow(),
                "generation": generation_offset,
                "ideas": idea_count,
                "tested": len(evaluated),
                "winners": len(winners),
                "winner_hashes": [str(item.get("hash", "")) for item in winners],
            }
        )

        return {"ideas": idea_count, "tested": len(evaluated), "winners": len(winners)}

    @staticmethod
    def _build_generated_hypothesis(*, index: int, generation_offset: int) -> str:
        templates = [
            "Design a trend-regime detector with volatility confluence and strict drawdown protection.",
            "Create a mean-reversion entry model with adaptive cooldown in high volatility.",
            "Build a liquidity-aware breakout filter combining volume pulse and momentum fade protection.",
            "Generate an entry-exit logic that avoids chop via regime gating and confidence thresholding.",
            "Invent a confluence rule that combines trend strength, volatility state, and risk-off override.",
        ]
        template = templates[index % len(templates)]
        return f"gen={generation_offset};idea={index};{template}"

    def _append_generated_bible_entry(
        self,
        *,
        dna: PolicyDNA,
        hypothesis: str,
        code: str,
        fitness: float,
    ) -> None:
        self._lumina_bible.append_generated_rule(
            dna_hash=str(dna.hash),
            lineage_hash=str(dna.lineage_hash),
            generation=int(dna.generation),
            fitness=float(fitness),
            hypothesis=str(hypothesis),
            code=str(code),
            status="winner",
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

    def _send_promotion_status_telegram(self, *, dna_hash: str, promoted: bool) -> None:
        status = "PROMOTED" if promoted else "VETOED"
        self._send_shadow_status_telegram(f"{status}\nDNA: {str(dna_hash)[:12]}")

    def _run_shadow_validation_gate(
        self,
        *,
        dna: PolicyDNA,
        winner_fitness: float,
        nightly_report: dict[str, Any],
        signed: bool,
        generation_ok: bool,
        shadow_runner: MultiDaySimRunner,
    ) -> dict[str, Any]:
        if not signed or not generation_ok:
            return {
                "promote_now": False,
                "veto_blocked": False,
                "veto_check": {"is_blocked": False, "reason": "guard_not_satisfied", "active_veto_records": []},
                "shadow_status": "guard_blocked",
                "shadow_passed": False,
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
            return {
                "promote_now": False,
                "veto_blocked": False,
                "veto_check": {"is_blocked": False, "reason": "shadow_started", "active_veto_records": []},
                "shadow_status": "pending",
                "shadow_passed": False,
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
                "shadow_passed": True,
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
                "shadow_passed": False,
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
                return {
                    "promote_now": False,
                    "veto_blocked": True,
                    "veto_check": {"is_blocked": True, "reason": "telegram_veto", "active_veto_records": []},
                    "shadow_status": "vetoed",
                    "shadow_passed": False,
                    "shadow_days_completed": len(daily_pnl),
                    "shadow_days_target": target_days,
                    "shadow_total_pnl": float(sum(daily_pnl)),
                }

            shadow_results = shadow_runner.evaluate_variants(
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

        shadow_total_pnl = float(sum(daily_pnl))
        veto_check = self._veto_window_for_days(target_days).check_with_details(dna_id=dna.hash)
        veto_blocked = bool(veto_check.get("is_blocked", False))

        if len(daily_pnl) < target_days:
            return {
                "promote_now": False,
                "veto_blocked": veto_blocked,
                "veto_check": veto_check,
                "shadow_status": "pending",
                "shadow_passed": False,
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

        return {
            "promote_now": shadow_passed,
            "veto_blocked": veto_blocked,
            "veto_check": veto_check,
            "shadow_status": str(record.get("status", "pending")),
            "shadow_passed": shadow_passed,
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
        dream_report: dict[str, Any] | None = None,
        evolution_mode: str = "sim",
    ) -> list[PolicyDNA]:
        """Produce 5-8 mutant/crossover candidates from top ranked DNA."""
        if not top_dna and active_dna is None:
            return []

        seed_pool = list(top_dna) or []
        if active_dna is not None and not any(d.hash == active_dna.hash for d in seed_pool):
            seed_pool.insert(0, active_dna)

        stress = float((dream_report or {}).get("breach_rate", 0.0) or 0.0)
        if stress > 0.18:
            target_count = random.randint(6, 8)
        else:
            target_count = random.randint(5, 8)
        candidates: list[PolicyDNA] = []
        base = seed_pool[0]
        for i in range(target_count):
            rate = round(0.1 + (i * 0.1), 2)
            if i < 4 or len(seed_pool) < 2:
                # Pure mutation
                new_content = mutate_prompt(base.content, rate)
                new_content = _apply_dream_learnings_to_dna_content(
                    new_content, dream_report, evolution_mode=evolution_mode
                )
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
                new_content = _apply_dream_learnings_to_dna_content(
                    new_content, dream_report, evolution_mode=evolution_mode
                )
                candidate = self._registry.mutate(
                    parent=base,
                    mutation_rate=rate,
                    content=new_content,
                    fitness_score=(base.fitness_score + other.fitness_score) / 2.0,
                    version="candidate",
                    lineage_hash=base.lineage_hash,
                    crossover=other,
                )

            # Pre-mutation constitutional screening (fast, in-process).
            pre_check = self._constitutional_guard.check_pre_mutation(
                candidate.content, mode=evolution_mode
            )
            if not pre_check.passed:
                logger.warning(
                    "Pre-mutation check blocked candidate %s: %s",
                    candidate.hash[:12],
                    pre_check.violation_names,
                )
                continue  # Skip this candidate; do not register.

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
                    "generated_tested": int(r.generated_tested),
                    "generated_winners": int(r.generated_winners),
                    "neuro_tested": int(r.neuro_tested),
                    "neuro_winners": int(r.neuro_winners),
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
