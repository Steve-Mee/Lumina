"""S1 attack tests: whitelist bypass, HMAC, CANCEL-cannot-place, modify whitelist."""

from __future__ import annotations

import hmac
import logging
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.agent_orchestration.schemas import ConstitutionViolation
from lumina_core.broker.ninjatrader.account_names import account_on_sim_whitelist
from lumina_core.broker.ninjatrader.bridge_service import NinjaTraderBridgeService
from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState
from lumina_core.broker.ninjatrader.guards import assert_nt_bridge_capability
from lumina_core.broker.ninjatrader.promotion_gate import (
    NtBridgeAction,
    action_enforces_sim_whitelist,
    action_for_command_frame,
)
from lumina_core.order_gatekeeper.admission_s1_steps import make_live_release_step
from lumina_core.risk.admission_chain import (
    ADMISSION_STEP_LIVE_RELEASE,
    AdmissionChain,
    AdmissionContext,
)
from lumina_core.risk.live_release import (
    LIVE_ACCOUNT_PATH_CLOSED_S1,
    LIVE_RELEASE_DISABLED,
    LIVE_RELEASE_HMAC_OK,
    LIVE_RELEASE_MAC_MISMATCH,
    LIVE_RELEASE_PURPOSE_INVALID,
    LIVE_RELEASE_TIMESTAMP_NOT_UTC,
    SECRET_ENV,
    canonical_live_release_payload,
    compute_live_release_mac,
    log_live_reject,
    reset_live_release_nonces_for_tests,
    verify_live_release,
)
from lumina_core.risk.s1_events import s1_reject_event_data
from lumina_core.risk.sim_account_guard import (
    SIM_ACCOUNT_NOT_WHITELISTED,
    SIM_WHITELIST_EMPTY,
    SimWhitelistLock,
    admit_sim_account,
    apply_signed_whitelist_widen,
    connected_account_from_engine,
    log_sim_reject,
)
from tests.risk.s1_hmac import TEST_SECRET, signed_live_release

ROOT = Path(__file__).resolve().parents[2]


def _connected(account: str = "Sim101") -> NinjaTraderConnectionState:
    return NinjaTraderConnectionState(state="connected", account_name=account)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_unicode_homoglyph_zero_width_and_prefix_cannot_bypass_whitelist() -> None:
    names = ("Sim101",)
    assert account_on_sim_whitelist("sim101", names) is True
    assert account_on_sim_whitelist(" Sim101 ", names) is True
    assert account_on_sim_whitelist("Sim101", ("Sim",)) is False
    assert account_on_sim_whitelist("Sim1010", names) is False
    assert account_on_sim_whitelist("Sim101\u200b", names) is False
    assert account_on_sim_whitelist("\u0405im101", names) is False
    assert admit_sim_account("Sim101\u200b", names, mode="sim")[0] is False
    assert admit_sim_account("Sim999", names, mode="sim") == (False, SIM_ACCOUNT_NOT_WHITELISTED)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_hmac_compare_digest_is_the_mac_and_seal_primitive() -> None:
    live = (ROOT / "lumina_core/risk/live_release.py").read_text(encoding="utf-8")
    guard = (ROOT / "lumina_core/risk/sim_account_guard.py").read_text(encoding="utf-8")
    assert "hmac.compare_digest(expected, mac)" in live
    assert "if expected == mac" not in live
    assert "hmac.compare_digest(self._seal, _seal_for(" in guard
    assert live.count("hmac.compare_digest") >= 1
    assert guard.count("hmac.compare_digest") >= 3


@pytest.mark.unit
@pytest.mark.safety_gate
def test_modify_order_is_whitelisted_cancel_is_not() -> None:
    assert action_for_command_frame("modify_order") is NtBridgeAction.MODIFY_ORDER
    assert action_for_command_frame("submit_order") is NtBridgeAction.SUBMIT_ORDER
    assert action_for_command_frame("flatten") is NtBridgeAction.CANCEL
    assert action_for_command_frame("cancel_order") is NtBridgeAction.CANCEL
    assert action_for_command_frame("place_adjacent_unknown") is NtBridgeAction.SUBMIT_ORDER
    assert action_enforces_sim_whitelist(NtBridgeAction.MODIFY_ORDER) is True
    assert action_enforces_sim_whitelist(NtBridgeAction.SUBMIT_ORDER) is True
    assert action_enforces_sim_whitelist(NtBridgeAction.CANCEL) is False

    ok_mod, why_ok = assert_nt_bridge_capability(
        action=NtBridgeAction.MODIFY_ORDER,
        trade_mode="sim",
        connection=_connected("Sim101"),
        configured_account="Sim101",
        ninjatrader_enabled=True,
        sim_account_whitelist=("Sim101",),
    )
    assert ok_mod is True
    assert why_ok == "ok"

    ok_cancel, why_cancel = assert_nt_bridge_capability(
        action=NtBridgeAction.CANCEL,
        trade_mode="sim",
        connection=_connected("Sim101"),
        configured_account="Sim101",
        ninjatrader_enabled=True,
        sim_account_whitelist=(),
    )
    assert ok_cancel is True
    assert why_cancel == "ok"


@pytest.mark.unit
@pytest.mark.safety_gate
def test_modify_empty_whitelist_denies() -> None:
    deny_mod, why_mod = assert_nt_bridge_capability(
        action=NtBridgeAction.MODIFY_ORDER,
        trade_mode="sim",
        connection=_connected("Sim101"),
        configured_account="Sim101",
        ninjatrader_enabled=True,
        sim_account_whitelist=(),
    )
    assert deny_mod is False
    assert why_mod == SIM_WHITELIST_EMPTY


@pytest.mark.unit
@pytest.mark.safety_gate
def test_send_command_sync_modify_is_whitelisted_cancel_is_not() -> None:
    bridge = NinjaTraderBridgeService(
        configured_account="Sim101",
        trade_mode="sim",
        ninjatrader_enabled=True,
    )
    bridge._connection = NinjaTraderConnectionState(state="connected", account_name="Sim101")  # noqa: SLF001
    bridge.set_s1_guards(sim_account_whitelist=())
    modify = bridge.send_command_sync({"type": "modify_order", "quantity": 99, "client_order_id": "m1"})
    assert modify["type"] == "error"
    assert "sim_whitelist_empty" in str(modify.get("message", ""))
    submit = bridge.send_command_sync({"type": "submit_order", "quantity": 1, "symbol": "MES", "side": "BUY"})
    assert submit["type"] == "error"
    assert "sim_whitelist_empty" in str(submit.get("message", ""))
    cancel = bridge.send_command_sync({"type": "flatten"})
    assert "sim_whitelist" not in str(cancel.get("message", ""))


@pytest.mark.unit
@pytest.mark.safety_gate
def test_cancel_frame_cannot_become_submit_or_size_increase() -> None:
    assert action_for_command_frame("cancel_order") is not NtBridgeAction.SUBMIT_ORDER
    assert action_for_command_frame("cancel_order") is not NtBridgeAction.MODIFY_ORDER
    assert action_for_command_frame("flatten") is NtBridgeAction.CANCEL
    sync = (ROOT / "lumina_core/broker/ninjatrader/bridge_command_sync.py").read_text(encoding="utf-8")
    assert "action_for_command_frame(frame_type)" in sync
    assert 'if frame_type == "submit_order"\n                else NtBridgeAction.CANCEL' not in sync
    cs = (ROOT / "integrations/ninjatrader8/LuminaNt8AddOn/NtAccountOrderGateway.cs").read_text(encoding="utf-8")
    modify_idx = cs.index("public IReadOnlyList<OrderEvent> ModifyOrder")
    modify_body = cs[modify_idx : modify_idx + 2500]
    assert "SimAccountWhitelist.DenyReason" in modify_body
    assert modify_body.index("SimAccountWhitelist.DenyReason") < modify_body.index("target.QuantityChanged")
    cancel_idx = cs.index("public IReadOnlyList<OrderEvent> CancelOrder")
    cancel_body = cs[cancel_idx:modify_idx]
    assert "SimAccountWhitelist.DenyReason" not in cancel_body
    assert "QuantityChanged" not in cancel_body


@pytest.mark.unit
@pytest.mark.safety_gate
def test_constitution_violation_equivalent_payload_validates() -> None:
    payload = s1_reject_event_data(
        event="s1.sim_whitelist.reject",
        reason=SIM_WHITELIST_EMPTY,
        agent_id="agent-x",
        mode="sim",
        account="Sim101",
    )
    parsed = ConstitutionViolation.model_validate(payload)
    assert parsed.principle_name == SIM_WHITELIST_EMPTY
    assert parsed.severity == "error"
    assert parsed.mode == "sim"
    assert parsed.description == "s1.sim_whitelist.reject"
    live_payload = s1_reject_event_data(
        event="s1.live_release.reject",
        reason=LIVE_ACCOUNT_PATH_CLOSED_S1,
        agent_id="agent-y",
        approved_by="steve.operator",
    )
    live_parsed = ConstitutionViolation.model_validate(live_payload)
    assert live_parsed.principle_name == LIVE_ACCOUNT_PATH_CLOSED_S1


class _EventDataHandler(logging.Handler):
    """Capture structured extras even when parent ``lumina`` does not propagate."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, object]] = []

    def emit(self, record: logging.LogRecord) -> None:
        payload = getattr(record, "event_data", None)
        if isinstance(payload, dict):
            self.events.append(payload)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_reject_log_keeps_agent_id() -> None:
    handler = _EventDataHandler()
    sim_log = logging.getLogger("lumina.risk.sim_account_guard")
    live_log = logging.getLogger("lumina.risk.live_release")
    parent = logging.getLogger("lumina")
    previous_propagate = parent.propagate
    sim_log.addHandler(handler)
    live_log.addHandler(handler)
    sim_log.setLevel(logging.ERROR)
    live_log.setLevel(logging.ERROR)
    try:
        # Coverage Report runs integration tests that call build_logger("lumina").
        parent.propagate = False
        log_sim_reject(reason=SIM_WHITELIST_EMPTY, account="Sim101", mode="sim", agent_id="agent-x")
        sim_payload = next((item for item in handler.events if item.get("agent_id") == "agent-x"), None)
        assert sim_payload is not None
        assert sim_payload["event"] == "s1.sim_whitelist.reject"
        assert sim_payload["reason"] == SIM_WHITELIST_EMPTY
        assert sim_payload["principle_name"] == SIM_WHITELIST_EMPTY
        assert sim_payload["account"] == "Sim101"
        assert sim_payload["mode"] == "sim"
        assert sim_payload["timestamp"]
        parsed = ConstitutionViolation.model_validate(sim_payload)
        assert parsed.principle_name == SIM_WHITELIST_EMPTY
        handler.events.clear()
        log_live_reject(
            reason=LIVE_ACCOUNT_PATH_CLOSED_S1,
            agent_id="agent-y",
            approved_by="steve.operator",
        )
        live_payload = next((item for item in handler.events if item.get("agent_id") == "agent-y"), None)
        assert live_payload is not None
        assert live_payload["event"] == "s1.live_release.reject"
        assert live_payload["reason"] == LIVE_ACCOUNT_PATH_CLOSED_S1
        assert live_payload["approved_by"] == "steve.operator"
        live_parsed = ConstitutionViolation.model_validate(live_payload)
        assert live_parsed.principle_name == LIVE_ACCOUNT_PATH_CLOSED_S1
    finally:
        sim_log.removeHandler(handler)
        live_log.removeHandler(handler)
        parent.propagate = previous_propagate


@pytest.mark.unit
def test_enabled_string_true_does_not_enable_live_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    reset_live_release_nonces_for_tests()
    record = signed_live_release(enabled="true", nonce="n-str-true-16xxxxxx")
    ok, reason = verify_live_release(record)
    assert ok is False
    assert reason == LIVE_RELEASE_DISABLED


@pytest.mark.unit
def test_plus00_timestamp_and_naive_datetime_objects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    reset_live_release_nonces_for_tests()
    now = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
    plus = signed_live_release(
        now=now,
        approved_at_utc="2026-10-29T12:00:00+00:00",
        expires_at_utc="2026-10-30T12:00:00+00:00",
        nonce="n-plus00-16xxxxxxxxx",
    )
    ok, reason = verify_live_release(plus, now=now)
    assert ok is True, reason

    naive = signed_live_release(
        now=now,
        approved_at_utc=datetime(2026, 10, 29, 12, 0),
        nonce="n-naive-dt-16xxxxxxxx",
    )
    ok, reason = verify_live_release(naive, now=now)
    assert ok is False
    assert reason == LIVE_RELEASE_TIMESTAMP_NOT_UTC
    naive_clock = signed_live_release(now=now, nonce="n-naive-now-16xxxxxxx")
    ok, reason = verify_live_release(naive_clock, now=datetime(2026, 10, 29, 12, 0))
    assert ok is False
    assert reason == LIVE_RELEASE_TIMESTAMP_NOT_UTC
    ok, reason = verify_live_release(naive_clock, now="2026-10-29T12:00:00+00:00")
    assert ok is False
    assert reason == LIVE_RELEASE_TIMESTAMP_NOT_UTC


@pytest.mark.unit
def test_missing_purpose_is_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    reset_live_release_nonces_for_tests()
    record = signed_live_release(purpose="", nonce="n-empty-purpose-16xxx")
    ok, reason = verify_live_release(record)
    assert ok is False
    assert reason == LIVE_RELEASE_PURPOSE_INVALID


@pytest.mark.unit
def test_live_release_step_still_closes_if_hmac_ok_is_forced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "lumina_core.order_gatekeeper.admission_s1_steps.admit_live_orders",
        lambda *_a, **_k: (True, LIVE_RELEASE_HMAC_OK),
    )
    engine = SimpleNamespace(config=SimpleNamespace(live_release_payload={"enabled": True}))
    ctx = AdmissionContext(
        engine=engine,
        mode="real",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        metadata={"live_release": {"enabled": True}},
        step_handlers={ADMISSION_STEP_LIVE_RELEASE: make_live_release_step(SimpleNamespace(engine=engine))},
    )
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_LIVE_RELEASE,)).run(ctx)
    assert allowed is False
    assert reason == LIVE_ACCOUNT_PATH_CLOSED_S1


@pytest.mark.unit
def test_live_release_metadata_wins_over_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    reset_live_release_nonces_for_tests()
    good = signed_live_release(nonce="n-meta-engine-16xxxxxx")
    engine = SimpleNamespace(config=SimpleNamespace(live_release_payload=good))
    ctx = AdmissionContext(
        engine=engine,
        mode="real",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        metadata={"live_release": signed_live_release(enabled=False, nonce="n-meta-disabled-16xxx")},
        step_handlers={ADMISSION_STEP_LIVE_RELEASE: make_live_release_step(SimpleNamespace(engine=engine))},
    )
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_LIVE_RELEASE,)).run(ctx)
    assert allowed is False
    assert reason == LIVE_RELEASE_DISABLED


@pytest.mark.unit
def test_connection_attr_resolves_account() -> None:
    engine = SimpleNamespace(nt_connection=SimpleNamespace(account_name="Sim101"))
    assert connected_account_from_engine(engine) == "Sim101"
    engine2 = SimpleNamespace(connection=SimpleNamespace(account_name="Sim202"))
    assert connected_account_from_engine(engine2) == "Sim202"


@pytest.mark.unit
def test_signed_widen_keeps_existing_names(monkeypatch: pytest.MonkeyPatch) -> None:
    lock = SimWhitelistLock()
    monkeypatch.setattr("lumina_core.risk.sim_account_guard.LOCK", lock)
    lock.freeze(("Sim101",))
    ok, _reason = apply_signed_whitelist_widen(("Sim202",), verified=True, verify_reason="ok")
    assert ok is True
    assert admit_sim_account("Sim101", ("Sim101",), mode="sim") == (True, "ok")
    assert admit_sim_account("Sim202", ("Sim101",), mode="sim") == (True, "ok")


@pytest.mark.unit
def test_wrong_key_independent_mac(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    reset_live_release_nonces_for_tests()
    record = signed_live_release(secret=TEST_SECRET, nonce="n-ind-mac-16xxxxxxxx")
    other = compute_live_release_mac(record, b"other-secret-key-xx")
    assert hmac.compare_digest(record["mac"], other) is False
    monkeypatch.setenv(SECRET_ENV, "other-secret-key-xx")
    ok, reason = verify_live_release(record)
    assert ok is False
    assert reason == LIVE_RELEASE_MAC_MISMATCH


@pytest.mark.unit
def test_safe_mode_blocks_modify_allows_cancel() -> None:
    conn = NinjaTraderConnectionState(state="connected", account_name="Sim101", safe_mode="SAFE")
    ok_m, reason_m = assert_nt_bridge_capability(
        action=NtBridgeAction.MODIFY_ORDER,
        trade_mode="sim",
        connection=conn,
        configured_account="Sim101",
        ninjatrader_enabled=True,
        sim_account_whitelist=("Sim101",),
    )
    assert ok_m is False
    assert "safe_mode" in reason_m
    ok_c, reason_c = assert_nt_bridge_capability(
        action=NtBridgeAction.CANCEL,
        trade_mode="sim",
        connection=conn,
        configured_account="Sim101",
        ninjatrader_enabled=True,
        sim_account_whitelist=(),
    )
    assert ok_c is True
    assert reason_c == "ok"


@pytest.mark.unit
def test_canonical_mac_uses_explicit_purpose() -> None:
    record = {
        "enabled": True,
        "adr_path": "docs/adr/0061-sim-whitelist-and-live-release.md",
        "adr_sha256": "a" * 64,
        "approved_by": "steve.operator",
        "approved_at_utc": "2026-10-29T00:00:00Z",
        "expires_at_utc": "2026-10-30T00:00:00Z",
        "nonce": "frozen-nonce-16xx",
        "purpose": "sim_whitelist_widen",
        "schema_version": "live_release.v1",
    }
    body = canonical_live_release_payload(record)
    assert b'"purpose":"sim_whitelist_widen"' in body
    assert b'"schema_version":"live_release.v1"' in body
    unsorted = (
        '{"enabled":true,"nonce":"frozen-nonce-16xx","purpose":"sim_whitelist_widen",'
        '"schema_version":"live_release.v1","approved_by":"steve.operator",'
        '"adr_path":"docs/adr/0061-sim-whitelist-and-live-release.md",'
        '"adr_sha256":"' + ("a" * 64) + '",'
        '"approved_at_utc":"2026-10-29T00:00:00Z",'
        '"expires_at_utc":"2026-10-30T00:00:00Z"}'
    ).encode("utf-8")
    assert body != unsorted
    assert body.startswith(b'{"adr_path":')
