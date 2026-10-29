"""D1/D8: yaml and env cannot reopen the ungated-place freeze."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from lumina_core.order_gatekeeper.ungated_place_block import (
    S0_PLACE_SOURCE_ALLOWLIST,
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
    freeze_is_armed,
    research_execution_mode_from_mapping,
)
from tests.test_order_path_regression import _make_service

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_config_yaml_shadow_key_is_observability_only() -> None:
    loaded = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    assert loaded["research_execution_mode"] == "shadow"
    assert research_execution_mode_from_mapping(loaded) == "shadow"
    assert freeze_is_armed() is True
    allowed, reason = assert_validation_gate_or_block("operations_service_orders.place_order", order_side="BUY")
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_yaml_sim_and_mode_sim_still_block() -> None:
    cfg = {"research_execution_mode": "sim", "mode": "sim", "trade_mode": "sim"}
    assert research_execution_mode_from_mapping(cfg) == "sim"
    assert freeze_is_armed() is True
    svc, container = _make_service("sim")
    assert svc.place_order("BUY", 1) is False
    container.broker.submit_order.assert_not_called()
    allowed, reason = assert_validation_gate_or_block(
        "supervisor_tick_exec.run_tick_exec",
        order_side="BUY",
        source_agent="research_bridge",
    )
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_missing_or_illegal_mode_parses_as_off_and_still_blocks() -> None:
    assert research_execution_mode_from_mapping(None) == "off"
    assert research_execution_mode_from_mapping({}) == "off"
    assert research_execution_mode_from_mapping({"research_execution_mode": "live"}) == "off"
    assert research_execution_mode_from_mapping({"research_execution_mode": ""}) == "off"
    allowed, reason = assert_validation_gate_or_block("reasoning_service.submit_order", order_side="SELL")
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_env_cannot_reopen_freeze(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEARCH_EXECUTION_MODE", "sim")
    monkeypatch.setenv("LUMINA_TRADE_MODE", "sim")
    monkeypatch.setenv("LUMINA_RESEARCH_EXECUTION_MODE", "sim")
    assert os.environ["RESEARCH_EXECUTION_MODE"] == "sim"
    assert freeze_is_armed() is True
    allowed, reason = assert_validation_gate_or_block("paper_simulator.try_open", order_side="BUY")
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_rebinding_allowlist_cannot_reopen() -> None:
    import lumina_core.order_gatekeeper.ungated_place_block as freeze

    original = freeze.S0_PLACE_SOURCE_ALLOWLIST
    try:
        freeze.S0_PLACE_SOURCE_ALLOWLIST = frozenset({"supervisor_tick_exec.run_tick_exec", "operations_service_orders.place_order"})
        allowed, reason = freeze.assert_validation_gate_or_block(
            "supervisor_tick_exec.run_tick_exec",
            order_side="BUY",
        )
        assert allowed is False
        assert reason == UNGATED_PLACE_BLOCK_REASON
        assert original == frozenset()
        assert S0_PLACE_SOURCE_ALLOWLIST == frozenset()
    finally:
        freeze.S0_PLACE_SOURCE_ALLOWLIST = original
