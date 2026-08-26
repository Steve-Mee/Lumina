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

Thin façade composing generation + promotion mixins (Wave B PR-B2).
Bounded modules: ``orchestrator_generation``, ``orchestrator_promotion``.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Sequence

from lumina_core.config_loader import ConfigLoader
from lumina_core.governance import ApprovalChain, SignedApproval
from lumina_core.notifications.notification_scheduler import NotificationScheduler
from lumina_core.notifications.telegram_notifier import TelegramNotifier
from lumina_core.safety.constitutional_guard import ConstitutionalGuard

from .approval_gym_scheduler import ApprovalGymScheduler
from .approval_twin_agent import ApprovalTwinAgent
from .dna_registry import DNARegistry
from .lumina_bible import LuminaBible
from .meta_swarm import MetaSwarm
from .multi_day_sim_runner import MultiDaySimRunner
from .mutation_pipeline import MutationPipeline
from .orchestrator_generation import GenerationResult, OrchestratorGenerationMixin
from .orchestrator_promotion import OrchestratorPromotionMixin
from .promotion_gate import PromotionGate
from .promotion_policy import PromotionPolicy
from .rollout import EvolutionRolloutFramework
from .steve_values_registry import SteveValuesRegistry
from .strategy_generator import StrategyGenerator
from .veto_registry import VetoRegistry
from .veto_window import VetoWindow

_METRICS_PATH = Path("logs/evolution_metrics.jsonl")
_SHADOW_STATE_PATH = Path("state/evolution_shadow_runs.json")
_NEURO_WEIGHTS_PATH = Path("state/neuro_weights")
logger = logging.getLogger(__name__)


def _compat() -> Any:
    from lumina_core.evolution import evolution_orchestrator as compat_module

    return compat_module


class EvolutionOrchestrator(OrchestratorGenerationMixin, OrchestratorPromotionMixin):
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
        self._guard = _compat().EvolutionGuard()
        self._values_registry = SteveValuesRegistry()
        self._approval_twin = ApprovalTwinAgent(registry=self._values_registry, event_bus=None)
        self._veto_registry = VetoRegistry()
        self._veto_window = VetoWindow(veto_registry=self._veto_registry, window_seconds=1800)
        self._telegram_notifier = TelegramNotifier(veto_registry=self._veto_registry)
        self._notification_scheduler = NotificationScheduler()
        self._market_data_service: Any | None = None
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
        self._rollout_framework = EvolutionRolloutFramework()
        # AGI Safety: single guard instance shared across all generation cycles.
        self._constitutional_guard = ConstitutionalGuard()
        self._mutation_pipeline = MutationPipeline(
            registry=self._registry,
            constitutional_guard=self._constitutional_guard,
            logger=logger,
        )
        self._promotion_gate = PromotionGate()
        self._promotion_policy = PromotionPolicy(owner=self, logger=logger, event_bus=None)
        self._approval_chain = ApprovalChain()
        self._initialized = True

    def bind_market_data_service(self, market_data_service: Any | None) -> None:
        self._market_data_service = market_data_service
        self._sim_runner = self._create_sim_runner()

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
        if not isinstance(mw_cfg, dict):
            mw_cfg = {}
        use_real_data = bool(mw_cfg.get("use_real_market_data", True))
        use_backtest_mode = bool(
            mw_cfg.get("backtest_mode", mw_cfg.get("true_backtest_mode", True))
        )

        market_data_service = self._market_data_service if use_real_data else None
        if use_real_data and market_data_service is None:
            try:
                from lumina_core.evolution.fitness_ssot import birth_tick_cache_mds

                market_data_service = birth_tick_cache_mds(Path.cwd())
            except Exception:
                market_data_service = None
            if market_data_service is None:
                logger.warning("[EVOLUTION] real_market_data enabled but market_data_service unavailable")

        return MultiDaySimRunner(
            max_workers=8,
            drawdown_limit_ratio=0.02,
            real_market_data=use_real_data,
            true_backtest_mode=use_backtest_mode,
            market_data_service=market_data_service,
        )

    def _run_single_generation(
        self,
        *,
        generation_offset: int,
        mode: str,
        explicit_human_approval: bool,
        require_human_approval: bool,
        real_promotion_approvals: Sequence[SignedApproval] | None,
        base_metrics: dict[str, Any],
        sim_days: int,
    ) -> GenerationResult:
        from lumina_core.evolution.generation_runner import run_single_generation

        return run_single_generation(
            self,
            generation_offset=generation_offset,
            mode=mode,
            explicit_human_approval=explicit_human_approval,
            require_human_approval=require_human_approval,
            real_promotion_approvals=real_promotion_approvals,
            base_metrics=base_metrics,
            sim_days=sim_days,
        )


__all__ = ["EvolutionOrchestrator", "GenerationResult"]
