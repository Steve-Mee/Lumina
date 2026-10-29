from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.order_gatekeeper.admission_s1_steps import (
    make_live_release_step,
    make_sim_account_whitelist_step,
)
from lumina_core.risk.admission_chain import (
    ADMISSION_STEP_LIVE_RELEASE,
    ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,
    CANONICAL_ADMISSION_STEPS,
    UNBYPASSABLE_ADMISSION_STEPS,
    AdmissionChain,
    AdmissionContext,
    default_chain_for_mode,
)
from lumina_core.risk.live_release import LIVE_ACCOUNT_PATH_CLOSED_S1, SECRET_ENV, admit_live_orders
from lumina_core.risk.sim_account_guard import SIM_ACCOUNT_NOT_WHITELISTED, SIM_WHITELIST_EMPTY
from tests.risk.s1_hmac import signed_live_release


def _ctx(*, mode: str, account: str = "Sim101", whitelist: tuple[str, ...] | None = ("Sim101",)) -> AdmissionContext:
    engine = SimpleNamespace(
        nt_connected_account=account,
        config=SimpleNamespace(ninjatrader_sim_account_whitelist=whitelist or ()),
    )
    metadata: dict[str, object] = {"connected_account": account}
    if whitelist is not None:
        metadata["sim_account_whitelist"] = whitelist
    return AdmissionContext(
        engine=engine,
        mode=mode,
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
        metadata=metadata,
        step_handlers={ADMISSION_STEP_SIM_ACCOUNT_WHITELIST: make_sim_account_whitelist_step(SimpleNamespace(engine=engine))},
    )


@pytest.mark.unit
def test_canonical_chain_includes_unbypassable_s1_steps() -> None:
    assert ADMISSION_STEP_SIM_ACCOUNT_WHITELIST in CANONICAL_ADMISSION_STEPS
    assert ADMISSION_STEP_LIVE_RELEASE in CANONICAL_ADMISSION_STEPS
    sync_idx = CANONICAL_ADMISSION_STEPS.index("session_equity_sync")
    wl_idx = CANONICAL_ADMISSION_STEPS.index(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST)
    lr_idx = CANONICAL_ADMISSION_STEPS.index(ADMISSION_STEP_LIVE_RELEASE)
    risk_idx = CANONICAL_ADMISSION_STEPS.index("risk_policy")
    assert sync_idx < wl_idx < lr_idx < risk_idx
    assert ADMISSION_STEP_SIM_ACCOUNT_WHITELIST in UNBYPASSABLE_ADMISSION_STEPS
    assert ADMISSION_STEP_LIVE_RELEASE in UNBYPASSABLE_ADMISSION_STEPS
    assert tuple(default_chain_for_mode("sim").steps) == CANONICAL_ADMISSION_STEPS


@pytest.mark.unit
@pytest.mark.safety_gate
@pytest.mark.parametrize("mode", ["sim", "sim_real_guard", "real"])
def test_missing_whitelist_handler_fails_closed(mode: str) -> None:
    chain = AdmissionChain(steps=CANONICAL_ADMISSION_STEPS)
    ctx = AdmissionContext(
        engine=SimpleNamespace(),
        mode=mode,
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        step_handlers={},
    )
    allowed, reason, trace = chain.run(ctx)
    assert allowed is False
    assert "admission_step_handler_missing" in reason
    missing = [item for item in trace.results if not item.ok]
    assert missing
    assert "handler_missing" in missing[0].reason


@pytest.mark.unit
@pytest.mark.safety_gate
def test_live_account_is_rejected_by_whitelist_step() -> None:
    chain = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,))
    ctx = _ctx(mode="sim", account="LiveAcct", whitelist=("Sim101",))
    allowed, reason, _trace = chain.run(ctx)
    assert allowed is False
    assert reason == SIM_ACCOUNT_NOT_WHITELISTED


@pytest.mark.unit
def test_empty_whitelist_denies_in_admission() -> None:
    chain = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,))
    ctx = _ctx(mode="sim", account="Sim101", whitelist=())
    allowed, reason, _trace = chain.run(ctx)
    assert allowed is False
    assert reason == SIM_WHITELIST_EMPTY


@pytest.mark.unit
@pytest.mark.safety_gate
def test_live_release_step_always_denies_real(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV, "s1-live-release-secret-key")
    record = signed_live_release(nonce="admit-step-nonce-01")
    engine = SimpleNamespace(config=SimpleNamespace(live_release_payload=record))
    ctx = AdmissionContext(
        engine=engine,
        mode="real",
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
        metadata={"live_release": record},
        step_handlers={ADMISSION_STEP_LIVE_RELEASE: make_live_release_step(SimpleNamespace(engine=engine))},
    )
    chain = AdmissionChain(steps=(ADMISSION_STEP_LIVE_RELEASE,))
    allowed, reason, _trace = chain.run(ctx)
    assert allowed is False
    assert reason == LIVE_ACCOUNT_PATH_CLOSED_S1
    assert admit_live_orders(signed_live_release(nonce="admit-step-nonce-02")) == (False, LIVE_ACCOUNT_PATH_CLOSED_S1)


@pytest.mark.unit
def test_bypass_of_whitelist_step_is_forbidden_in_sim() -> None:
    chain = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,))
    ctx = _ctx(mode="sim")
    ctx.experimental_bypass_step_ids = frozenset({ADMISSION_STEP_SIM_ACCOUNT_WHITELIST})
    allowed, reason, trace = chain.run(ctx)
    assert allowed is False
    assert "experimental_bypass_forbidden" in reason
    assert trace.results[0].bypassed is False
