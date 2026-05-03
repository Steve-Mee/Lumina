from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from lumina_core.engine.broker_bridge import AccountInfo, PaperBroker, Position
from lumina_core.risk.equity_snapshot import EquitySnapshot, EquitySnapshotProvider
from lumina_core.risk.final_arbitration import FinalArbitration, build_current_state_from_engine
from lumina_core.risk.risk_policy import RiskPolicy
from lumina_core.risk.schemas import ArbitrationState, OrderIntent, OrderIntentMetadata


def _policy() -> RiskPolicy:
    return RiskPolicy(
        runtime_mode="real",
        daily_loss_cap=-500.0,
        max_open_risk_per_instrument=100.0,
        max_total_open_risk=300.0,
        max_exposure_per_regime=250.0,
        var_95_limit_usd=400.0,
        var_99_limit_usd=600.0,
        es_95_limit_usd=500.0,
        es_99_limit_usd=700.0,
        margin_min_confidence=0.6,
    )


@dataclass
class _CountingBroker:
    account: AccountInfo
    positions: list[Position]
    calls: int = 0

    def get_account_info(self) -> AccountInfo:
        self.calls += 1
        return self.account

    def get_positions(self) -> list[Position]:
        return list(self.positions)


@pytest.mark.unit
def test_equity_snapshot_provider_fail_closed_on_broker_error() -> None:
    class _FailingBroker:
        def get_account_info(self) -> AccountInfo:
            raise RuntimeError("broker offline")

    provider = EquitySnapshotProvider(get_broker=lambda: _FailingBroker(), ttl_seconds=30.0)
    snapshot = provider.get_snapshot()
    assert snapshot.ok is False
    assert snapshot.reason_code == "broker_account_fetch_failed"
    assert snapshot.equity_usd == 0.0
    assert snapshot.available_margin_usd == 0.0


@pytest.mark.unit
def test_equity_snapshot_provider_uses_cache_within_ttl() -> None:
    broker = _CountingBroker(
        account=AccountInfo(balance=50_000.0, equity=51_000.0, available_margin=42_000.0),
        positions=[],
    )
    provider = EquitySnapshotProvider(get_broker=lambda: broker, ttl_seconds=30.0)
    first = provider.get_snapshot()
    second = provider.get_snapshot()
    assert first.ok is True
    assert second.ok is True
    assert second.from_cache is True
    assert broker.calls == 1


@pytest.mark.integration
def test_equity_snapshot_provider_with_paper_broker_has_live_equity_margin() -> None:
    engine = SimpleNamespace(account_balance=50_000.0, account_equity=50_250.0)
    broker = PaperBroker(engine=engine)
    provider = EquitySnapshotProvider(get_broker=lambda: broker, ttl_seconds=30.0)
    snapshot = provider.get_snapshot()
    assert snapshot.ok is True
    assert snapshot.equity_usd == 50_250.0
    assert snapshot.available_margin_usd == 50_250.0


@pytest.mark.unit
def test_build_current_state_real_never_falls_back_to_50k_default() -> None:
    now = datetime.now(timezone.utc)

    class _SnapshotProvider:
        def get_snapshot(self) -> EquitySnapshot:
            return EquitySnapshot(
                equity_usd=0.0,
                available_margin_usd=0.0,
                used_margin_usd=0.0,
                as_of_utc=now,
                source="test",
                ok=False,
                reason_code="broker_unavailable",
                ttl_seconds=30.0,
            )

    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="real", drawdown_kill_percent=25.0),
        app=None,
        risk_controller=None,
        realized_pnl_today=0.0,
        account_equity=None,
        available_margin=None,
        positions_margin_used=None,
        drawdown_pct=0.0,
        live_position_qty=0,
        equity_snapshot_provider=_SnapshotProvider(),
    )

    state = build_current_state_from_engine(engine)
    assert state.runtime_mode == "real"
    assert state.equity_snapshot_ok is False
    assert state.account_equity == 0.0
    assert state.account_equity != 50_000.0


@pytest.mark.unit
def test_build_current_state_sim_keeps_default_equity_for_experiments() -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="sim", drawdown_kill_percent=25.0),
        app=None,
        risk_controller=None,
        realized_pnl_today=0.0,
        account_equity=None,
        available_margin=None,
        positions_margin_used=None,
        drawdown_pct=0.0,
        live_position_qty=0,
        equity_snapshot_provider=None,
    )
    state = build_current_state_from_engine(engine)
    assert state.runtime_mode == "sim"
    assert state.account_equity == 50_000.0
    assert state.equity_snapshot_reason == "not_required_non_real"


@pytest.mark.unit
def test_build_current_state_real_fail_closed_when_snapshot_is_stale() -> None:
    now = datetime.now(timezone.utc)

    class _StaleSnapshotProvider:
        def get_snapshot(self) -> EquitySnapshot:
            return EquitySnapshot(
                equity_usd=120_000.0,
                available_margin_usd=90_000.0,
                used_margin_usd=30_000.0,
                as_of_utc=now - timedelta(seconds=31),
                source="test",
                ok=True,
                reason_code="ok_live",
                ttl_seconds=30.0,
            )

    engine = SimpleNamespace(
        config=SimpleNamespace(trade_mode="real", drawdown_kill_percent=25.0),
        app=None,
        risk_controller=None,
        realized_pnl_today=0.0,
        account_equity=None,
        available_margin=None,
        positions_margin_used=None,
        drawdown_pct=0.0,
        live_position_qty=0,
        equity_snapshot_provider=_StaleSnapshotProvider(),
    )

    state = build_current_state_from_engine(engine)
    assert state.runtime_mode == "real"
    assert state.equity_snapshot_ok is False
    assert state.equity_snapshot_reason == "equity_snapshot_stale"
    assert state.account_equity == 0.0
    assert state.free_margin == 0.0


@pytest.mark.unit
def test_final_arbitration_rejects_real_risk_increase_without_fresh_snapshot() -> None:
    arbitration = FinalArbitration(_policy())
    intent = OrderIntent(
        instrument="MES",
        side="BUY",
        quantity=1,
        proposed_risk=10.0,
        confidence=0.8,
        source_agent="test-agent",
        metadata=OrderIntentMetadata(reason="entry_signal"),
    )
    state = ArbitrationState(
        runtime_mode="real",
        equity_snapshot_ok=False,
        equity_snapshot_reason="real_equity_snapshot_required",
        daily_pnl=100.0,
        account_equity=0.0,
        free_margin=0.0,
        used_margin=0.0,
        drawdown_pct=0.0,
        drawdown_kill_percent=25.0,
        open_risk_by_symbol={},
        total_open_risk=0.0,
        var_95_usd=0.0,
        var_99_usd=0.0,
        es_95_usd=0.0,
        es_99_usd=0.0,
        live_position_qty=0,
    )
    result = arbitration.check_order_intent(intent, state)
    assert result.status == "REJECTED"
    assert result.reason == "real_equity_snapshot_required"
