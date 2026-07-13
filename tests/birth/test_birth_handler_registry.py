"""Tests for BirthHandlerRegistry lifecycle and response cache."""

from __future__ import annotations

import pytest

from lumina_core.agent_orchestration.event_bus import EventBus
from lumina_core.birth.birth_handler_registry import BirthHandlerRegistry
from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig


@pytest.mark.unit
def test_attach_detach_idempotent() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig()
    reward = BirthRewardConfig()
    registry = BirthHandlerRegistry(bus, cfg, reward)

    token1 = registry.attach_all()
    token2 = registry.attach_all()
    assert token1 == token2
    assert registry._attached is True

    registry.detach_all()
    registry.detach_all()
    assert registry._attached is False


@pytest.mark.unit
def test_response_cache_pop_and_get() -> None:
    bus = EventBus()
    registry = BirthHandlerRegistry(bus, BirthCurriculumConfig(), BirthRewardConfig())

    registry.set_response("cid-1", "meta_plan", {"primary": "hold"})
    registry.set_response("cid-1", "stall", {"is_stalled": True})

    assert registry.get_response("cid-1")["meta_plan"]["primary"] == "hold"
    popped = registry.pop_response("cid-1")
    assert popped["stall"]["is_stalled"] is True
    assert registry.get_response("cid-1") == {}


@pytest.mark.unit
def test_sync_birth_cfg_refreshes_controller() -> None:
    bus = EventBus()
    cfg = BirthCurriculumConfig(meta_controller_enabled=True)
    reward = BirthRewardConfig()
    registry = BirthHandlerRegistry(bus, cfg, reward)

    new_cfg = BirthCurriculumConfig(meta_controller_enabled=True, exploration_chunk_size=99)
    new_reward = BirthRewardConfig(expectancy_coeff=0.9)
    registry.sync_birth_cfg(new_cfg, new_reward)

    assert registry.curriculum_cfg.exploration_chunk_size == 99
    assert registry.meta.cfg.exploration_chunk_size == 99
    assert registry.meta.controller.cfg.exploration_chunk_size == 99
    assert registry.reward_cfg.expectancy_coeff == 0.9
