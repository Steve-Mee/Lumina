"""Code evolution pipeline: constitution → twin → sandbox → optional sandbox apply.

Fail-closed. Default disabled. H5: apply only to sandbox store under hard gates
(never live repo / REAL capital).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from lumina_core.audit import get_audit_logger
from lumina_core.code_evolution.apply_gate import ApplyPolicy, CodeEvolutionApplyGate
from lumina_core.code_evolution.constitution import CodeEvolutionConstitution
from lumina_core.code_evolution.journal import CodeEvolutionJournal
from lumina_core.code_evolution.operators import CodeEvolutionController
from lumina_core.code_evolution.proposal import (
    CodeEvolutionCycleResult,
)

from lumina_core.code_evolution.pipeline_process import CodeEvolutionProcessMixin
from lumina_core.code_evolution.pipeline_finalize import CodeEvolutionFinalizeMixin

logger = logging.getLogger(__name__)

AUDIT_STREAM = "evolution.code_mutation"


class CodeEvolutionPipeline(CodeEvolutionProcessMixin, CodeEvolutionFinalizeMixin):
    """Orchestrates one gated cycle of trading-code evolution proposals."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        max_proposals_per_cycle: int = 1,
        mode: str = "sim",
        timeout_s: int = 30,
        controller: CodeEvolutionController | None = None,
        constitution: CodeEvolutionConstitution | None = None,
        sandbox: Any | None = None,
        journal: CodeEvolutionJournal | None = None,
        twin: Any | None = None,
        event_bus: Any | None = None,
        constitutional_guard: Any | None = None,
        journal_root: Path | str | None = None,
        audit_path: Path | str | None = None,
        require_twin: bool = True,
        apply_policy: ApplyPolicy | dict[str, Any] | None = None,
    ) -> None:
        # Lazy import avoids circular: sandboxed_code_executor → proposal → package → pipeline
        from lumina_core.safety.sandboxed_code_executor import SandboxedCodeExecutor

        self.enabled = bool(enabled)
        self.mode = str(mode or "sim").strip().lower()
        self.require_twin = bool(require_twin)
        self.controller = controller or CodeEvolutionController(
            enabled=self.enabled,
            max_proposals_per_cycle=max_proposals_per_cycle,
        )
        # Keep controller enable flag in sync
        self.controller.enabled = self.enabled
        self.constitution = constitution or CodeEvolutionConstitution()
        self.sandbox = sandbox or SandboxedCodeExecutor(timeout_s=timeout_s)
        self.journal = journal or CodeEvolutionJournal(root=journal_root)
        self.twin = twin
        self.event_bus = event_bus
        self.constitutional_guard = constitutional_guard
        if isinstance(apply_policy, ApplyPolicy):
            self.apply_policy = apply_policy
        else:
            self.apply_policy = ApplyPolicy.from_config(
                apply_policy if isinstance(apply_policy, dict) else None
            )
        self._apply_gate = CodeEvolutionApplyGate(
            journal_root=self.journal.root,
            policy=self.apply_policy,
        )
        self._audit_path = Path(audit_path) if audit_path else Path("state/code_evolution_audit.jsonl")
        try:
            get_audit_logger().register_stream(AUDIT_STREAM, self._audit_path)
        except Exception:
            logger.debug("code_evolution audit stream register best-effort failed", exc_info=True)

        self.metrics: dict[str, int] = {
            "proposals": 0,
            "constitution_blocks": 0,
            "twin_blocks": 0,
            "sandbox_passes": 0,
            "sandbox_fails": 0,
            "sandbox_applies": 0,
            "apply_blocks": 0,
            "cycles": 0,
        }

    def run_cycle(
        self,
        *,
        current_params: dict[str, float] | None = None,
        seed: str | None = None,
    ) -> CodeEvolutionCycleResult:
        self.metrics["cycles"] += 1
        if not self.enabled:
            return CodeEvolutionCycleResult(
                enabled=False,
                proposals=[],
                decisions=[],
                metrics=self._metrics_payload(),
            )

        proposals = self.controller.propose(current_params=current_params, seed=seed)
        decisions: list[dict[str, Any]] = []
        for prop in proposals:
            decisions.append(self._process_proposal(prop))

        return CodeEvolutionCycleResult(
            enabled=True,
            proposals=proposals,
            decisions=decisions,
            metrics=self._metrics_payload(),
        )

def run_code_evolution_dry_cycle(
    *,
    enabled: bool = False,
    max_proposals_per_cycle: int = 1,
    mode: str = "sim",
    twin: Any | None = None,
    event_bus: Any | None = None,
    constitutional_guard: Any | None = None,
    journal_root: Path | str | None = None,
    seed: str | None = None,
    current_params: dict[str, float] | None = None,
    timeout_s: int = 30,
    require_twin: bool = True,
    apply_policy: ApplyPolicy | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Public entrypoint for gated cycle (default disabled; apply default off)."""
    pipe = CodeEvolutionPipeline(
        enabled=enabled,
        max_proposals_per_cycle=max_proposals_per_cycle,
        mode=mode,
        twin=twin,
        event_bus=event_bus,
        constitutional_guard=constitutional_guard,
        journal_root=journal_root,
        timeout_s=timeout_s,
        require_twin=require_twin,
        apply_policy=apply_policy,
    )
    result = pipe.run_cycle(current_params=current_params, seed=seed)
    return result.to_dict()
