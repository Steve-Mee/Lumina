"""Research Risk Core: reject/scale oversized or risky proposals regardless of agent_id."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lumina_research.risk_core import DecisionKind, OrderProposal, RiskConfig, RiskCore, load_default_config, propose_order
from lumina_research.risk_core.config import RiskConfigError
from lumina_research.risk_core.seal import RiskCoreSealError


def _cfg() -> RiskConfig:
    return load_default_config()


def _core(equity: float = 100_000.0) -> RiskCore:
    core = RiskCore(_cfg(), equity=equity)
    core.heartbeat(datetime.now(timezone.utc))
    return core


def _proposal(*, agent_id: str = "alpha", quantity: float = 1.0, notional: float = 5_000.0, cluster: str = "eq") -> OrderProposal:
    return OrderProposal(
        agent_id=agent_id,
        instrument="MES",
        side="buy",
        quantity=quantity,
        price=5000.0,
        notional=notional,
        cluster_id=cluster,
        submitted_at_utc=datetime.now(timezone.utc),
    )


@pytest.mark.unit
def test_config_is_frozen_and_has_no_setters() -> None:
    cfg = _cfg()
    with pytest.raises(Exception):
        cfg.max_position_pct = 0.9  # type: ignore[misc]
    with pytest.raises(TypeError, match="subclassed"):

        class Soft(RiskConfig):  # type: ignore[misc]
            pass


@pytest.mark.unit
def test_oversized_position_scaled_or_rejected_for_any_agent() -> None:
    core = _core()
    for agent in ("alpha", "omega", "evolution"):
        decision = core.propose_order(_proposal(agent_id=agent, quantity=100.0, notional=50_000.0))
        assert decision.kind in {DecisionKind.SCALED, DecisionKind.REJECTED}
        assert decision.agent_id == agent
        if decision.kind is DecisionKind.SCALED:
            assert decision.notional <= 0.10 * 100_000.0 + 1e-9


@pytest.mark.unit
def test_leverage_and_cluster_caps() -> None:
    core = _core()
    core.set_exposure(gross_notional=390_000.0, cluster_id="eq", cluster_notional=14_000.0)
    lev = core.propose_order(_proposal(notional=20_000.0, quantity=4.0))
    assert lev.kind in {DecisionKind.SCALED, DecisionKind.REJECTED}
    cluster = core.propose_order(_proposal(notional=10_000.0, quantity=2.0, cluster="eq"))
    assert cluster.kind in {DecisionKind.SCALED, DecisionKind.REJECTED}


@pytest.mark.unit
def test_kill_switch_heartbeat_and_drawdown() -> None:
    core = _core()
    late = OrderProposal(
        agent_id="alpha",
        instrument="MES",
        side="buy",
        quantity=1.0,
        price=5000.0,
        notional=1_000.0,
        cluster_id="eq",
        submitted_at_utc=datetime.now(timezone.utc) + timedelta(seconds=120),
    )
    lost = core.propose_order(late)
    assert lost.kind is DecisionKind.REJECTED
    assert "heartbeat" in lost.reason

    core2 = _core()
    core2.record_pnl(-15_000.0)
    dd = core2.propose_order(_proposal(notional=1_000.0))
    assert dd.kind is DecisionKind.REJECTED
    assert "kill_switch" in dd.reason
    with pytest.raises(AttributeError):
        core2._book.kill = False  # type: ignore[misc]


@pytest.mark.unit
def test_daily_loss_kill() -> None:
    core = _core()
    core.record_pnl(-3_000.0)
    decision = core.propose_order(_proposal(notional=1_000.0))
    assert decision.kind is DecisionKind.REJECTED
    assert "daily_loss" in decision.reason or "kill_switch" in decision.reason


@pytest.mark.unit
def test_module_seal_blocks_monkeypatch() -> None:
    import lumina_research.risk_core as pkg

    with pytest.raises(RiskCoreSealError):
        pkg.propose_order = lambda proposal: None  # type: ignore[assignment]
    with pytest.raises(TypeError, match="subclassed"):

        class Rogue(RiskCore):  # type: ignore[misc]
            def propose_order(self, proposal: OrderProposal) -> object:  # type: ignore[override]
                return None


@pytest.mark.unit
def test_default_propose_without_core_fail_closes() -> None:
    decision = propose_order(_proposal())
    assert decision.kind is DecisionKind.REJECTED


@pytest.mark.unit
def test_limits_file_rejects_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "limits.toml"
    path.write_text("max_position_pct = 0.1\n", encoding="utf-8")
    with pytest.raises(RiskConfigError):
        load_default_config(path)
