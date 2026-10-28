"""SIM floor is a measured percent of equity. REAL is not written."""
from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from lumina_core.maturity.playground.envelope import read_seal
from lumina_core.maturity.playground.portfolio_seal import (
    SimAccount,
    apply_sim_portfolio_caps,
    caps_from_equity,
    ensure_portfolio_seal,
    read_sim_account,
    read_sim_equity,
)
from lumina_core.risk.risk_limits import RiskLimits


@pytest.mark.unit
def test_caps_are_two_percent_of_equity() -> None:
    assert caps_from_equity(100_000.0) == (-2_000.0, 2_000.0)


@pytest.mark.unit
def _account(**overrides: object) -> SimAccount:
    fields: dict[str, object] = {
        "cash": 50_000.0,
        "equity": 100_000.0,
        "buying_power": 40_000.0,
        "account_name": "Sim101",
        "gateway_kind": "",
    }
    fields.update(overrides)
    return SimAccount(
        cash=fields["cash"],  # type: ignore[arg-type]
        equity=fields["equity"],  # type: ignore[arg-type]
        buying_power=fields["buying_power"],  # type: ignore[arg-type]
        account_name=str(fields["account_name"]),
        gateway_kind=str(fields["gateway_kind"]),
    )


@pytest.mark.unit
def test_missing_cash_does_not_seal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    monkeypatch.setattr(
        "lumina_core.maturity.playground.portfolio_seal.read_sim_account",
        lambda: None,
    )
    text = ensure_portfolio_seal(tmp_path)
    assert "cash" in text
    assert read_seal(tmp_path) is None


@pytest.mark.unit
def test_net_liquidation_does_not_replace_missing_cash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    monkeypatch.setattr(
        "lumina_core.maturity.playground.portfolio_seal.read_sim_account",
        lambda: _account(cash=None, equity=100_000.0),
    )
    ensure_portfolio_seal(tmp_path)
    assert read_seal(tmp_path) is None


@pytest.mark.unit
def test_cash_writes_the_fraction_and_names_net_liquidation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    monkeypatch.setattr(
        "lumina_core.maturity.playground.portfolio_seal.read_sim_account",
        lambda: _account(),
    )
    text = ensure_portfolio_seal(tmp_path)
    seal = read_seal(tmp_path)
    assert seal is not None
    assert seal["source"] == "portfolio_fraction"
    assert seal["floor_basis"] == "cash"
    assert seal["daily_loss_cap"] == -1_000.0
    assert seal["max_total_open_risk"] == 1_000.0
    assert seal["cash"] == 50_000.0
    assert seal["net_liquidation"] == 100_000.0
    assert "Dagvloer -1000" in text
    assert "Netto 100000" in text
    assert "Rekening Sim101" in text


@pytest.mark.unit
def test_memory_gateway_does_not_seal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    monkeypatch.setattr(
        "lumina_core.maturity.playground.portfolio_seal.read_sim_account",
        lambda: _account(cash=100_000.0, equity=100_000.0, buying_power=90_000.0),
    )
    text = ensure_portfolio_seal(tmp_path)
    assert "memory-gateway" in text
    assert read_seal(tmp_path) is None


@pytest.mark.unit
def test_basis_change_rewrites_even_when_the_cap_matches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config.yaml").write_text("mode: sim\n", encoding="utf-8")
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_sim_envelope_sealed.json").write_text(
        '{"sealed": true, "source": "portfolio_fraction", "daily_loss_cap": -2000.0, '
        '"max_total_open_risk": 2000.0, "equity": 100000.0}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "lumina_core.maturity.playground.portfolio_seal.read_sim_account",
        lambda: _account(cash=100_000.0, equity=100_000.0, buying_power=100_000.0),
    )
    text = ensure_portfolio_seal(tmp_path)
    seal = read_seal(tmp_path)
    assert seal is not None
    assert seal["floor_basis"] == "cash"
    assert seal["daily_loss_cap"] == -2_000.0
    assert "Reset Initial cash" in text
    stamp = seal["updated_at"]
    monkeypatch.setattr(
        "lumina_core.maturity.playground.portfolio_seal.read_sim_account",
        lambda: _account(cash=102_000.0, equity=101_000.0, buying_power=80_000.0),
    )
    drifted = ensure_portfolio_seal(tmp_path)
    again = read_seal(tmp_path)
    assert again is not None
    assert again["updated_at"] == stamp
    assert again["daily_loss_cap"] == -2_000.0
    assert "Cash 102000" in drifted


@pytest.mark.unit
def test_bound_account_mismatch_does_not_rewrite_the_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config.yaml").write_text(
        "mode: sim\nbroker:\n  ninjatrader:\n    account_name: DEMO5042070\n",
        encoding="utf-8",
    )
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_sim_envelope_sealed.json").write_text(
        '{"sealed": true, "source": "portfolio_fraction", "daily_loss_cap": -2000.0, '
        '"max_total_open_risk": 2000.0, "equity": 100000.0, "floor_basis": "cash", '
        '"cash": 100000.0, "account_name": "Sim101", "updated_at": "2026-09-29T17:27:03Z"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "lumina_core.maturity.playground.portfolio_seal.read_sim_account",
        lambda: _account(cash=100_000.0, equity=100_000.0, buying_power=100_000.0),
    )
    text = ensure_portfolio_seal(tmp_path)
    seal = read_seal(tmp_path)
    assert seal is not None
    assert seal["account_name"] == "Sim101"
    assert seal["daily_loss_cap"] == -2000.0
    assert seal["updated_at"] == "2026-09-29T17:27:03Z"
    assert "Sim101" in text
    assert "DEMO5042070" in text


def test_matching_demo_account_seals_its_own_cash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config.yaml").write_text(
        "mode: sim\nbroker:\n  ninjatrader:\n    account_name: DEMO5042070\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "lumina_core.maturity.playground.portfolio_seal.read_sim_account",
        lambda: _account(
            cash=50_000.0,
            equity=50_000.0,
            buying_power=40_000.0,
            account_name="DEMO5042070",
        ),
    )
    text = ensure_portfolio_seal(tmp_path)
    seal = read_seal(tmp_path)
    assert seal is not None
    assert seal["account_name"] == "DEMO5042070"
    assert seal["cash"] == 50_000.0
    assert seal["daily_loss_cap"] == -1_000.0
    assert "Rekening DEMO5042070" in text


def test_real_config_does_not_seal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "config.yaml").write_text("mode: real\n", encoding="utf-8")

    def _boom() -> SimAccount:
        raise AssertionError("real read")

    monkeypatch.setattr(
        "lumina_core.maturity.playground.portfolio_seal.read_sim_account",
        _boom,
    )
    ensure_portfolio_seal(tmp_path)
    assert read_seal(tmp_path) is None


@pytest.mark.unit
def test_apply_caps_is_sim_only_and_does_not_raise_open_risk() -> None:
    limits = RiskLimits(daily_loss_cap=-1000.0, max_total_open_risk=3000.0, max_open_risk_per_instrument=500.0)

    class Controller:
        def __init__(self) -> None:
            self.limits = limits
            self._base_limits = limits
            self._active_limits = limits

    controller = Controller()
    assert apply_sim_portfolio_caps(controller, mode="real", cap=-2000.0, open_risk=2000.0) is False
    assert limits.daily_loss_cap == -1000.0
    assert apply_sim_portfolio_caps(controller, mode="sim", cap=-2000.0, open_risk=2000.0) is True
    assert limits.daily_loss_cap == -2000.0
    assert limits.max_total_open_risk == 2000.0
    assert limits.max_open_risk_per_instrument == 500.0


@pytest.mark.unit
def test_equity_read_does_not_open_a_trading_stream() -> None:
    source = inspect.getsource(read_sim_account)
    assert ".connect(" not in source
    assert "read_account_snapshot_unary" in source
    assert ".connect(" not in inspect.getsource(read_sim_equity)


@pytest.mark.unit
def test_live_session_equity_does_not_call_unary(monkeypatch: pytest.MonkeyPatch) -> None:
    account = SimpleNamespace(equity=100_000.0, balance=100_000.0)

    class _Client:
        def get_account_state(self) -> tuple[object, list[object], str]:
            return account, [], "ok"

    class _Supervisor:
        def get_client(self) -> _Client:
            return _Client()

    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_link_supervisor.get_fabric_link_supervisor",
        lambda: _Supervisor(),
    )
    unary = MagicMock(side_effect=AssertionError("unary stream"))
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_client.read_account_snapshot_unary",
        unary,
    )
    assert read_sim_equity() == 100_000.0
    unary.assert_not_called()


@pytest.mark.unit
def test_session_without_cash_uses_unary_cash(monkeypatch: pytest.MonkeyPatch) -> None:
    session = SimpleNamespace(equity=50_000.0, balance=None, raw={})
    unary_account = SimpleNamespace(
        equity=50_000.0,
        balance=50_000.0,
        available_margin=50_000.0,
        raw={"account_name": "DEMO5042070", "gateway_kind": ""},
    )

    class _Client:
        def get_account_state(self) -> tuple[object, list[object], str]:
            return session, [], "ok"

    class _Supervisor:
        def get_client(self) -> _Client:
            return _Client()

    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_link_supervisor.get_fabric_link_supervisor",
        lambda: _Supervisor(),
    )
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_client.read_account_snapshot_unary",
        lambda: unary_account,
    )
    read = read_sim_account()
    assert read is not None
    assert read.cash == 50_000.0
    assert read.account_name == "DEMO5042070"


@pytest.mark.unit
def test_missing_session_uses_unary_and_does_not_invent(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Supervisor:
        def get_client(self) -> None:
            return None

    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_link_supervisor.get_fabric_link_supervisor",
        lambda: _Supervisor(),
    )
    unary = MagicMock(return_value=None)
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_client.read_account_snapshot_unary",
        unary,
    )
    assert read_sim_equity() is None
    unary.assert_called_once()


@pytest.mark.unit
def test_unary_account_read_is_not_a_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    from lumina_core.broker.ninjatrader.fabric_client import (
        FabricConfig,
        read_account_equity_unary,
        read_account_snapshot_unary,
    )

    source = inspect.getsource(read_account_snapshot_unary)
    assert ".connect(" not in source
    assert "GetAccountState" in source

    class _Channel:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    channel = _Channel()
    seen: dict[str, object] = {}

    class _Stub:
        def __init__(self, _channel: object) -> None:
            return None

        def GetAccountState(self, request: object, timeout: float, metadata: tuple) -> str:
            seen["timeout"] = timeout
            seen["metadata"] = metadata
            return "state"

    class _Info:
        equity = 100_000.0

    monkeypatch.setattr(FabricConfig, "resolve_token", lambda self: "brain-token")
    monkeypatch.setattr(
        "lumina_core.mtls_config.build_grpc_channel",
        lambda _target: channel,
    )
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_client.grpc.insecure_channel",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("real channel")),
    )
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_client.fabric_pb2_grpc.ExecutionFabricStub",
        _Stub,
    )
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_client.mapper.account_state_to_info",
        lambda _state: _Info(),
    )
    monkeypatch.setattr(
        "lumina_core.broker.ninjatrader.fabric_client.FabricGrpcClient",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("stream client")),
    )
    assert read_account_equity_unary(FabricConfig(mode_context="sim")) == 100_000.0
    assert channel.closed is True
    assert seen["metadata"] == (("x-lumina-token", "brain-token"),)
    _Info.equity = 0.0
    channel.closed = False
    assert read_account_equity_unary(FabricConfig(mode_context="sim")) is None
