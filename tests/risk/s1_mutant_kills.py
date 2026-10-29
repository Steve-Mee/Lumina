"""Fail-closed kill battery for S1 whitelist + LIVE_RELEASE. No pytest."""

from __future__ import annotations

import hmac
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from lumina_core.broker.ninjatrader.account_names import account_on_sim_whitelist, is_local_sim_name
from lumina_core.broker.ninjatrader.connection_state import NinjaTraderConnectionState
from lumina_core.agent_orchestration.schemas import ConstitutionViolation
from lumina_core.broker.ninjatrader.guards import assert_nt_bridge_capability, check_account_match
from lumina_core.broker.ninjatrader.promotion_gate import (
    NtBridgeAction,
    action_enforces_sim_whitelist,
    action_for_command_frame,
)
from lumina_core.code_evolution.operators import FORBIDDEN_PARAMETER_KEYS, validate_parameter_tweak
from lumina_core.code_evolution.proposal import FORBIDDEN_TARGET_PREFIXES
from lumina_core.engine.engine_config import _yaml_sim_account_whitelist
from lumina_core.engine.mode_capabilities import resolve_mode_capabilities
from lumina_core.order_gatekeeper import admission_s1_steps as s1_steps
from lumina_core.order_gatekeeper.admission_s1_steps import (
    attach_s1_admission_metadata,
    make_live_release_step,
    make_sim_account_whitelist_step,
)
from lumina_core.order_gatekeeper.ungated_place_block import (
    S0_PLACE_SOURCE_ALLOWLIST,
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
    freeze_is_armed,
    research_execution_mode_from_mapping,
)
from lumina_core.risk import sim_account_guard as sim_mod
from lumina_core.risk.admission_chain import (
    ADMISSION_STEP_LIVE_RELEASE,
    ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,
    CANONICAL_ADMISSION_STEPS,
    UNBYPASSABLE_ADMISSION_STEPS,
    AdmissionChain,
    AdmissionContext,
)
from lumina_core.risk.live_release import (
    LIVE_ACCOUNT_PATH_CLOSED_S1,
    LIVE_RELEASE_ADR_HASH_INVALID,
    LIVE_RELEASE_ADR_REQUIRED,
    LIVE_RELEASE_AGENT_APPROVER_FORBIDDEN,
    LIVE_RELEASE_CLOCK_SKEW,
    LIVE_RELEASE_DISABLED,
    LIVE_RELEASE_EXPIRED,
    LIVE_RELEASE_HMAC_OK,
    LIVE_RELEASE_HMAC_REQUIRED,
    LIVE_RELEASE_MAC_INVALID,
    LIVE_RELEASE_MAC_MISMATCH,
    LIVE_RELEASE_NONCE_INVALID,
    LIVE_RELEASE_PURPOSE_INVALID,
    LIVE_RELEASE_RECORD_MISSING,
    LIVE_RELEASE_REPLAY,
    LIVE_RELEASE_REQUIRED,
    LIVE_RELEASE_SECRET_MISSING,
    LIVE_RELEASE_TIMESTAMP_NOT_UTC,
    LIVE_RELEASE_WINDOW_INVALID,
    PURPOSE_LIVE,
    PURPOSE_WHITELIST_WIDEN,
    SCHEMA_VERSION,
    SECRET_ENV,
    admit_live_orders,
    canonical_live_release_payload,
    compute_live_release_mac,
    live_release_from_engine,
    nonce_was_used,
    reset_live_release_nonces_for_tests,
    verify_live_release,
    _consume_nonce,
    _parse_utc,
)
from lumina_core.risk.sim_account_guard import (
    ACCOUNT_UNKNOWN,
    SIM_ACCOUNT_NOT_WHITELISTED,
    SIM_WHITELIST_EMPTY,
    SIM_WHITELIST_LIVE_NAME_FORBIDDEN,
    SIM_WHITELIST_TAMPERED,
    SIM_WHITELIST_WIDEN_REFUSED,
    SIM_WHITELIST_WIDENED,
    SimWhitelistLock,
    admit_sim_account,
    apply_signed_whitelist_widen,
    canonicalize_whitelist,
    connected_account_from_engine,
    log_sim_reject,
    modes_requiring_whitelist,
    whitelist_from_engine,
)
from lumina_core.risk.s1_events import s1_reject_event_data
from lumina_core.runtime_config_reloader import _immutable_field_changes
from tests.risk.s1_hmac import TEST_SECRET, signed_live_release

REPO_ROOT = Path(__file__).resolve().parents[2]

FROZEN_NOW = datetime(2026, 10, 29, 12, 0, tzinfo=timezone.utc)
FROZEN_RECORD = {
    "enabled": True,
    "adr_path": "docs/adr/0061-sim-whitelist-and-live-release.md",
    "adr_sha256": "a" * 64,
    "approved_by": "steve.operator",
    "approved_at_utc": "2026-10-29T00:00:00Z",
    "expires_at_utc": "2026-10-30T00:00:00Z",
    "nonce": "frozen-nonce-16xx",
    "purpose": PURPOSE_LIVE,
    "schema_version": SCHEMA_VERSION,
}
FROZEN_CANONICAL = (
    '{"adr_path":"docs/adr/0061-sim-whitelist-and-live-release.md",'
    '"adr_sha256":"' + ("a" * 64) + '",'
    '"approved_at_utc":"2026-10-29T00:00:00Z",'
    '"approved_by":"steve.operator",'
    '"enabled":true,'
    '"expires_at_utc":"2026-10-30T00:00:00Z",'
    '"nonce":"frozen-nonce-16xx",'
    '"purpose":"live_enablement",'
    '"schema_version":"live_release.v1"}'
).encode("utf-8")


def _fail(message: str) -> None:
    raise AssertionError(message)


def _fresh(names: tuple[str, ...] | None = None) -> SimWhitelistLock:
    lock = SimWhitelistLock()
    if names is not None:
        lock.freeze(names)
    sim_mod.LOCK = lock
    return lock


def _expect_deny(account: str, whitelist: tuple[str, ...] | None, want: str, *, mode: str = "sim") -> None:
    ok, reason = admit_sim_account(account, whitelist, mode=mode)
    if ok is not False or reason != want:
        _fail(f"expected deny {want} for {account!r} got {(ok, reason)}")


def _expect_allow(account: str, whitelist: tuple[str, ...], *, mode: str = "sim") -> None:
    ok, reason = admit_sim_account(account, whitelist, mode=mode)
    if ok is not True or reason != "ok":
        _fail(f"expected allow {account!r} got {(ok, reason)}")


def _whitelist_battery() -> None:
    _fresh()
    _expect_deny("Sim101", (), SIM_WHITELIST_EMPTY)
    _fresh()
    _expect_deny("Sim101", None, SIM_WHITELIST_EMPTY)
    _fresh()
    _expect_deny("Sim101", "Sim101", SIM_WHITELIST_EMPTY)  # type: ignore[arg-type]
    _fresh()
    if account_on_sim_whitelist("Sim101", []) is not False:
        _fail("empty membership must deny")
    if is_local_sim_name("Sim202") is not True:
        _fail("prefix helper still diagnoses Sim202")
    _fresh(("Sim101",))
    _expect_deny("Sim202", ("Sim101",), SIM_ACCOUNT_NOT_WHITELISTED)
    _fresh(("Sim101",))
    _expect_deny("LiveAcct", ("LiveAcct",), SIM_ACCOUNT_NOT_WHITELISTED)
    _fresh(("Sim101",))
    _expect_deny("", ("Sim101",), ACCOUNT_UNKNOWN)
    _fresh(("Sim101",))
    _expect_allow("Sim101", ("Sim101",))
    _fresh(("Sim101",))
    _expect_allow("sim101", ("Sim101",))
    _fresh(("DEMO5042070",))
    _expect_allow("DEMO5042070", ("DEMO5042070",))
    names = canonicalize_whitelist([" Sim101 ", "sim101", "Sim202"])
    if names != ("Sim101", "Sim202"):
        _fail(f"canonicalize {names}")
    lock = _fresh(("Sim101",))
    effective, status = lock.effective(("Sim101", "Sim202"))
    if status != "ok" or "Sim202" in {item.casefold() for item in effective}:
        _fail(f"widen via yaml {effective} {status}")
    _expect_deny("Sim202", ("Sim101", "Sim202"), SIM_ACCOUNT_NOT_WHITELISTED)
    unlocked = SimWhitelistLock()
    if unlocked.is_tampered() is not False:
        _fail("unfrozen lock is not tampered")
    if unlocked.is_frozen() is not False:
        _fail("unfrozen lock must not report frozen")
    if unlocked.current() != frozenset():
        _fail("unfrozen current must be empty")
    frozen_ok = _fresh(("Sim101",))
    if frozen_ok.is_frozen() is not True:
        _fail("frozen lock must report frozen")
    if "Sim101" not in frozen_ok.current():
        _fail("frozen current must keep Sim101")
    tamper = _fresh(("Sim101",))
    tamper._frozen = frozenset({"Sim101", "Sim202"})  # noqa: SLF001
    if tamper.is_tampered() is not True:
        _fail("tamper not detected")
    if tamper.current() != frozenset():
        _fail("tampered current must deny-all")
    _expect_deny("Sim101", ("Sim101",), SIM_WHITELIST_TAMPERED)
    widen_tamper, widen_tamper_reason = tamper.widen(("Sim202",))
    if widen_tamper is not False or widen_tamper_reason != SIM_WHITELIST_TAMPERED:
        _fail(f"tampered widen {widen_tamper} {widen_tamper_reason}")
    _fresh(("Sim101",))
    refused, why = apply_signed_whitelist_widen(("Sim202",), verified=False, verify_reason="nope")
    if refused is not False or why != "nope":
        _fail(f"unsigned widen {refused} {why}")
    live_widen, live_why = apply_signed_whitelist_widen(("LiveAcct",), verified=True, verify_reason="ok")
    if live_widen is not False or live_why != SIM_WHITELIST_LIVE_NAME_FORBIDDEN:
        _fail(f"live widen {live_widen} {live_why}")
    empty_widen, empty_why = apply_signed_whitelist_widen((), verified=True, verify_reason="ok")
    if empty_widen is not False or empty_why != SIM_WHITELIST_WIDEN_REFUSED:
        _fail(f"empty widen {empty_widen} {empty_why}")
    _fresh(("Sim101",))
    ok, reason = apply_signed_whitelist_widen(("Sim202",), verified=True, verify_reason="ok")
    if ok is not True or reason != SIM_WHITELIST_WIDENED:
        _fail(f"signed paper widen {ok} {reason}")
    _expect_allow("Sim202", ("Sim101",))
    _expect_allow("Sim101", ("Sim101",))
    _fresh(("Sim101",))
    match_ok, match_reason = check_account_match(
        trade_mode="sim",
        configured_account="Sim101",
        connected_account="Sim101",
        sim_account_whitelist=("Sim101",),
    )
    if match_ok is not True or match_reason != "ok":
        _fail(f"guard allow {match_ok} {match_reason}")
    live_ok, live_reason = check_account_match(
        trade_mode="sim",
        configured_account="LiveAcct",
        connected_account="LiveAcct",
        sim_account_whitelist=("LiveAcct",),
    )
    if live_ok is not False or live_reason != SIM_ACCOUNT_NOT_WHITELISTED:
        _fail(f"guard live {live_ok} {live_reason}")
    real_ok, real_reason = check_account_match(
        trade_mode="real",
        configured_account="LiveAcct",
        connected_account="LiveAcct",
        live_release=None,
    )
    if real_ok is not False or real_reason != LIVE_RELEASE_REQUIRED:
        _fail(f"real missing release {real_ok} {real_reason}")
    conn = NinjaTraderConnectionState(state="connected", account_name="Sim101")
    cancel_ok, cancel_reason = assert_nt_bridge_capability(
        action=NtBridgeAction.CANCEL,
        trade_mode="sim",
        connection=conn,
        configured_account="Sim101",
        ninjatrader_enabled=True,
        sim_account_whitelist=(),
    )
    if cancel_ok is not True or cancel_reason != "ok":
        _fail(f"cancel must skip whitelist {cancel_ok} {cancel_reason}")
    _fresh(())
    submit_ok, submit_reason = assert_nt_bridge_capability(
        action=NtBridgeAction.SUBMIT_ORDER,
        trade_mode="sim",
        connection=conn,
        configured_account="Sim101",
        ninjatrader_enabled=True,
        sim_account_whitelist=(),
    )
    if submit_ok is not False or submit_reason != SIM_WHITELIST_EMPTY:
        _fail(f"submit empty whitelist {submit_ok} {submit_reason}")


def _live_battery() -> None:
    os.environ[SECRET_ENV] = TEST_SECRET
    reset_live_release_nonces_for_tests()
    got = canonical_live_release_payload(FROZEN_RECORD)
    if got != FROZEN_CANONICAL:
        _fail(f"canonical drifted {got!r}")
    independent_mac = hmac.new(TEST_SECRET.encode("utf-8"), FROZEN_CANONICAL, "sha256").hexdigest()
    computed = compute_live_release_mac(FROZEN_RECORD, TEST_SECRET.encode("utf-8"))
    if computed != independent_mac:
        _fail("mac drifted from independent hmac")
    frozen = dict(FROZEN_RECORD)
    frozen["mac"] = independent_mac
    ok, reason = verify_live_release(frozen, now=FROZEN_NOW)
    if ok is not True or reason != LIVE_RELEASE_HMAC_OK:
        _fail(f"frozen verify {ok} {reason}")
    allowed, closed = admit_live_orders(dict(frozen), now=FROZEN_NOW)
    if allowed is not False or closed != LIVE_RELEASE_REPLAY:
        _fail(f"admit after verify must replay {allowed} {closed}")
    reset_live_release_nonces_for_tests()
    frozen2 = dict(FROZEN_RECORD)
    frozen2["nonce"] = "frozen-nonce-16yy"
    frozen2["mac"] = hmac.new(
        TEST_SECRET.encode("utf-8"),
        json.dumps(
            {
                "adr_path": frozen2["adr_path"],
                "adr_sha256": frozen2["adr_sha256"],
                "approved_at_utc": frozen2["approved_at_utc"],
                "approved_by": frozen2["approved_by"],
                "enabled": True,
                "expires_at_utc": frozen2["expires_at_utc"],
                "nonce": frozen2["nonce"],
                "purpose": frozen2["purpose"],
                "schema_version": frozen2["schema_version"],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
        "sha256",
    ).hexdigest()
    allowed, closed = admit_live_orders(frozen2, now=FROZEN_NOW)
    if allowed is not False or closed != LIVE_ACCOUNT_PATH_CLOSED_S1:
        _fail(f"valid hmac must still close live {allowed} {closed}")

    cases = (
        (None, LIVE_RELEASE_RECORD_MISSING),
        (signed_live_release(enabled=False, nonce="n-disabled-16xxxx", now=FROZEN_NOW), LIVE_RELEASE_DISABLED),
        (signed_live_release(mac="", nonce="n-hmac-req-16xxxx", now=FROZEN_NOW), LIVE_RELEASE_HMAC_REQUIRED),
        (signed_live_release(mac="b" * 32, nonce="n-mac-inv-16xxxxx", now=FROZEN_NOW), LIVE_RELEASE_MAC_INVALID),
        (signed_live_release(mac="b" * 64, nonce="n-mac-mis-16xxxxx", now=FROZEN_NOW), LIVE_RELEASE_MAC_MISMATCH),
        (signed_live_release(approved_by="research_bridge", nonce="n-agent-16xxxxxxx", now=FROZEN_NOW), LIVE_RELEASE_AGENT_APPROVER_FORBIDDEN),
        (signed_live_release(adr_path="not-an-adr", nonce="n-adr-16xxxxxxxxxx", now=FROZEN_NOW), LIVE_RELEASE_ADR_REQUIRED),
        (signed_live_release(adr_sha256="nope", nonce="n-adr-hash-16xxxxx", now=FROZEN_NOW), LIVE_RELEASE_ADR_HASH_INVALID),
        (signed_live_release(purpose="other", nonce="n-purpose-16xxxxxxx", now=FROZEN_NOW), LIVE_RELEASE_PURPOSE_INVALID),
        (signed_live_release(schema_version="v0", nonce="n-schema-16xxxxxxxx", now=FROZEN_NOW), LIVE_RELEASE_PURPOSE_INVALID),
        (signed_live_release(nonce="short", now=FROZEN_NOW), LIVE_RELEASE_NONCE_INVALID),
        (signed_live_release(approved_at_utc="2026-10-29T00:00:00", nonce="n-naive-16xxxxxxxx", now=FROZEN_NOW), LIVE_RELEASE_TIMESTAMP_NOT_UTC),
    )
    for record, want in cases:
        reset_live_release_nonces_for_tests()
        got_ok, got_reason = verify_live_release(record, now=FROZEN_NOW)
        if got_ok is not False or got_reason != want:
            _fail(f"verify {want} got {(got_ok, got_reason)}")

    os.environ.pop(SECRET_ENV, None)
    reset_live_release_nonces_for_tests()
    missing_ok, missing_reason = verify_live_release(signed_live_release(nonce="n-secret-16xxxxxxx"))
    if missing_ok is not False or missing_reason != LIVE_RELEASE_SECRET_MISSING:
        _fail(f"missing secret {missing_ok} {missing_reason}")
    os.environ[SECRET_ENV] = "short"
    short_ok, short_reason = verify_live_release(signed_live_release(nonce="n-short-secret-16xx"))
    if short_ok is not False or short_reason != LIVE_RELEASE_SECRET_MISSING:
        _fail(f"short secret {short_ok} {short_reason}")
    os.environ[SECRET_ENV] = TEST_SECRET
    now = datetime.now(timezone.utc)
    future = signed_live_release(now=now + timedelta(minutes=30), nonce="n-skew-16xxxxxxxxxx")
    skew_ok, skew_reason = verify_live_release(future, now=now)
    if skew_ok is not False or skew_reason != LIVE_RELEASE_CLOCK_SKEW:
        _fail(f"clock skew {skew_ok} {skew_reason}")
    expired = signed_live_release(
        now=now,
        expires_at_utc=(now - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
        nonce="n-expired-16xxxxxxxx",
    )
    exp_ok, exp_reason = verify_live_release(expired, now=now)
    if exp_ok is not False or exp_reason != LIVE_RELEASE_EXPIRED:
        _fail(f"expired {exp_ok} {exp_reason}")
    wide = signed_live_release(
        now=now,
        expires_at_utc=(now + timedelta(days=8)).isoformat().replace("+00:00", "Z"),
        nonce="n-window-16xxxxxxxxx",
    )
    win_ok, win_reason = verify_live_release(wide, now=now)
    if win_ok is not False or win_reason != LIVE_RELEASE_WINDOW_INVALID:
        _fail(f"window {win_ok} {win_reason}")
    edge = signed_live_release(now=now + timedelta(minutes=5), nonce="n-skew-edge-16xxxxx")
    edge_ok, edge_reason = verify_live_release(edge, now=now)
    if edge_ok is not True:
        _fail(f"skew == 5m must verify {edge_ok} {edge_reason}")
    replay = signed_live_release(nonce="replay-nonce-0001xx")
    first_ok, _first = verify_live_release(replay)
    if first_ok is not True:
        _fail("replay first must verify")
    again_ok, again_reason = verify_live_release(signed_live_release(nonce="replay-nonce-0001xx"))
    if again_ok is not False or again_reason != LIVE_RELEASE_REPLAY:
        _fail(f"replay {again_ok} {again_reason}")
    os.environ[SECRET_ENV] = "other-secret-key-xx"
    wrong = signed_live_release(secret=TEST_SECRET, nonce="n-wrong-key-16xxxxxx")
    wrong_ok, wrong_reason = verify_live_release(wrong)
    if wrong_ok is not False or wrong_reason != LIVE_RELEASE_MAC_MISMATCH:
        _fail(f"wrong key {wrong_ok} {wrong_reason}")
    os.environ[SECRET_ENV] = TEST_SECRET
    tampered = signed_live_release(nonce="n-tamper-16xxxxxxxxx")
    tampered["approved_by"] = "steve.operator.x"
    tamper_ok, tamper_reason = verify_live_release(tampered)
    if tamper_ok is not False or tamper_reason != LIVE_RELEASE_MAC_MISMATCH:
        _fail(f"tamper {tamper_ok} {tamper_reason}")
    widen_rec = signed_live_release(purpose=PURPOSE_WHITELIST_WIDEN, nonce="n-widen-purpose-16xx")
    purpose_ok, purpose_reason = verify_live_release(widen_rec, expected_purpose=PURPOSE_LIVE)
    if purpose_ok is not False or purpose_reason != LIVE_RELEASE_PURPOSE_INVALID:
        _fail(f"wrong purpose {purpose_ok} {purpose_reason}")
    not_map_ok, not_map_reason = verify_live_release(["nope"])  # type: ignore[arg-type]
    if not_map_ok is not False or not_map_reason != LIVE_RELEASE_RECORD_MISSING:
        _fail(f"non-mapping record {not_map_ok} {not_map_reason}")
    short_approver_ok, short_approver_reason = verify_live_release(
        signed_live_release(approved_by="x", nonce="n-short-approver-16xx")
    )
    if short_approver_ok is not False or short_approver_reason != LIVE_RELEASE_AGENT_APPROVER_FORBIDDEN:
        _fail(f"short approver {short_approver_ok} {short_approver_reason}")
    bad_hex_ok, bad_hex_reason = verify_live_release(signed_live_release(mac="g" * 64, nonce="n-bad-hex-16xxxxxxxx"))
    if bad_hex_ok is not False or bad_hex_reason != LIVE_RELEASE_MAC_INVALID:
        _fail(f"non-hex mac {bad_hex_ok} {bad_hex_reason}")


def _admission_battery() -> None:
    if CANONICAL_ADMISSION_STEPS[:3] != (
        "session_equity_sync",
        ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,
        ADMISSION_STEP_LIVE_RELEASE,
    ):
        _fail(f"canonical steps {CANONICAL_ADMISSION_STEPS}")
    if ADMISSION_STEP_SIM_ACCOUNT_WHITELIST not in UNBYPASSABLE_ADMISSION_STEPS:
        _fail("whitelist must be unbypassable")
    if ADMISSION_STEP_LIVE_RELEASE not in UNBYPASSABLE_ADMISSION_STEPS:
        _fail("live_release must be unbypassable")
    os.environ["LUMINA_ADMISSION_BYPASS_STEPS"] = "sim_account_whitelist,live_release"
    try:
        engine = SimpleNamespace(nt_connected_account="Sim101", config=SimpleNamespace())
        ctx = AdmissionContext(
            engine=engine,
            mode="sim",
            symbol="MES",
            regime="NEUTRAL",
            proposed_risk=1.0,
            metadata={"connected_account": "Sim101", "sim_account_whitelist": ("Sim101",)},
            step_handlers={
                ADMISSION_STEP_SIM_ACCOUNT_WHITELIST: lambda _ctx: (True, "ok"),
                ADMISSION_STEP_LIVE_RELEASE: lambda _ctx: (True, "ok"),
            },
            experimental_bypass_step_ids=frozenset(
                {ADMISSION_STEP_SIM_ACCOUNT_WHITELIST, ADMISSION_STEP_LIVE_RELEASE}
            ),
        )
        allowed, reason, _trace = AdmissionChain(
            steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST, ADMISSION_STEP_LIVE_RELEASE)
        ).run(ctx)
        if allowed is not False or "experimental_bypass_forbidden" not in reason:
            _fail(f"bypass opened {allowed} {reason}")
    finally:
        os.environ.pop("LUMINA_ADMISSION_BYPASS_STEPS", None)

    _fresh(("Sim101",))
    engine = SimpleNamespace(
        nt_connected_account="Sim101",
        config=SimpleNamespace(ninjatrader_sim_account_whitelist=("Sim101",), live_release_payload={"enabled": False}),
    )
    wl_ctx = AdmissionContext(
        engine=engine,
        mode="sim",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        metadata={"connected_account": "LiveAcct", "sim_account_whitelist": ("Sim101",)},
        step_handlers={
            ADMISSION_STEP_SIM_ACCOUNT_WHITELIST: make_sim_account_whitelist_step(SimpleNamespace(engine=engine))
        },
    )
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,)).run(wl_ctx)
    if allowed is not False or reason != SIM_ACCOUNT_NOT_WHITELISTED:
        _fail(f"admission live name {allowed} {reason}")

    os.environ[SECRET_ENV] = TEST_SECRET
    reset_live_release_nonces_for_tests()
    record = signed_live_release(nonce="n-admit-live-16xxxxxx")
    live_engine = SimpleNamespace(config=SimpleNamespace(live_release_payload=record))
    lr_ctx = AdmissionContext(
        engine=live_engine,
        mode="real",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        metadata={"live_release": record},
        step_handlers={ADMISSION_STEP_LIVE_RELEASE: make_live_release_step(SimpleNamespace(engine=live_engine))},
    )
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_LIVE_RELEASE,)).run(lr_ctx)
    if allowed is not False or reason != LIVE_ACCOUNT_PATH_CLOSED_S1:
        _fail(f"admission live step {allowed} {reason}")
    paper_ctx = AdmissionContext(
        engine=engine,
        mode="paper",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        step_handlers={
            ADMISSION_STEP_SIM_ACCOUNT_WHITELIST: make_sim_account_whitelist_step(SimpleNamespace(engine=engine))
        },
    )
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,)).run(paper_ctx)
    if allowed is not True or reason != "not_required_paper":
        _fail(f"paper skip {allowed} {reason}")

    real_wl = AdmissionContext(
        engine=engine,
        mode="real",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        metadata={"connected_account": "LiveAcct", "sim_account_whitelist": ("Sim101",)},
        step_handlers={
            ADMISSION_STEP_SIM_ACCOUNT_WHITELIST: make_sim_account_whitelist_step(SimpleNamespace(engine=engine))
        },
    )
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,)).run(real_wl)
    if allowed is not True or reason != "sim_whitelist_not_applicable_real":
        _fail(f"real whitelist skip {allowed} {reason}")

    sim_lr = AdmissionContext(
        engine=engine,
        mode="sim",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        step_handlers={ADMISSION_STEP_LIVE_RELEASE: make_live_release_step(SimpleNamespace(engine=engine))},
    )
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_LIVE_RELEASE,)).run(sim_lr)
    if allowed is not True or reason != "live_release_not_required":
        _fail(f"sim live_release skip {allowed} {reason}")

    _fresh(("Sim101",))
    sim_ok_ctx = AdmissionContext(
        engine=engine,
        mode="sim",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        metadata={"connected_account": "Sim101", "sim_account_whitelist": ("Sim101",)},
        step_handlers={
            ADMISSION_STEP_SIM_ACCOUNT_WHITELIST: make_sim_account_whitelist_step(SimpleNamespace(engine=engine))
        },
    )
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,)).run(sim_ok_ctx)
    if allowed is not True or reason != "ok":
        _fail(f"sim whitelist allow {allowed} {reason}")

    _fresh()
    meta_only_engine = SimpleNamespace(nt_connected_account="Sim101", config=SimpleNamespace())
    meta_only = AdmissionContext(
        engine=meta_only_engine,
        mode="sim",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        metadata={"connected_account": "Sim101", "sim_account_whitelist": ("Sim101",)},
        step_handlers={
            ADMISSION_STEP_SIM_ACCOUNT_WHITELIST: make_sim_account_whitelist_step(
                SimpleNamespace(engine=meta_only_engine)
            )
        },
    )
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,)).run(meta_only)
    if allowed is not True or reason != "ok":
        _fail(f"metadata whitelist allow {allowed} {reason}")

    unknown_ctx = AdmissionContext(
        engine=engine,
        mode="shadow",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        step_handlers={
            ADMISSION_STEP_SIM_ACCOUNT_WHITELIST: make_sim_account_whitelist_step(SimpleNamespace(engine=engine))
        },
    )
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_SIM_ACCOUNT_WHITELIST,)).run(unknown_ctx)
    if allowed is not False or "nt_bridge_not_allowed_in_mode" not in reason:
        _fail(f"unknown mode whitelist {allowed} {reason}")

    meta: dict[str, object] = {}
    attach_engine = SimpleNamespace(
        nt_connected_account="Sim101",
        config=SimpleNamespace(
            ninjatrader_sim_account_whitelist=("Sim101",),
            live_release_payload={"enabled": False, "mac": ""},
        ),
    )
    attach_s1_admission_metadata(attach_engine, meta)
    if meta.get("connected_account") != "Sim101":
        _fail(f"attach account {meta}")
    if tuple(meta.get("sim_account_whitelist") or ()) != ("Sim101",):
        _fail(f"attach whitelist {meta}")
    if meta.get("live_release") != {"enabled": False, "mac": ""}:
        _fail(f"attach live_release {meta}")


def _s0_and_policy_battery() -> None:
    if freeze_is_armed() is not True:
        _fail("S0 freeze must stay armed")
    if S0_PLACE_SOURCE_ALLOWLIST:
        _fail("S0 allow-list must stay empty")
    if research_execution_mode_from_mapping({"research_execution_mode": "live"}) != "off":
        _fail("illegal research mode is off")
    blocked, reason = assert_validation_gate_or_block(
        "supervisor_tick_exec.run_tick_exec",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
        source_agent="research_bridge",
    )
    if blocked is not False or reason != UNGATED_PLACE_BLOCK_REASON:
        _fail(f"supervisor still closed {blocked} {reason}")
    if resolve_mode_capabilities("sim").risk_enforced is not False:
        _fail("sim stays learning-mode")
    if resolve_mode_capabilities("sim_real_guard").risk_enforced is not True:
        _fail("sim_real_guard must enforce")
    if resolve_mode_capabilities("real").risk_enforced is not True:
        _fail("real must enforce")
    try:
        resolve_mode_capabilities("not-a-mode")
    except ValueError:
        pass
    else:
        _fail("unknown mode must raise")
    for key in ("live_release", "sim_account_whitelist", "account_name", "mode", "trade_mode", "research_execution_mode"):
        if key not in FORBIDDEN_PARAMETER_KEYS:
            _fail(f"forbidden key missing {key}")
        if "forbidden_parameter_key" not in validate_parameter_tweak(key, 1.0, 2.0):
            _fail(f"tweak allowed {key}")
    if "lumina_core/risk/live_release" not in FORBIDDEN_TARGET_PREFIXES:
        _fail("live_release prefix missing")
    if "lumina_core/risk/sim_account_guard" not in FORBIDDEN_TARGET_PREFIXES:
        _fail("sim_account_guard prefix missing")
    live = SimpleNamespace(
        trade_mode="sim",
        live_release_enabled=False,
        live_release_mac="",
        live_release_payload={"enabled": False, "mac": ""},
        ninjatrader_sim_account_whitelist=("Sim101",),
        ninjatrader_account_name="Sim101",
        research_execution_mode="shadow",
    )
    cfg = {
        "live_release": {"enabled": True, "mac": "a" * 64},
        "broker": {"ninjatrader": {"sim_account_whitelist": ["Sim101", "Sim202"], "account_name": "Sim101"}},
        "research_execution_mode": "sim",
    }
    changed = _immutable_field_changes(cfg, live)
    if "live_release" not in changed or "sim_account_whitelist" not in changed or "research_execution_mode" not in changed:
        _fail(f"immutable changes {changed}")
    same = {
        "live_release": {"enabled": False, "mac": ""},
        "broker": {"ninjatrader": {"sim_account_whitelist": ["Sim101"], "account_name": "Sim101"}},
        "research_execution_mode": "shadow",
    }
    unchanged = _immutable_field_changes(same, live)
    if "sim_account_whitelist" in unchanged:
        _fail(f"tuple/list whitelist compared unequal {unchanged}")
    os.environ["NINJATRADER_SIM_WHITELIST"] = "Sim999,LiveAcct"
    os.environ["SIM_ACCOUNT_WHITELIST"] = "Sim999"
    names = _yaml_sim_account_whitelist()
    if "Sim999" in names or "LiveAcct" in names:
        _fail(f"env injected whitelist {names}")
    if connected_account_from_engine(None) != "":
        _fail("missing engine account")
    if connected_account_from_engine(SimpleNamespace(nt_connected_account=" Sim101 ")) != "Sim101":
        _fail("nt_connected_account")
    if connected_account_from_engine(SimpleNamespace(connected_account="DEMO5042070")) != "DEMO5042070":
        _fail("connected_account attr")
    nested = SimpleNamespace(config=SimpleNamespace(ninjatrader_account_name="Sim202"))
    if connected_account_from_engine(nested) != "Sim202":
        _fail("config account_name")
    broker_engine = SimpleNamespace(
        config=SimpleNamespace(broker={"ninjatrader": {"account_name": "Sim303", "sim_account_whitelist": ["Sim303"]}})
    )
    if connected_account_from_engine(broker_engine) != "Sim303":
        _fail("nested broker account")
    if whitelist_from_engine(None) != ():
        _fail("missing engine whitelist")
    if whitelist_from_engine(SimpleNamespace(config=SimpleNamespace(ninjatrader_sim_account_whitelist=("Sim101",)))) != (
        "Sim101",
    ):
        _fail("engine whitelist tuple")
    if whitelist_from_engine(SimpleNamespace(config=SimpleNamespace(ninjatrader_sim_account_whitelist="Sim101"))) != ():
        _fail("string whitelist from engine")
    if whitelist_from_engine(broker_engine) != ("Sim303",):
        _fail("nested broker whitelist")
    if "sim" not in modes_requiring_whitelist() or "sim_real_guard" not in modes_requiring_whitelist():
        _fail("modes requiring whitelist")
    if live_release_from_engine(None) is not None:
        _fail("live_release missing engine")
    if live_release_from_engine(SimpleNamespace()) is not None:
        _fail("live_release missing config")
    if live_release_from_engine(SimpleNamespace(config=SimpleNamespace())) is not None:
        _fail("live_release missing payload")
    payload_engine = SimpleNamespace(config=SimpleNamespace(live_release_payload={"enabled": False, "mac": ""}))
    got_payload = live_release_from_engine(payload_engine)
    if got_payload != {"enabled": False, "mac": ""}:
        _fail(f"live_release payload {got_payload}")
    reset_live_release_nonces_for_tests()
    if nonce_was_used("unused-nonce-16xxxx") is not False:
        _fail("fresh nonce must be unused")
    os.environ[SECRET_ENV] = TEST_SECRET
    used = signed_live_release(nonce="used-nonce-16xxxxx")
    verify_live_release(used)
    if nonce_was_used("used-nonce-16xxxxx") is not True:
        _fail("consumed nonce must be marked used")


class _MemLog(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[dict[str, object]] = []

    def emit(self, record: logging.LogRecord) -> None:
        payload = getattr(record, "event_data", None)
        if isinstance(payload, dict):
            self.events.append(payload)


def _gap_battery() -> None:
    live_src = (REPO_ROOT / "lumina_core/risk/live_release.py").read_text(encoding="utf-8")
    guard_src = (REPO_ROOT / "lumina_core/risk/sim_account_guard.py").read_text(encoding="utf-8")
    if "hmac.compare_digest(expected, mac)" not in live_src:
        _fail("MAC compare must be timing-safe")
    if "sort_keys=True" not in live_src:
        _fail("canonical MAC must sort keys")
    if guard_src.count("hmac.compare_digest") < 3:
        _fail("seal compare must be timing-safe")
    if account_on_sim_whitelist("Sim101", ("Sim",)) is not False:
        _fail("prefix on list must not admit Sim101")
    if account_on_sim_whitelist("Sim101\u200b", ("Sim101",)) is not False:
        _fail("zero-width must not match")
    if account_on_sim_whitelist("\u0405im101", ("Sim101",)) is not False:
        _fail("homoglyph must not match")
    if action_for_command_frame("modify_order") is not NtBridgeAction.MODIFY_ORDER:
        _fail("modify_order frame must be MODIFY")
    if action_for_command_frame("flatten") is not NtBridgeAction.CANCEL:
        _fail("flatten must stay CANCEL")
    if action_for_command_frame("weird") is not NtBridgeAction.SUBMIT_ORDER:
        _fail("unknown frames must not skip whitelist")
    if action_enforces_sim_whitelist(NtBridgeAction.MODIFY_ORDER) is not True:
        _fail("modify must be whitelisted")
    if action_enforces_sim_whitelist(NtBridgeAction.CANCEL) is not False:
        _fail("cancel skip is flatten-only")
    _fresh(())
    conn = NinjaTraderConnectionState(state="connected", account_name="Sim101")
    mod_ok, mod_reason = assert_nt_bridge_capability(
        action=NtBridgeAction.MODIFY_ORDER,
        trade_mode="sim",
        connection=conn,
        configured_account="Sim101",
        ninjatrader_enabled=True,
        sim_account_whitelist=(),
    )
    if mod_ok is not False or mod_reason != SIM_WHITELIST_EMPTY:
        _fail(f"modify empty whitelist {mod_ok} {mod_reason}")
    payload = s1_reject_event_data(
        event="s1.sim_whitelist.reject",
        reason=SIM_WHITELIST_EMPTY,
        agent_id="agent-x",
        mode="sim",
        account="Sim101",
    )
    parsed = ConstitutionViolation.model_validate(payload)
    if parsed.principle_name != SIM_WHITELIST_EMPTY or parsed.severity != "error":
        _fail(f"constitution equivalent {parsed}")

    handler = _MemLog()
    sim_log = logging.getLogger("lumina.risk.sim_account_guard")
    sim_log.addHandler(handler)
    sim_log.setLevel(logging.ERROR)
    try:
        log_sim_reject(reason=SIM_WHITELIST_EMPTY, account="Sim101", mode="sim", agent_id="agent-x")
        if not any(item.get("agent_id") == "agent-x" for item in handler.events):
            _fail("agent_id must survive reject log")
        lock = _fresh(("Sim101",))
        handler.events.clear()
        lock.effective(("Sim101", "Sim202"))
        extras = [
            item.get("extra")
            for item in handler.events
            if item.get("event") == "s1.sim_whitelist.widen_refused"
        ]
        if extras != [["Sim202"]]:
            _fail(f"widen_refused extra {extras}")
        handler.events.clear()
        lock.effective(("Sim101",))
        if any(item.get("event") == "s1.sim_whitelist.widen_refused" for item in handler.events):
            _fail("same-set request must not log extras")
    finally:
        sim_log.removeHandler(handler)

    if connected_account_from_engine(SimpleNamespace(nt_connection=SimpleNamespace(account_name="Sim101"))) != "Sim101":
        _fail("nt_connection account")
    if connected_account_from_engine(SimpleNamespace(connection=SimpleNamespace(account_name="Sim202"))) != "Sim202":
        _fail("connection account")

    reset_live_release_nonces_for_tests()
    if _consume_nonce("short") is not False:
        _fail("short nonce consume")
    if _consume_nonce("long-enough-nonce1") is not True:
        _fail("first long nonce")
    if _consume_nonce("long-enough-nonce1") is not False:
        _fail("replay consume")
    if _parse_utc("") is not None:
        _fail("empty timestamp")
    if _parse_utc("not-a-timestamp") is not None:
        _fail("invalid timestamp")
    if _parse_utc(datetime(2026, 10, 29, 0, 0)) is not None:
        _fail("naive datetime")
    aware = datetime(2026, 10, 29, 0, 0, tzinfo=timezone.utc)
    parsed_aware = _parse_utc(aware)
    if parsed_aware is None or parsed_aware.tzinfo is None:
        _fail("aware datetime")

    os.environ[SECRET_ENV] = TEST_SECRET
    reset_live_release_nonces_for_tests()
    naive_now_rec = signed_live_release(now=FROZEN_NOW, nonce="n-kill-naive-now-16xx")
    naive_now_ok, naive_now_reason = verify_live_release(
        naive_now_rec, now=datetime(2026, 10, 29, 12, 0)
    )
    if naive_now_ok is not False or naive_now_reason != LIVE_RELEASE_TIMESTAMP_NOT_UTC:
        _fail(f"naive now {naive_now_ok} {naive_now_reason}")
    str_now_ok, str_now_reason = verify_live_release(
        naive_now_rec, now="2026-10-29T12:00:00+00:00"
    )
    if str_now_ok is not False or str_now_reason != LIVE_RELEASE_TIMESTAMP_NOT_UTC:
        _fail(f"string now {str_now_ok} {str_now_reason}")
    str_enabled = signed_live_release(enabled="true", nonce="n-kill-str-true-16xxx")
    str_ok, str_reason = verify_live_release(str_enabled, now=FROZEN_NOW)
    if str_ok is not False or str_reason != LIVE_RELEASE_DISABLED:
        _fail(f"string true must not enable {str_ok} {str_reason}")
    plus = signed_live_release(
        now=FROZEN_NOW,
        approved_at_utc="2026-10-29T12:00:00+00:00",
        expires_at_utc="2026-10-30T12:00:00+00:00",
        nonce="n-kill-plus00-16xxxxx",
    )
    plus_ok, plus_reason = verify_live_release(plus, now=FROZEN_NOW)
    if plus_ok is not True:
        _fail(f"+00:00 timestamp {plus_ok} {plus_reason}")
    empty_ts = signed_live_release(approved_at_utc="", nonce="n-kill-empty-ts-16xxxx")
    empty_ok, empty_reason = verify_live_release(empty_ts, now=FROZEN_NOW)
    if empty_ok is not False or empty_reason != LIVE_RELEASE_TIMESTAMP_NOT_UTC:
        _fail(f"empty ts {empty_ok} {empty_reason}")
    bad_ts = signed_live_release(approved_at_utc="%%%not-iso%%%", nonce="n-kill-bad-ts-16xxxxx")
    bad_ok, bad_reason = verify_live_release(bad_ts, now=FROZEN_NOW)
    if bad_ok is not False or bad_reason != LIVE_RELEASE_TIMESTAMP_NOT_UTC:
        _fail(f"bad ts {bad_ok} {bad_reason}")
    missing_purpose = signed_live_release(purpose="", nonce="n-kill-no-purpose-16xx")
    mp_ok, mp_reason = verify_live_release(missing_purpose, now=FROZEN_NOW)
    if mp_ok is not False or mp_reason != LIVE_RELEASE_PURPOSE_INVALID:
        _fail(f"empty purpose {mp_ok} {mp_reason}")

    widen_body = {
        "adr_path": "docs/adr/0061-sim-whitelist-and-live-release.md",
        "adr_sha256": "a" * 64,
        "approved_at_utc": "2026-10-29T00:00:00Z",
        "approved_by": "steve.operator",
        "enabled": True,
        "expires_at_utc": "2026-10-30T00:00:00Z",
        "nonce": "n-kill-widen-can-16xxx",
        "purpose": PURPOSE_WHITELIST_WIDEN,
        "schema_version": SCHEMA_VERSION,
    }
    got_widen = canonical_live_release_payload(widen_body)
    if b'"purpose":"sim_whitelist_widen"' not in got_widen:
        _fail(f"canonical purpose {got_widen!r}")
    if not got_widen.startswith(b'{"adr_path":'):
        _fail(f"canonical must be sort_keys ordered {got_widen!r}")
    unsorted_widen = (
        b'{"enabled":true,"nonce":"n-kill-widen-can-16xxx","purpose":"sim_whitelist_widen"'
    )
    if got_widen.startswith(unsorted_widen):
        _fail("canonical followed insertion order; sort_keys is not binding")
    empty_schema = dict(widen_body)
    empty_schema["schema_version"] = ""
    empty_schema["purpose"] = PURPOSE_LIVE
    got_schema = canonical_live_release_payload(empty_schema)
    if b'"schema_version":""' not in got_schema:
        _fail(f"canonical empty schema {got_schema!r}")

    orig_admit = s1_steps.admit_live_orders
    s1_steps.admit_live_orders = lambda *_a, **_k: (True, LIVE_RELEASE_HMAC_OK)
    try:
        engine = SimpleNamespace(config=SimpleNamespace(live_release_payload={"enabled": True}))
        lr_ctx = AdmissionContext(
            engine=engine,
            mode="real",
            symbol="MES",
            regime="NEUTRAL",
            proposed_risk=1.0,
            metadata={"live_release": {"enabled": True}},
            step_handlers={ADMISSION_STEP_LIVE_RELEASE: make_live_release_step(SimpleNamespace(engine=engine))},
        )
        allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_LIVE_RELEASE,)).run(lr_ctx)
        if allowed is not False or reason != LIVE_ACCOUNT_PATH_CLOSED_S1:
            _fail(f"forced hmac_ok must still close {allowed} {reason}")
    finally:
        s1_steps.admit_live_orders = orig_admit

    os.environ[SECRET_ENV] = TEST_SECRET
    reset_live_release_nonces_for_tests()
    good = signed_live_release(nonce="n-kill-meta-good-16xxx")
    live_engine = SimpleNamespace(config=SimpleNamespace(live_release_payload=good))
    disabled = signed_live_release(enabled=False, nonce="n-kill-meta-dis-16xxxx")
    meta_ctx = AdmissionContext(
        engine=live_engine,
        mode="real",
        symbol="MES",
        regime="NEUTRAL",
        proposed_risk=1.0,
        metadata={"live_release": disabled},
        step_handlers={ADMISSION_STEP_LIVE_RELEASE: make_live_release_step(SimpleNamespace(engine=live_engine))},
    )
    allowed, reason, _trace = AdmissionChain(steps=(ADMISSION_STEP_LIVE_RELEASE,)).run(meta_ctx)
    if allowed is not False or reason != LIVE_RELEASE_DISABLED:
        _fail(f"metadata must win {allowed} {reason}")


def run() -> None:
    os.environ[SECRET_ENV] = TEST_SECRET
    reset_live_release_nonces_for_tests()
    _whitelist_battery()
    _live_battery()
    _admission_battery()
    _s0_and_policy_battery()
    _gap_battery()
