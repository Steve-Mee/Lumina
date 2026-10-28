"""Attack tests: bypass routes cannot reopen ungated places (D1/D8)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.order_gatekeeper.ungated_place_block import (
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
    freeze_is_armed,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
def test_confluence_yaml_env_and_source_agent_cannot_reopen() -> None:
    assert freeze_is_armed() is True
    probes = (
        ("supervisor_tick_exec.run_tick_exec", "BUY", "confluence"),
        ("operations_service_orders.place_order", "SELL", "operator"),
        ("policy_engine.execute_order", "BUY", "policy"),
        ("reasoning_service.submit_order", "BUY", "reasoning"),
        ("trade_workers.submit_order_with_risk_check", "BUY", "workers"),
        ("paper_simulator.try_open", "BUY", "paper"),
        ("paper_trade_executor.submit_paper_order", "BUY", "paper_exec"),
    )
    for source, side, _label in probes:
        allowed, reason = assert_validation_gate_or_block(
            source,
            order_side=side,
            source_agent="research_bridge",
            reduce_only=False,
        )
        assert allowed is False, source
        assert reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_reduce_only_without_opposing_position_is_blocked() -> None:
    allowed, reason = assert_validation_gate_or_block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="SELL",
        live_position_qty=0,
    )
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON
    allowed_add, reason_add = assert_validation_gate_or_block(
        "policy_engine.execute_order",
        reduce_only=True,
        order_side="SELL",
        live_position_qty=-1,
    )
    assert allowed_add is False
    assert reason_add == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_supervisor_module_does_not_import_research_bridge() -> None:
    text = (ROOT / "lumina_core" / "engine" / "supervisor_tick_exec.py").read_text(encoding="utf-8")
    assert "research_bridge" not in text
    assert "SignalIntent" not in text
    assert "schemas_research_execution" not in text


@pytest.mark.unit
def test_freeze_module_never_loads_config_yaml() -> None:
    text = (ROOT / "lumina_core" / "order_gatekeeper" / "ungated_place_block.py").read_text(encoding="utf-8")
    assert "config.yaml" not in text
    assert "yaml.safe_load" not in text
    assert "os.environ" not in text
    assert "os.getenv" not in text
