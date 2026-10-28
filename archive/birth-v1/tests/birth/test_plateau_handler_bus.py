"""PlateauHandler EventBus integration tests."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage


@pytest.mark.unit
def test_plateau_handler_trap_detection_publishes_fact() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(plateau_detection_enabled=True)
    reward = BirthRewardConfig()
    client = BirthBusClient(bus, cfg, reward)

    trapped = client.plateau_detect_over_trading_trap(
        CurriculumStage.STAGE2_RANGE,
        range_flat_ratio=0.05,
        range_round_trips=80,
        required=500,
        velocity_stall=True,
    )
    assert isinstance(trapped, bool)
    assert bus.latest("birth.plateau.trap.detected") is not None
