"""Fail-closed residuals for S1 whitelist + LIVE_RELEASE (ADR-0061).

These paths were missing from the Coverage Report serial run. They do not
open live orders or change Risk Core behaviour.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.broker.ninjatrader.account_names import (
    account_on_sim_whitelist,
    is_local_sim_name,
    paper_orders_allowed,
)
from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState
from lumina_core.broker.ninjatrader.guards import (
    check_account_match,
    check_disconnect_policy,
    paper_account_allowed,
    s1_guard_kwargs,
)
from lumina_core.broker.ninjatrader.promotion_gate import (
    NtBridgeAction,
    action_allowed,
    normalize_trade_mode,
)
from lumina_core.order_gatekeeper.admission_s1_steps import (
    attach_s1_admission_metadata,
    make_live_release_step,
    make_sim_account_whitelist_step,
)
from lumina_core.risk.admission_chain import (
    ADMISSION_STEP_LIVE_RELEASE,
    ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,
    AdmissionChain,
    AdmissionContext,
)
from lumina_core.risk.live_release import (
    LIVE_ACCOUNT_PATH_CLOSED_S1,
    LIVE_RELEASE_DISABLED,
    LIVE_RELEASE_REQUIRED,
    SECRET_ENV,
)
from lumina_core.risk.sim_account_guard import (
    ACCOUNT_UNKNOWN,
    SIM_WHITELIST_EMPTY,
    canonicalize_whitelist,
    connected_account_from_engine,
    whitelist_from_engine,
)
from tests.risk.s1_hmac import TEST_SECRET, signed_live_release


def _admission(
    *,
    mode: str,
    engine: object,
    metadata: dict[str, object] | None = None,
    step: str = ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,
) -> AdmissionContext:
    handlers = {
        ADMISSION_STEP_SIM_ACCOUNT_WHITELIST: make_sim_account_whitelist_step(SimpleNamespace(engine=engine)),
        ADMISSION_STEP_LIVE_RELEASE: make_live_release_step(SimpleNamespace(engine=engine)),
    }
    return AdmissionContext(
        engine=engine,
        mode=mode,
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        metadata=dict(metadata or {}),
        step_handlers={step: handlers[step]},
    )


@pytest.mark.unit
@pytest.mark.safety_gate
def test_canonicalize_whitelist_skips_blanks_and_rejects_scalars() -> None:
    assert canonicalize_whitelist(["", "  ", None, "Sim101", "sim101"]) == ("Sim101",)
    assert canonicalize_whitelist("Sim101") == ()
    assert canonicalize_whitelist(b"Sim101") == ()
    assert canonicalize_whitelist(None) == ()
    assert account_on_sim_whitelist("", ("Sim101",)) is False
    assert account_on_sim_whitelist("Sim101", ("", None, "Sim101")) is True
    assert is_local_sim_name("") is False
    assert paper_orders_allowed("DEMO5042070", "sim") is True
    assert paper_orders_allowed("DEMO5042070", "real") is False
    assert paper_account_allowed("Sim101", "sim") is True


@pytest.mark.unit
@pytest.mark.safety_gate
def test_engine_account_and_whitelist_fail_closed_fallbacks() -> None:
    assert connected_account_from_engine(None) == ""
    assert connected_account_from_engine(SimpleNamespace()) == ""
    named = SimpleNamespace(config=SimpleNamespace(ninjatrader_account_name="Sim101"))
    assert connected_account_from_engine(named) == "Sim101"
    empty_config = SimpleNamespace(config=SimpleNamespace(ninjatrader_account_name="", broker={}))
    assert connected_account_from_engine(empty_config) == ""
    assert whitelist_from_engine(None) == ()
    assert whitelist_from_engine(SimpleNamespace()) == ()
    assert whitelist_from_engine(SimpleNamespace(config=SimpleNamespace())) == ()
    mapping_whitelist = SimpleNamespace(config=SimpleNamespace(ninjatrader_sim_account_whitelist={"Sim101": True}))
    assert whitelist_from_engine(mapping_whitelist) == ()


@pytest.mark.unit
@pytest.mark.safety_gate
def test_admission_steps_read_engine_when_metadata_omits_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    engine = SimpleNamespace(
        nt_connected_account="Sim101",
        config=SimpleNamespace(
            ninjatrader_sim_account_whitelist=("Sim101",),
            live_release_payload={"enabled": False},
        ),
    )
    sim_ctx = _admission(mode="sim", engine=engine, metadata={"agent_id": "agent-x"})
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,)).run(sim_ctx)
    assert allowed is True
    assert reason == "ok"

    live_ctx = _admission(
        mode="real",
        engine=engine,
        metadata={},
        step=ADMISSION_STEP_LIVE_RELEASE,
    )
    live_ok, live_reason, _live_trace = AdmissionChain(steps=(ADMISSION_STEP_LIVE_RELEASE,)).run(live_ctx)
    assert live_ok is False
    assert live_reason == LIVE_RELEASE_DISABLED

    stamped: dict[str, object] = {}
    attach_s1_admission_metadata(engine, stamped)
    assert stamped["connected_account"] == "Sim101"
    assert stamped["sim_account_whitelist"] == ("Sim101",)
    assert stamped["live_release"] == {"enabled": False}


@pytest.mark.unit
@pytest.mark.safety_gate
def test_unknown_mode_and_unknown_action_are_denied() -> None:
    assert normalize_trade_mode("backtest") == "paper"
    assert action_allowed("sim", "not-an-nt-action") is False  # type: ignore[arg-type]
    engine = SimpleNamespace(config=SimpleNamespace(ninjatrader_sim_account_whitelist=("Sim101",)))
    ctx = _admission(mode="backtest", engine=engine, metadata={"connected_account": "Sim101"})
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,)).run(ctx)
    assert allowed is False
    assert reason == "nt_bridge_not_allowed_in_mode:backtest"


@pytest.mark.unit
@pytest.mark.safety_gate
def test_account_match_unknown_real_unconfigured_and_hmac_still_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unknown_ok, unknown_reason = check_account_match(
        trade_mode="sim",
        configured_account="Sim101",
        connected_account="",
        sim_account_whitelist=("Sim101",),
    )
    assert unknown_ok is False
    assert unknown_reason == ACCOUNT_UNKNOWN

    unconfigured_ok, unconfigured_reason = check_account_match(
        trade_mode="real",
        configured_account="",
        connected_account="LiveAcct",
    )
    assert unconfigured_ok is False
    assert unconfigured_reason == "real_account_not_configured"

    missing_ok, missing_reason = check_account_match(
        trade_mode="real",
        configured_account="LiveAcct",
        connected_account="LiveAcct",
        live_release=None,
    )
    assert missing_ok is False
    assert missing_reason == LIVE_RELEASE_REQUIRED

    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    record = signed_live_release(nonce="n-guard-closed-16xxxx")
    closed_ok, closed_reason = check_account_match(
        trade_mode="real",
        configured_account="LiveAcct",
        connected_account="LiveAcct",
        live_release=record,
    )
    assert closed_ok is False
    assert closed_reason == LIVE_ACCOUNT_PATH_CLOSED_S1

    disabled_ok, disabled_reason = check_account_match(
        trade_mode="real",
        configured_account="LiveAcct",
        connected_account="LiveAcct",
        live_release={"enabled": False},
    )
    assert disabled_ok is False
    assert disabled_reason == LIVE_RELEASE_DISABLED


@pytest.mark.unit
@pytest.mark.safety_gate
def test_sim_real_guard_mismatch_and_paper_disconnect(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_SIM_REAL_GUARD", "true")
    ok, reason = check_account_match(
        trade_mode="sim_real_guard",
        configured_account="Sim101",
        connected_account="Sim202",
        sim_account_whitelist=("Sim101", "Sim202"),
    )
    assert ok is False
    assert "mismatch" in reason

    disconnected = NinjaTraderConnectionState(state="disconnected", account_name="Sim101")
    disc_ok, disc_reason = check_disconnect_policy(
        trade_mode="paper",
        connection=disconnected,
        action=NtBridgeAction.SUBMIT_ORDER,
    )
    assert disc_ok is False
    assert disc_reason == "ninjatrader_disconnected"

    paper_ok, paper_reason = check_account_match(
        trade_mode="paper",
        configured_account="Sim101",
        connected_account="Sim101",
        sim_account_whitelist=("Sim101",),
    )
    assert paper_ok is False
    assert paper_reason == "nt_bridge_not_allowed_in_mode:paper"


@pytest.mark.unit
@pytest.mark.safety_gate
def test_empty_chain_and_handler_exception_fail_closed() -> None:
    ctx = AdmissionContext(
        engine=SimpleNamespace(),
        mode="sim",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
    )
    empty_ok, empty_reason, empty_trace = AdmissionChain(steps=()).run(ctx)
    assert empty_ok is False
    assert empty_reason == "admission_chain_empty"
    assert empty_trace.last_step_id == "admission_chain_uninitialized"
    assert empty_trace.approved is False

    def _boom(_ctx: AdmissionContext) -> tuple[bool, str]:
        raise RuntimeError("handler exploded")

    boom_ctx = AdmissionContext(
        engine=SimpleNamespace(),
        mode="sim",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        step_handlers={ADMISSION_STEP_SIM_ACCOUNT_WHITELIST: _boom},
    )
    boom_ok, boom_reason, boom_trace = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,)).run(boom_ctx)
    assert boom_ok is False
    assert boom_reason == "admission_step_exception:sim_account_whitelist:RuntimeError"
    assert boom_trace.results[0].ok is False


@pytest.mark.unit
def test_s1_guard_kwargs_snapshot_from_engine() -> None:
    engine = SimpleNamespace(
        config=SimpleNamespace(
            ninjatrader_sim_account_whitelist=("Sim101",),
            live_release_payload={"enabled": False, "mac": ""},
        )
    )
    snapshot = s1_guard_kwargs(engine)
    assert snapshot["sim_account_whitelist"] == ("Sim101",)
    assert snapshot["live_release"] == {"enabled": False, "mac": ""}
    empty_snapshot = s1_guard_kwargs(None)
    assert empty_snapshot["sim_account_whitelist"] == ()
    assert empty_snapshot["live_release"] is None


@pytest.mark.unit
def test_empty_whitelist_still_denies_after_engine_fallback() -> None:
    engine = SimpleNamespace(
        nt_connected_account="Sim101",
        config=SimpleNamespace(ninjatrader_sim_account_whitelist=()),
    )
    ctx = _admission(mode="sim", engine=engine, metadata={"agent_id": "agent-z"})
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,)).run(ctx)
    assert allowed is False
    assert reason == SIM_WHITELIST_EMPTY
    assert ctx.metadata["deny_reason_code"] == SIM_WHITELIST_EMPTY
