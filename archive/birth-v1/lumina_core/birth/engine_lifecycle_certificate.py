"""Certificate + runway + polish (M5 engine_lifecycle extract)."""
from __future__ import annotations

from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.engine")


class EngineLifecycleCertificateMixin:
    def _ensure_holdout_preflight(
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
        return self._certificate_pipeline().ensure_holdout_preflight(ticks=ticks, split=split, max_days=max_days, prefer_real=prefer_real, start_price=start_price, training_mode=training_mode, reuse_manifest=reuse_manifest, saved_manifest=saved_manifest)

    def _run_certificate_remediation(
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
        return self._certificate_pipeline().run_certificate_remediation(split=split, eval_result=eval_result, training_mode=training_mode, ppo_steps_per_update=ppo_steps_per_update, trade_budget_cap=trade_budget_cap, prefer_real=prefer_real, start_price=start_price)

    def _resolve_birth_exit_winrate(self) -> float:
        return self._certificate_pipeline().resolve_birth_exit_winrate()

    def _resolve_baseline_oos_winrate(self, *, checkpoint_state: dict[str, Any] | None = None) -> float:
        return self._certificate_pipeline().resolve_baseline_oos_winrate(checkpoint_state=checkpoint_state)

    def _bootstrap_runway_stage5(self, *, train_ticks: list[dict[str, Any]]) -> None:
        return self._certificate_pipeline().bootstrap_runway_stage5(train_ticks=train_ticks)

    def _run_certificate_runway_stages(
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
        return self._certificate_pipeline().run_certificate_runway_stages(split=split, validation_ticks=validation_ticks, train_core_ticks=train_core_ticks, training_mode=training_mode, ppo_steps_per_update=ppo_steps_per_update, trade_budget_cap=trade_budget_cap, prefer_real=prefer_real, start_price=start_price, baseline_oos_winrate=baseline_oos_winrate, birth_exit_winrate=birth_exit_winrate)

    def _fail_certificate_with_runway_checkpoint(
        self,
        *,
        eval_result: dict[str, Any],
        training_mode: str,
        trade_budget_cap: int,
    ) -> dict[str, Any]:
        return self._certificate_pipeline().fail_certificate_with_runway_checkpoint(eval_result=eval_result, training_mode=training_mode, trade_budget_cap=trade_budget_cap)

    def _run_stage8_polish_and_certificate(
        self,
        *,
        split: Any,
        training_mode: str,
        ppo_steps_per_update: int,
        trade_budget_cap: int,
        prefer_real: bool,
        start_price: float,
    ) -> dict[str, Any]:
        return self._certificate_pipeline().run_stage8_polish_and_certificate(split=split, training_mode=training_mode, ppo_steps_per_update=ppo_steps_per_update, trade_budget_cap=trade_budget_cap, prefer_real=prefer_real, start_price=start_price)

    def _complete_certified_birth(
        self,
        *,
        split: Any,
        eval_result: dict[str, Any],
        training_mode: str,
        trade_budget_cap: int,
    ) -> dict[str, Any]:
        return self._certificate_pipeline().complete_certified_birth(split=split, eval_result=eval_result, training_mode=training_mode, trade_budget_cap=trade_budget_cap)


