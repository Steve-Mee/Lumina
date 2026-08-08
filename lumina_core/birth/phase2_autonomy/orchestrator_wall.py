"""Phase2WallEvalMixin (M5 phase2 orchestrator extract)."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.phase2_autonomy.contracts import (
    Phase2OrchestratorDecision,
    Phase2Pillar,
)
from lumina_core.birth.phase2_autonomy.dynamic_wall import (
    apply_wall_adjustment_to_thresholds,
    propose_dynamic_wall_adjustment,
)
from lumina_core.birth.phase2_autonomy.gates import evaluate_phase2_gate


class Phase2WallEvalMixin:
    def evaluate_dynamic_wall(
        self,
        *,
        correlation_id: str = "",
        stage: str = "",
        stage_trades: int = 0,
        required: int = 0,
        winrate_slope: float = 0.0,
        winrate_stagnation_count: int = 0,
        hold_stagnation_count: int = 0,
        elapsed_stage_sec: float = 0.0,
        regime: str | None = None,
        constitution_violations: int = 0,
        apply: bool = False,
    ) -> Phase2OrchestratorDecision:
        proposal = propose_dynamic_wall_adjustment(
            stage=stage,
            stage_trades=stage_trades,
            required=required,
            winrate_slope=winrate_slope,
            winrate_stagnation_count=winrate_stagnation_count,
            hold_stagnation_count=hold_stagnation_count,
            elapsed_stage_sec=elapsed_stage_sec,
            regime=regime,
            cfg=self.cfg,
        )
        self._publish_proposal(
            pillar=Phase2Pillar.DYNAMIC_WALL,
            correlation_id=correlation_id,
            stage=stage,
            proposal=proposal.to_dict(),
        )
        require_apply = self._require_apply_path(apply)
        gate = evaluate_phase2_gate(
            features=self.features,
            pillar=Phase2Pillar.DYNAMIC_WALL,
            constitution_violations=constitution_violations,
            mode=self.mode,
            approval_twin=self.approval_twin if require_apply else None,
            proposal=proposal,
            require_apply_path=require_apply,
        )
        self._publish_gate(correlation_id=correlation_id, stage=stage, gate=gate)

        mutate_payload: dict[str, Any] = {}
        if apply and gate.allowed:
            base_wall = 600.0
            wr_stag = 3
            hold_stag = 3
            if self.cfg is not None:
                base_wall = float(
                    getattr(self.cfg, "certified_stage_stall_wall_sec", base_wall) or base_wall
                )
                wr_stag = int(
                    getattr(self.cfg, "stage1_winrate_stagnation_rollouts", wr_stag) or wr_stag
                )
                hold_stag = int(
                    getattr(self.cfg, "stage2_hold_stagnation_rollouts", hold_stag) or hold_stag
                )
            mutate_payload = apply_wall_adjustment_to_thresholds(
                base_stall_wall_sec=base_wall,
                base_winrate_stagnation_rollouts=wr_stag,
                base_hold_stagnation_rollouts=hold_stag,
                proposal=proposal,
            )
        applied, apply_payload, shadow_would = self._resolve_apply(
            apply=apply,
            gate_allowed=bool(gate.allowed),
            mutate_payload=mutate_payload,
        )

        decision = Phase2OrchestratorDecision(
            pillar=Phase2Pillar.DYNAMIC_WALL.value,
            proposal=proposal.to_dict(),
            gate=gate,
            applied=applied,
            apply_payload=apply_payload,
        )
        self._audit_decision(
            decision,
            correlation_id=correlation_id,
            stage=stage,
            constitution_violations=constitution_violations,
            apply_requested=apply,
            recovery_tag="wall",
            shadow_would_apply=shadow_would,
        )
        return decision


