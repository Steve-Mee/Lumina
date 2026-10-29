from __future__ import annotations

import hmac

import pytest

from lumina_core.order_gatekeeper.ungated_place_block import (
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
)
from lumina_core.risk.live_release import PURPOSE_WHITELIST_WIDEN, SECRET_ENV, verify_live_release
from lumina_core.risk.sim_account_guard import (
    LOCK,
    SIM_ACCOUNT_NOT_WHITELISTED,
    SIM_WHITELIST_LIVE_NAME_FORBIDDEN,
    SIM_WHITELIST_TAMPERED,
    SIM_WHITELIST_WIDEN_REFUSED,
    SIM_WHITELIST_WIDENED,
    SimWhitelistLock,
    admit_sim_account,
    apply_signed_whitelist_widen,
)
from tests.risk.s1_hmac import TEST_SECRET, signed_live_release


@pytest.mark.unit
@pytest.mark.safety_gate
def test_runtime_cannot_widen_frozen_whitelist(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = SimWhitelistLock()
    monkeypatch.setattr("lumina_core.risk.sim_account_guard.LOCK", lock)
    first = lock.freeze(("Sim101",))
    assert "Sim101" in first
    effective, status = lock.effective(("Sim101", "Sim202"))
    assert status == "ok"
    assert "Sim202" not in {item.casefold() for item in effective}
    ok, reason = admit_sim_account("Sim202", ("Sim101", "Sim202"), mode="sim")
    assert ok is False
    assert reason == SIM_ACCOUNT_NOT_WHITELISTED


@pytest.mark.unit
def test_tampered_seal_denies() -> None:
    lock = SimWhitelistLock()
    lock.freeze(("Sim101",))
    lock._frozen = frozenset({"Sim101", "Sim202"})  # noqa: SLF001
    assert lock.is_tampered() is True
    effective, status = lock.effective(("Sim101", "Sim202"))
    assert status == SIM_WHITELIST_TAMPERED
    assert effective == frozenset()


@pytest.mark.unit
@pytest.mark.safety_gate
def test_signed_widen_admits_extra_paper_name(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = SimWhitelistLock()
    monkeypatch.setattr("lumina_core.risk.sim_account_guard.LOCK", lock)
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    lock.freeze(("Sim101",))
    record = signed_live_release(purpose=PURPOSE_WHITELIST_WIDEN, nonce="widen-nonce-16xxxx")
    verified, verify_reason = verify_live_release(record, expected_purpose=PURPOSE_WHITELIST_WIDEN)
    assert verified is True
    ok, reason = apply_signed_whitelist_widen(("Sim202",), verified=True, verify_reason=verify_reason)
    assert ok is True
    assert reason == SIM_WHITELIST_WIDENED
    assert admit_sim_account("Sim202", ("Sim101",), mode="sim") == (True, "ok")


@pytest.mark.unit
def test_unsigned_widen_is_refused() -> None:
    ok, reason = apply_signed_whitelist_widen(("Sim202",), verified=False, verify_reason="nope")
    assert ok is False
    assert reason == "nope"
    ok, reason = apply_signed_whitelist_widen(("LiveAcct",), verified=True, verify_reason="ok")
    assert ok is False
    assert reason == SIM_WHITELIST_LIVE_NAME_FORBIDDEN
    ok, reason = apply_signed_whitelist_widen((), verified=True, verify_reason="ok")
    assert ok is False
    assert reason == SIM_WHITELIST_WIDEN_REFUSED


@pytest.mark.unit
def test_seal_uses_hmac_compare() -> None:
    lock = SimWhitelistLock()
    lock.freeze(("Sim101",))
    assert hmac.compare_digest(lock._seal, lock._seal) is True  # noqa: SLF001


@pytest.mark.unit
@pytest.mark.safety_gate
def test_s0_freeze_stays_on_during_s1() -> None:
    allowed, reason = assert_validation_gate_or_block(
        "supervisor_tick_exec.run_tick_exec",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
        source_agent="research_bridge",
    )
    assert allowed is False
    assert reason == UNGATED_PLACE_BLOCK_REASON
    assert LOCK is not None
