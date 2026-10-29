from __future__ import annotations

import pytest

from lumina_core.broker.ninjatrader.account_names import account_on_sim_whitelist
from lumina_core.broker.ninjatrader.guards import check_account_match
from lumina_core.risk.sim_account_guard import SIM_WHITELIST_EMPTY, admit_sim_account


@pytest.mark.unit
@pytest.mark.safety_gate
def test_empty_whitelist_denies_sim101() -> None:
    assert account_on_sim_whitelist("Sim101", []) is False
    ok, reason = admit_sim_account("Sim101", (), mode="sim")
    assert ok is False
    assert reason == SIM_WHITELIST_EMPTY
    allowed, match_reason = check_account_match(
        trade_mode="sim",
        configured_account="Sim101",
        connected_account="Sim101",
        sim_account_whitelist=(),
    )
    assert allowed is False
    assert match_reason == SIM_WHITELIST_EMPTY


@pytest.mark.unit
@pytest.mark.safety_gate
def test_missing_whitelist_denies() -> None:
    assert account_on_sim_whitelist("Sim101", None) is False
    ok, reason = admit_sim_account("Sim101", None, mode="sim")
    assert ok is False
    assert reason == SIM_WHITELIST_EMPTY


@pytest.mark.unit
def test_string_whitelist_is_not_a_list_and_denies() -> None:
    assert account_on_sim_whitelist("Sim101", "Sim101") is False  # type: ignore[arg-type]
    ok, reason = admit_sim_account("Sim101", "Sim101", mode="sim")  # type: ignore[arg-type]
    assert ok is False
    assert reason == SIM_WHITELIST_EMPTY
