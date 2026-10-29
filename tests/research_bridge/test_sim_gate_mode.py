"""S3 requires sim_real_guard + env. trade_mode sim or real refuses."""

from __future__ import annotations

import pytest

from lumina_core.research_bridge.sim_gate import RESEARCH_SIM_GATED, bind_sim_gate, evaluate
from tests.research_bridge.s3_helpers import passing_context


@pytest.fixture(autouse=True)
def _unbind() -> None:
    bind_sim_gate(None)
    yield
    bind_sim_gate(None)


@pytest.mark.unit
def test_trade_mode_sim_refuses() -> None:
    ok, reason = evaluate(passing_context(trade_mode="sim"))
    assert ok is False
    assert reason == RESEARCH_SIM_GATED


@pytest.mark.unit
def test_trade_mode_real_refuses() -> None:
    ok, reason = evaluate(passing_context(trade_mode="real"))
    assert ok is False
    assert reason == RESEARCH_SIM_GATED


@pytest.mark.unit
def test_sim_real_guard_without_env_refuses() -> None:
    ok, reason = evaluate(passing_context(env=False))
    assert ok is False
    assert reason == "sim_real_guard_disabled"


@pytest.mark.unit
def test_sim_real_guard_with_env_ok() -> None:
    ok, reason = evaluate(passing_context(trade_mode="sim_real_guard", env=True))
    assert ok is True
    assert reason == "research_sim_gate_ok"
