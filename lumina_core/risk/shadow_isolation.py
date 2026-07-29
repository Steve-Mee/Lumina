"""Shadow isolation / isolated orchestrator helpers."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from lumina_core.logging_utils import get_logger
from lumina_core.risk.orchestration import RiskOrchestrator
from lumina_core.risk.shadow_registry import ShadowRunRegistry

if TYPE_CHECKING:
    from lumina_core.risk.shadow import ShadowRiskEvaluator

logger = get_logger("lumina.risk.shadow")


class ShadowIsolationMixin:
    _shadow_orchestrator: RiskOrchestrator | None
    engine: Any

    @classmethod
    def with_persistent_registry(
        cls,
        engine: Any,
        storage_path: str | Path,
        **kwargs
    ) -> "ShadowRiskEvaluator":
        """
        Convenience constructor that returns a `ShadowRiskEvaluator` with a
        file-backed `ShadowRunRegistry` already attached.

        This is the easiest way to get the full durable shadow deployment
        experience in one line.

        Example:
            evaluator = ShadowRiskEvaluator.with_persistent_registry(
                engine=engine,
                storage_path=Path("shadow_experiments.jsonl")
            )

            result = evaluator.execute_shadow_experiment(
                experiment_id=...,
                ...
            )
        """
        registry = ShadowRunRegistry(storage_path=storage_path)
        return cls(engine=engine, registry=registry, **kwargs)

    def _get_isolated_orchestrator(self) -> RiskOrchestrator:
        """
        Returns a fresh, isolated RiskOrchestrator instance for shadow use only.

        This is critical: we do NOT reuse the live engine's orchestrator.
        Any future attempt to bypass this isolation will be caught by aperture_guard.
        """
        if self._shadow_orchestrator is None:
            # Create a completely separate orchestrator instance.
            # It will still read config for policy/limits, but we will never allow
            # it to proceed to any broker submission path.
            orchestrator = RiskOrchestrator(engine=self.engine)
            orchestrator.initialize()

            # The isolation guarantee comes from:
            # 1. Fresh object instance (never the live one)
            # 2. Hard aperture_guard calls on every entry point
            # 3. Never wiring this orchestrator to any broker submission path
            self._shadow_orchestrator = orchestrator

        return self._shadow_orchestrator

    def _enforce_shadow_isolation(self, operation: str) -> None:
        """
        Hard guard. Any code path that reaches real execution from shadow context
        must die here with a clear ConstitutionViolation.
        """
        from lumina_core.risk.aperture_guard import enforce_no_bypass_in_strict_mode
        enforce_no_bypass_in_strict_mode(
            engine=self.engine,
            bypass_id=f"shadow_isolation_violation:{operation}",
            caller="ShadowRiskEvaluator._enforce_shadow_isolation",
            reason="Shadow execution attempted to reach live capital path. This is forbidden.",
        )
