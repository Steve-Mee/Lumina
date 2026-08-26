"""Base curriculum seed quality + axis coverage + teach-while-train clarity."""

from __future__ import annotations

from lumina_core.evolution.twin_base_curriculum import (
    BASE_CURRICULUM_VERSION,
    build_base_curriculum,
    curriculum_axes_coverage,
    question_count,
)
from lumina_core.evolution.twin_curriculum_types import CURRICULUM_VERSION, mc_answer_to_steve_fields


def test_curriculum_version_is_v4() -> None:
    assert CURRICULUM_VERSION == "base_v4"
    assert BASE_CURRICULUM_VERSION == "base_v4"


def test_curriculum_size_and_axes() -> None:
    qs = build_base_curriculum()
    assert 18 <= len(qs) <= 22
    assert question_count() == len(qs)
    cov = curriculum_axes_coverage(qs)
    assert cov.get("capital_preservation", 0) >= 3
    assert cov.get("mutation_aggression", 0) >= 3
    assert cov.get("regime_sensitivity", 0) >= 3
    assert cov.get("drawdown_recovery", 0) >= 2
    assert cov.get("approve_veto_modify", 0) >= 4
    assert cov.get("edge_case", 0) >= 3
    need_data = sum(
        1
        for q in qs
        if any(c.value_signal == "need_more_data" for c in q.choices)
    )
    assert need_data >= 4


def test_all_questions_app_only_and_answerable() -> None:
    for q in build_base_curriculum():
        assert q.channel_policy == "app_only"
        assert 3 <= len(q.choices) <= 4
        assert q.estimated_seconds <= 22
        choice = q.choices[0]
        vraag, antwoord, conf = mc_answer_to_steve_fields(q, choice_id=choice.id)
        assert choice.id in antwoord or "choice=" in antwoord
        assert 0.0 <= conf <= 1.0
        assert "scenario=" in vraag or q.scenario[:20] in vraag
        # RLHF tokens
        head = antwoord.split(":", 1)[0].strip().upper()
        assert head in {"APPROVE", "VETO", "MODIFY"}


def test_teach_while_train_clarity_signals() -> None:
    """Each scenario teaches: plain lead + parenthetical / example definition."""
    for q in build_base_curriculum():
        text = q.scenario
        first_line = text.split("\n", 1)[0].strip()
        # First line should not be pure code-speak (has spaces / Dutch words)
        assert " " in first_line
        assert not first_line.startswith("mutation_rate")
        assert not first_line.startswith("SIM-run:")
        # Teach signal: parentheses, equals, of/bijv/voorbeeld
        lower = text.lower()
        teach = (
            "(" in text
            or " = " in text
            or "bijv" in lower
            or "voorbeeld" in lower
            or "wat is" in lower
            or " = " in lower
        )
        assert teach, f"missing teach signal in {q.question_id}"
        # Choices: human-readable + explicit +/− consequences (base_v3)
        for c in q.choices:
            assert len(c.label) >= 8
            assert "\n+ " in c.label, f"missing + consequence in {q.question_id}/{c.id}"
            assert "\n− " in c.label or "\n- " in c.label, (
                f"missing − consequence in {q.question_id}/{c.id}"
            )
