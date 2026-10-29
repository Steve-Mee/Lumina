"""D6: SignalIntent required fields; missing horizon refuses; oos_size is not a default."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from lumina_core.agent_orchestration.schemas_research import PromotionCandidate
from lumina_core.agent_orchestration.schemas_research_execution import SignalIntent
from lumina_core.research_bridge.horizon import HorizonRefused, require_expected_horizon_bars
from tests.research_bridge.helpers import make_runtime, sealed_candidate, unsigned_candidate_fields


@pytest.mark.unit
def test_signal_intent_requires_horizon_and_core_fields() -> None:
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
    intent = SignalIntent(
        strategy_id="hyp-s0",
        config_id="cfg-s0",
        trial_id=1,
        instrument="MES",
        direction="BUY",
        size=1.0,
        timestamp=now,
        expected_horizon=8,
        validation_mac="a" * 64,
        issue_mac="b" * 64,
    )
    assert intent.strategy_id == "hyp-s0"
    assert intent.direction == "BUY"
    assert intent.size == 1.0
    assert intent.timestamp == now
    assert intent.expected_horizon == 8
    with pytest.raises(ValidationError):
        SignalIntent(
            strategy_id="hyp-s0",
            config_id="cfg-s0",
            trial_id=1,
            instrument="MES",
            direction="BUY",
            size=1.0,
            timestamp=now,
            expected_horizon=0,
            validation_mac="a" * 64,
            issue_mac="b" * 64,
        )


@pytest.mark.unit
def test_oos_size_is_never_a_horizon_fallback() -> None:
    with pytest.raises(HorizonRefused):
        require_expected_horizon_bars(None, oos_size=30)
    with pytest.raises(HorizonRefused):
        require_expected_horizon_bars(0, oos_size=30)
    with pytest.raises(HorizonRefused):
        require_expected_horizon_bars(-1, oos_size=30)
    assert require_expected_horizon_bars(8, oos_size=30) == 8
    assert require_expected_horizon_bars(20, oos_size=30) == 20


@pytest.mark.unit
def test_missing_horizon_on_constructed_candidate_refuses_fill(tmp_path: Path) -> None:
    _bus, authority, runtime, alerts, observe = make_runtime(tmp_path, healthy=True)
    unsigned = unsigned_candidate_fields(expected_horizon_bars=0)
    mac = authority.seal_issue(unsigned)
    forged = PromotionCandidate.model_construct(**{**unsigned, "issue_mac": mac})
    intent = runtime.on_candidate(forged)
    assert intent is None
    assert runtime.issued_intents() == ()
    assert runtime.issued_fills() == ()
    assert observe.calls == []
    assert any("expected_horizon" in str(item["code"]) for item in alerts.records)
    jsonl = (tmp_path / "research_shadow.jsonl").read_text(encoding="utf-8")
    assert "hypothetical_fill" not in jsonl
    assert "expected_horizon_missing" in jsonl


@pytest.mark.unit
def test_logged_intent_has_required_fields(tmp_path: Path) -> None:
    _bus, authority, runtime, _alerts, _observe = make_runtime(tmp_path, healthy=True)
    intent = runtime.on_candidate(sealed_candidate(authority))
    assert intent is not None
    assert intent.strategy_id
    assert intent.direction in {"BUY", "SELL"}
    assert intent.size > 0
    assert intent.timestamp.tzinfo is not None
    assert intent.expected_horizon >= 1
    lines = (tmp_path / "research_shadow.jsonl").read_text(encoding="utf-8")
    assert "expected_horizon" in lines
    assert '"fill": "pending"' in lines or '"event": "signal_intent"' in lines
