"""Attack tests for every S3 fail-closed path."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

from lumina_core.order_gatekeeper.ungated_place_block import (
    S0_PLACE_SOURCE_ALLOWLIST,
    UNGATED_PLACE_BLOCK_REASON,
    assert_validation_gate_or_block,
    freeze_is_armed,
)
from lumina_core.research_bridge.sim_gate import (
    RESEARCH_SIM_GATED,
    bind_sim_gate,
    evaluate,
)
from lumina_research.cycles.holdout import HOLDOUT_PIN_ISO, holdout_pin_is_closed
from lumina_research.validation.nt_tape import TapeRefused, closed_bars_from_rows, fixture_closed_mes_bars
from tests.research_bridge.s3_helpers import passing_context, survivor


@pytest.fixture(autouse=True)
def _unbind() -> None:
    bind_sim_gate(None)
    yield
    bind_sim_gate(None)


@pytest.mark.unit
@pytest.mark.safety_gate
def test_s0_allowlist_stays_empty_and_freeze_armed() -> None:
    assert S0_PLACE_SOURCE_ALLOWLIST == frozenset()
    assert freeze_is_armed() is True
    assert holdout_pin_is_closed() is True
    assert HOLDOUT_PIN_ISO == "2026-01-28T23:00:00Z"


@pytest.mark.unit
@pytest.mark.safety_gate
def test_yaml_boot_shadow_cannot_place() -> None:
    ok, reason = evaluate(passing_context(boot="off", yaml_now="sim"))
    assert ok is False
    assert reason == RESEARCH_SIM_GATED
    allowed, freeze = assert_validation_gate_or_block(
        "ninjatrader.broker.submit_order",
        order_side="BUY",
        source_agent="research_bridge",
        live_position_qty=0,
        order_qty=1,
    )
    assert allowed is False
    assert freeze == UNGATED_PLACE_BLOCK_REASON


@pytest.mark.unit
@pytest.mark.safety_gate
def test_live_release_real_mix_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LUMINA_LIVE_RELEASE_SECRET", "x" * 16)
    from lumina_core.risk.live_release import compute_live_release_mac

    record = {
        "schema_version": "live_release.v1",
        "enabled": True,
        "purpose": "live_enablement",
        "approved_by": "steve",
        "adr_path": "docs/adr/0061-sim-whitelist-and-live-release.md",
        "adr_sha256": "a" * 64,
        "approved_at_utc": "2026-10-29T00:00:00+00:00",
        "expires_at_utc": "2026-10-30T00:00:00+00:00",
        "nonce": "n" * 16,
    }
    record["mac"] = compute_live_release_mac(record, b"x" * 16)
    ok, reason = evaluate(passing_context(live_release=record))
    assert ok is False
    assert reason == RESEARCH_SIM_GATED


@pytest.mark.unit
@pytest.mark.safety_gate
def test_expected_horizon_zero_not_survivor() -> None:
    row = replace(survivor(tag="z", family="trend"), expected_horizon_bars=0)
    ok, reason = evaluate(passing_context(survivors=(row, survivor(tag="b", family="meanrev"))))
    assert ok is False


@pytest.mark.unit
@pytest.mark.safety_gate
def test_unknown_account_and_empty_whitelist() -> None:
    ok, reason = evaluate(passing_context(connected="LiveAcct", whitelist=("Sim101",)))
    assert ok is False
    ok, reason = evaluate(passing_context(whitelist=()))
    assert ok is False


@pytest.mark.unit
@pytest.mark.safety_gate
def test_far_unmeasured_and_above_floor() -> None:
    ok, reason = evaluate(passing_context(far=None))
    assert ok is False
    assert reason == "far_unmeasured"
    ok, reason = evaluate(passing_context(far=0.06))
    assert ok is False
    assert reason == "far_above_floor"


@pytest.mark.unit
@pytest.mark.safety_gate
def test_forming_bar_attack() -> None:
    now = datetime(2025, 12, 31, 21, 0, tzinfo=timezone.utc)
    rows = list(fixture_closed_mes_bars(now=now))
    rows[-1] = {**rows[-1], "timestamp": datetime(2026, 1, 1, tzinfo=timezone.utc)}
    with pytest.raises(TapeRefused):
        closed_bars_from_rows(rows, now=now, purpose="gate")


@pytest.mark.unit
@pytest.mark.safety_gate
def test_config_yaml_not_sim() -> None:
    text = Path("config.yaml").read_text(encoding="utf-8")
    assert "research_execution_mode: sim" not in text
    assert "research_execution_mode: shadow" in text
