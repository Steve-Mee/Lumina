"""PhoenixHandler EventBus integration tests."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_bus_client import BirthBusClient
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.birth.curriculum import CurriculumStage


@pytest.mark.unit
def test_phoenix_handler_begin_cycle_publishes_event() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(phoenix_loop_enabled=True, phoenix_max_cycles=3)
    reward = BirthRewardConfig()
    client = BirthBusClient(bus, cfg, reward)

    patch = client.phoenix_begin_cycle(
        CurriculumStage.STAGE1_TREND,
        stall_reason="phoenix_cycle",
        novelty="expand_data",
    )
    assert isinstance(patch, dict)
    assert bus.latest("birth.phoenix.cycle") is not None
