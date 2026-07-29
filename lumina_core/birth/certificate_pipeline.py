"""Birth certificate preflight, runway, remediation, and completion pipeline.

Bounded modules: ``certificate_preflight``, ``certificate_remediation``,
``certificate_runway``, ``certificate_evaluate``. Host class keeps thin delegates.
"""
from __future__ import annotations

from typing import Any

from lumina_core.birth.certificate_evaluator import evaluate_holdout_certificate  # noqa: F401
from lumina_core.birth.data_expansion import clamp_expansion_steps, expand_birth_data  # noqa: F401
from lumina_core.birth.news_enricher import enrich_ticks_with_news  # noqa: F401
from lumina_core.birth.preflight import assess_split_preflight, data_manifest_from_split  # noqa: F401
from lumina_core.birth.runway import micro_oos_sanity_passed  # noqa: F401
from lumina_core.birth.sim_runner import run_policy_rollout  # noqa: F401
from lumina_core.birth import certificate_evaluate as _evaluate
from lumina_core.birth import certificate_preflight as _preflight
from lumina_core.birth import certificate_remediation as _remediation
from lumina_core.birth import certificate_runway as _runway
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.certificate_pipeline")


class BirthCertificatePipeline:
    def __init__(self, host: Any) -> None:
        self._host = host

    def ensure_holdout_preflight(
        self,
        *,
        ticks: list[dict[str, Any]],
        split: Any,
        max_days: int,
        prefer_real: bool,
        start_price: float,
        training_mode: str,
        reuse_manifest: bool = False,
        saved_manifest: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], Any, dict[str, Any]] | dict[str, Any]:
        return _preflight.ensure_holdout_preflight(
            self,
            ticks=ticks,
            split=split,
            max_days=max_days,
            prefer_real=prefer_real,
            start_price=start_price,
            training_mode=training_mode,
            reuse_manifest=reuse_manifest,
            saved_manifest=saved_manifest,
        )

    def run_certificate_remediation(
        self,
        *,
        split: Any,
        eval_result: dict[str, Any],
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
    ) -> dict[str, Any]:
        return _remediation.run_certificate_remediation(
            self,
            split=split,
            eval_result=eval_result,
            training_mode=training_mode,
            ppo_steps_per_update=ppo_steps_per_update,
            trade_budget_cap=trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
        )

    def resolve_birth_exit_winrate(self) -> float:
        return _runway.resolve_birth_exit_winrate(self)

    def resolve_baseline_oos_winrate(self, *, checkpoint_state: dict[str, Any] | None = None) -> float:
        return _runway.resolve_baseline_oos_winrate(self, checkpoint_state=checkpoint_state)

    def bootstrap_runway_stage5(self, *, train_ticks: list[dict[str, Any]]) -> None:
        return _runway.bootstrap_runway_stage5(self, train_ticks=train_ticks)

    def run_certificate_runway_stages(
        self,
        *,
        split: Any,
        validation_ticks: list[dict[str, Any]],
        train_core_ticks: list[dict[str, Any]],
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
        baseline_oos_winrate: float,
        birth_exit_winrate: float,
    ) -> dict[str, Any] | None:
        return _runway.run_certificate_runway_stages(
            self,
            split=split,
            validation_ticks=validation_ticks,
            train_core_ticks=train_core_ticks,
            training_mode=training_mode,
            ppo_steps_per_update=ppo_steps_per_update,
            trade_budget_cap=trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
            baseline_oos_winrate=baseline_oos_winrate,
            birth_exit_winrate=birth_exit_winrate,
        )

    def fail_certificate_with_runway_checkpoint(
        self,
        *,
        eval_result: dict[str, Any],
        training_mode: str,
        trade_budget_cap: int,
    ) -> dict[str, Any]:
        return _runway.fail_certificate_with_runway_checkpoint(
            self,
            eval_result=eval_result,
            training_mode=training_mode,
            trade_budget_cap=trade_budget_cap,
        )

    def run_stage8_polish_and_certificate(
        self,
        *,
        split: Any,
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
    ) -> dict[str, Any]:
        return _evaluate.run_stage8_polish_and_certificate(
            self,
            split=split,
            training_mode=training_mode,
            ppo_steps_per_update=ppo_steps_per_update,
            trade_budget_cap=trade_budget_cap,
            prefer_real=prefer_real,
            start_price=start_price,
        )

    def complete_certified_birth(
        self,
        *,
        split: Any,
        eval_result: dict[str, Any],
        training_mode: str,
        trade_budget_cap: int,
    ) -> dict[str, Any]:
        return _evaluate.complete_certified_birth(
            self,
            split=split,
            eval_result=eval_result,
            training_mode=training_mode,
            trade_budget_cap=trade_budget_cap,
        )
