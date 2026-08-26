"""base_v3 live scenario style for micro + escalation."""

from __future__ import annotations

from lumina_core.evolution.twin_escalation import build_escalation_question
from lumina_core.evolution.twin_micro_training import proposal_to_mc
from lumina_core.evolution.twin_question_style import (
    format_escalation_live_scenario,
    format_micro_live_scenario,
    standard_avm_choices,
)


def test_standard_avm_choices_have_plus_minus() -> None:
    for c in standard_avm_choices():
        assert "\n+ " in c.label
        assert "\n− " in c.label


def test_micro_scenario_has_live_structure() -> None:
    q = proposal_to_mc(
        "Shadow clean maar DD steeg.",
        "abc123deadbeef",
        conf=0.72,
        recommendation=True,
        risk_flags=["correlated_instruments"],
        source_hint="live high-stakes beslissing",
    )
    s = q.scenario
    assert "Live data:" in s
    assert "Termen:" in s
    assert "72%" in s or "conf" in s.lower()
    assert "correlated_instruments" in s
    assert "• " in s
    for c in q.choices:
        assert "\n+ " in c.label


def test_escalation_scenario_explains_doubt() -> None:
    q = build_escalation_question(
        dna_hash="esc_dna_hash_01",
        confidence=0.71,
        risk_flags=["overnight"],
        explanation="Regime entropy hoog",
        twin_recommendation=None,
        doubt_reasons=["low_conf", "novel_pattern"],
    )
    s = q.scenario
    assert "twijfel" in s.lower() or "onzeker" in s.lower()
    assert "Live data:" in s
    assert "Termen:" in s
    assert "71%" in s or "0.71" in s
    assert "lage zekerheid" in s.lower() or "low_conf" in s
    assert "overnight" in s
    assert len(q.choices) == 4
    assert all("\n+ " in c.label for c in q.choices)


def test_format_helpers_are_multiline() -> None:
    micro = format_micro_live_scenario(conf=0.5, dna_hash="x", summary="test")
    esc = format_escalation_live_scenario(conf=0.4, dna_hash="y", doubt_reasons=["low_conf"])
    assert micro.count("\n") >= 4
    assert esc.count("\n") >= 4
