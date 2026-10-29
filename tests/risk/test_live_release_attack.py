from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.code_evolution.operators import FORBIDDEN_PARAMETER_KEYS, validate_parameter_tweak
from lumina_core.code_evolution.proposal import FORBIDDEN_TARGET_PREFIXES
from lumina_core.order_gatekeeper.ungated_place_block import (
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
)
from lumina_core.risk.live_release import (
    LIVE_ACCOUNT_PATH_CLOSED_S1,
    LIVE_RELEASE_MAC_MISMATCH,
    LIVE_RELEASE_REQUIRED,
    LIVE_RELEASE_SECRET_MISSING,
    SECRET_ENV,
    admit_live_orders,
    verify_live_release,
)
from lumina_core.risk.sim_account_guard import SIM_ACCOUNT_NOT_WHITELISTED, admit_sim_account
from lumina_core.runtime_config_reloader import _immutable_field_changes
from tests.risk.s1_hmac import TEST_SECRET, signed_live_release


@pytest.mark.unit
@pytest.mark.safety_gate
def test_trade_mode_real_without_live_release_is_denied() -> None:
    from lumina_core.broker.ninjatrader.guards import check_account_match

    ok, reason = check_account_match(
        trade_mode="real",
        configured_account="LiveAcct",
        connected_account="LiveAcct",
        live_release=None,
    )
    assert ok is False
    assert reason == LIVE_RELEASE_REQUIRED


@pytest.mark.unit
@pytest.mark.safety_gate
def test_hot_reload_cannot_flip_live_release_enabled() -> None:
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
    assert "live_release" in changed
    assert "sim_account_whitelist" in changed
    assert "research_execution_mode" in changed


@pytest.mark.unit
def test_code_evolution_cannot_tweak_live_release_or_whitelist() -> None:
    for key in ("live_release", "sim_account_whitelist", "account_name", "mode", "trade_mode"):
        assert key in FORBIDDEN_PARAMETER_KEYS
        assert "forbidden_parameter_key" in validate_parameter_tweak(key, 1.0, 2.0)
    assert "lumina_core/risk/live_release" in FORBIDDEN_TARGET_PREFIXES
    assert "lumina_core/risk/sim_account_guard" in FORBIDDEN_TARGET_PREFIXES
    assert "config.yaml" in FORBIDDEN_TARGET_PREFIXES
    assert "fabric.json" in FORBIDDEN_TARGET_PREFIXES


@pytest.mark.unit
def test_wrong_key_and_forged_payload_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    good = signed_live_release()
    monkeypatch.setenv(SECRET_ENV, "other-secret-key-xx")
    ok, reason = verify_live_release(good)
    assert ok is False
    assert reason == LIVE_RELEASE_MAC_MISMATCH
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    tampered = dict(good)
    tampered["approved_by"] = "steve.operator.x"
    ok, reason = verify_live_release(tampered)
    assert ok is False
    assert reason == LIVE_RELEASE_MAC_MISMATCH


@pytest.mark.unit
@pytest.mark.safety_gate
def test_valid_live_release_does_not_lift_s0_freeze(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    allowed, reason = admit_live_orders(signed_live_release())
    assert allowed is False
    assert reason == LIVE_ACCOUNT_PATH_CLOSED_S1
    blocked, freeze_reason = assert_validation_gate_or_block(
        "supervisor_tick_exec.run_tick_exec",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
        source_agent="research_bridge",
    )
    assert blocked is False
    assert freeze_reason == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
def test_missing_secret_rejects_even_with_signed_looking_record(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SECRET_ENV, raising=False)
    ok, reason = admit_live_orders({"enabled": True, "mac": "a" * 64})
    assert ok is False
    assert reason == LIVE_RELEASE_SECRET_MISSING


@pytest.mark.unit
@pytest.mark.safety_gate
def test_monkeypatch_prefix_helper_does_not_admit_off_list_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("lumina_core.risk.sim_account_guard.is_paper_account_name", lambda _name: True)
    monkeypatch.setattr("lumina_core.broker.ninjatrader.account_names.is_local_sim_name", lambda _name: True)
    ok, reason = admit_sim_account("Sim999", ("Sim101",), mode="sim")
    assert ok is False
    assert reason == SIM_ACCOUNT_NOT_WHITELISTED
    live_ok, live_reason = admit_sim_account("LiveAcct", ("Sim101",), mode="sim")
    assert live_ok is False
    assert live_reason == SIM_ACCOUNT_NOT_WHITELISTED


@pytest.mark.unit
@pytest.mark.safety_gate
def test_checked_in_config_does_not_enable_live_release() -> None:
    text = Path("config.yaml").read_text(encoding="utf-8")
    assert "LUMINA_LIVE_RELEASE_SECRET" not in text
    assert "live_release_secret" not in text.lower()
    raw_enabled = False
    raw_mac = ""
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("live_release:"):
            in_block = True
            continue
        if in_block and stripped and not line.startswith(" ") and not line.startswith("\t"):
            break
        if in_block and stripped.startswith("enabled:"):
            raw_enabled = stripped.split(":", 1)[1].strip().lower() in {"true", "1", "yes"}
        if in_block and stripped.startswith("mac:"):
            raw_mac = stripped.split(":", 1)[1].strip().strip("\"'")
    assert raw_enabled is False
    assert raw_mac in {"", "''", '""'}


@pytest.mark.unit
def test_yaml_env_cannot_inject_whitelist_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NINJATRADER_SIM_WHITELIST", "Sim999,LiveAcct")
    monkeypatch.setenv("SIM_ACCOUNT_WHITELIST", "Sim999")
    from lumina_core.engine.engine_config import _yaml_sim_account_whitelist

    names = _yaml_sim_account_whitelist()
    assert "Sim999" not in names
    assert "LiveAcct" not in names
