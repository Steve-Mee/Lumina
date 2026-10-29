from __future__ import annotations

import pytest

from lumina_core.broker.ninjatrader.account_names import account_on_sim_whitelist, canonicalize_account_name
from lumina_core.risk.sim_account_guard import admit_sim_account, canonicalize_whitelist


@pytest.mark.unit
def test_whitelist_matches_casefold_and_stores_canonical_trim() -> None:
    assert canonicalize_account_name(" Sim101 ") == "Sim101"
    names = canonicalize_whitelist([" Sim101 ", "sim101", "Sim202"])
    assert names == ("Sim101", "Sim202")
    assert account_on_sim_whitelist("sim101", names) is True
    assert account_on_sim_whitelist("SIM101", ("Sim101",)) is True
    ok, reason = admit_sim_account("sim101", ("Sim101",), mode="sim")
    assert ok is True
    assert reason == "ok"
