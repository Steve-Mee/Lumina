from __future__ import annotations

import pytest

from lumina_core.broker.ninjatrader.account_names import (
    account_on_sim_whitelist,
    is_local_sim_name,
)
from lumina_core.broker.ninjatrader.guards import check_account_match
from lumina_core.risk.sim_account_guard import (
    SIM_ACCOUNT_NOT_WHITELISTED,
    admit_sim_account,
)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_sim101_on_list_and_match_is_ok() -> None:
    ok, reason = check_account_match(
        trade_mode="sim",
        configured_account="Sim101",
        connected_account="Sim101",
        sim_account_whitelist=("Sim101",),
    )
    assert ok is True
    assert reason == "ok"
    assert admit_sim_account("Sim101", ("Sim101",), mode="sim") == (True, "ok")


@pytest.mark.unit
@pytest.mark.safety_gate
def test_sim202_rejected_even_though_prefix_helper_is_true() -> None:
    assert is_local_sim_name("Sim202") is True
    assert account_on_sim_whitelist("Sim202", ("Sim101",)) is False
    ok, reason = check_account_match(
        trade_mode="sim",
        configured_account="Sim101",
        connected_account="Sim202",
        sim_account_whitelist=("Sim101",),
    )
    assert ok is False
    assert reason == SIM_ACCOUNT_NOT_WHITELISTED


@pytest.mark.unit
@pytest.mark.safety_gate
def test_demo_not_on_list_is_rejected() -> None:
    ok, reason = check_account_match(
        trade_mode="sim",
        configured_account="DEMO5042070",
        connected_account="DEMO5042070",
        sim_account_whitelist=("Sim101",),
    )
    assert ok is False
    assert reason == SIM_ACCOUNT_NOT_WHITELISTED


@pytest.mark.unit
def test_demo_on_list_is_ok() -> None:
    ok, reason = check_account_match(
        trade_mode="sim",
        configured_account="DEMO5042070",
        connected_account="DEMO5042070",
        sim_account_whitelist=("DEMO5042070",),
    )
    assert ok is True
    assert reason == "ok"
