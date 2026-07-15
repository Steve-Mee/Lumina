"""Thin lifecycle registry for birth EventBus SRP handlers."""

from __future__ import annotations

from typing import Any

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.meta_controller_handler import MetaControllerHandler
from lumina_core.birth.organism_autonomy_handler import OrganismAutonomyHandler
from lumina_core.birth.phoenix_handler import PhoenixHandler
from lumina_core.birth.plateau_handler import PlateauHandler
from lumina_core.birth.remediation_handler import RemediationHandler
from lumina_core.birth.wall_adaptation_handler import WallAdaptationHandler


class BirthHandlerRegistry:
    """Owns handler instances and synchronous response cache (not domain logic)."""

    def __init__(
        self,
        event_bus: EventBus,
        curriculum_cfg: BirthCurriculumConfig,
        reward_cfg: BirthRewardConfig,
        *,
        approval_twin: Any | None = None,
    ) -> None:
        self.bus = event_bus
        self.curriculum_cfg = curriculum_cfg
        self.reward_cfg = reward_cfg
        self.approval_twin = approval_twin
        self._responses: dict[str, dict[str, Any]] = {}
        self.meta = MetaControllerHandler(
            event_bus,
            curriculum_cfg,
            reward_cfg,
            registry=self,
            approval_twin=approval_twin,
        )
        self.plateau = PlateauHandler(event_bus, curriculum_cfg, registry=self)
        self.remediation = RemediationHandler(event_bus, curriculum_cfg, registry=self)
        self.phoenix = PhoenixHandler(event_bus, curriculum_cfg, registry=self)
        self.autonomy = OrganismAutonomyHandler(
            event_bus, curriculum_cfg, registry=self, approval_twin=approval_twin
        )
        self.wall_adaptation = WallAdaptationHandler(event_bus, curriculum_cfg, registry=self)
        self._attached = False

    def set_response(self, correlation_id: str, key: str, value: Any) -> None:
        self._responses.setdefault(str(correlation_id), {})[key] = value

    def pop_response(self, correlation_id: str) -> dict[str, Any]:
        return self._responses.pop(str(correlation_id), {})

    def get_response(self, correlation_id: str) -> dict[str, Any]:
        return dict(self._responses.get(str(correlation_id), {}))

    def attach_all(self) -> None:
        if self._attached:
            return
        self.meta.attach()
        self.plateau.attach()
        self.remediation.attach()
        self.phoenix.attach()
        self.autonomy.attach()
        self.wall_adaptation.attach()
        self._attached = True

    def detach_all(self) -> None:
        if not self._attached:
            return
        self.meta.detach()
        self.plateau.detach()
        self.remediation.detach()
        self.phoenix.detach()
        self.autonomy.detach()
        self.wall_adaptation.detach()
        self._attached = False

    def sync_curriculum_cfg(self, cfg: BirthCurriculumConfig) -> None:
        """Refresh handler cfg after host birth_config is replaced (tests / hot reload)."""
        self.curriculum_cfg = cfg
        self.meta.cfg = cfg
        self.meta.controller.cfg = cfg
        self.plateau.cfg = cfg
        self.remediation.cfg = cfg
        self.phoenix.cfg = cfg
        self.autonomy.cfg = cfg
        self.wall_adaptation.cfg = cfg

    def sync_birth_cfg(self, curriculum: BirthCurriculumConfig, reward: BirthRewardConfig) -> None:
        """Refresh curriculum + reward refs across birth EventBus handlers."""
        self.reward_cfg = reward
        self.sync_curriculum_cfg(curriculum)
        from lumina_core.birth.meta_controller import BirthMetaController

        twin = getattr(self, "approval_twin", None) or getattr(self.meta, "approval_twin", None)
        self.meta.controller = BirthMetaController(curriculum, reward, approval_twin=twin)
        self.meta.approval_twin = twin
        if hasattr(self.autonomy, "approval_twin"):
            self.autonomy.approval_twin = twin

    def bind_approval_twin(self, approval_twin: Any | None) -> None:
        """Late-bind ApprovalTwin after bus wiring (orchestrator/container)."""
        self.approval_twin = approval_twin
        self.meta.approval_twin = approval_twin
        if hasattr(self.meta, "controller") and self.meta.controller is not None:
            self.meta.controller.approval_twin = approval_twin
        self.autonomy.approval_twin = approval_twin


__all__ = ["BirthHandlerRegistry"]
