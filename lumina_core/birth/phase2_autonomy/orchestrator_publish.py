"""Phase2PublishMixin (M5 phase2 orchestrator extract)."""
from __future__ import annotations

import logging
from typing import Any

from lumina_core.birth.phase2_autonomy.contracts import Phase2GateResult, Phase2Pillar

logger = logging.getLogger("lumina.birth.phase2_autonomy")


class Phase2PublishMixin:
    def _publish_proposal(
        self,
        *,
        pillar: Phase2Pillar,
        correlation_id: str,
        stage: str,
        proposal: dict[str, Any],
    ) -> None:
        if self.event_bus is None or not self.features.enabled:
            return
        try:
            from lumina_core.birth.birth_bus_choreography import (
                publish_phase2_instance_proposal,
                publish_phase2_param_proposal,
                publish_phase2_wall_proposal,
            )

            if pillar == Phase2Pillar.DYNAMIC_WALL:
                publish_phase2_wall_proposal(
                    self.event_bus,
                    producer="birth.phase2_autonomy",
                    correlation_id=correlation_id,
                    stage=stage,
                    proposal=proposal,
                )
            elif pillar == Phase2Pillar.SELF_ADAPTIVE_PARAMS:
                publish_phase2_param_proposal(
                    self.event_bus,
                    producer="birth.phase2_autonomy",
                    correlation_id=correlation_id,
                    stage=stage,
                    proposal=proposal,
                )
            elif pillar == Phase2Pillar.INSTANCE_ADAPT:
                publish_phase2_instance_proposal(
                    self.event_bus,
                    producer="birth.phase2_autonomy",
                    correlation_id=correlation_id,
                    stage=stage,
                    proposal=proposal,
                )
        except Exception:
            logger.debug("phase2 publish proposal best-effort failed", exc_info=True)

    def _publish_gate(
        self,
        *,
        correlation_id: str,
        stage: str,
        gate: Phase2GateResult,
    ) -> None:
        if self.event_bus is None or not self.features.enabled:
            return
        try:
            from lumina_core.birth.birth_bus_choreography import publish_phase2_gate_result

            publish_phase2_gate_result(
                self.event_bus,
                producer="birth.phase2_autonomy",
                correlation_id=correlation_id,
                stage=stage,
                gate=gate.to_dict(),
            )
        except Exception:
            logger.debug("phase2 publish gate best-effort failed", exc_info=True)



