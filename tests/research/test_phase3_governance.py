"""ADR + signed human review required for Risk Core / threshold mutations."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_research.evolution.governance import ReviewAuthority, ReviewError, is_human_reviewer, read_adr
from lumina_research.evolution.integrity import IntegrityError
from lumina_research.evolution.types import (
    RISK_CORE_TARGET,
    THRESHOLD_TARGET,
    evolution_rationale,
)
from tests.research.phase3_harness import dummy_genome, make_runtime, sign_protected, write_adr


@pytest.mark.unit
def test_threshold_mutation_without_adr_is_rejected(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    mutation = runtime.reflector.propose(
        kind="threshold_change",
        target=THRESHOLD_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("Attempt to weaken PBO hard reject without an ADR file xx"),
        seed=1,
        parent_config_id="parent",
        config_id="thr-no-adr",
    )
    n_before = runtime.registry.n_trials
    decision = runtime.governance.admit(mutation)
    assert decision.admitted is False
    assert decision.applied is False
    assert "adr_required" in decision.reasons
    assert runtime.registry.n_trials == n_before


@pytest.mark.unit
def test_threshold_mutation_with_adr_and_human_approve_is_not_applied(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    adr = write_adr(tmp_path / "adr", THRESHOLD_TARGET)
    config_id = "thr-with-review"
    review = sign_protected(
        runtime,
        adr_path=adr,
        config_id=config_id,
        kind="threshold_change",
        target=THRESHOLD_TARGET,
    )
    mutation = runtime.reflector.propose(
        kind="threshold_change",
        target=THRESHOLD_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("Documented threshold proposal that evolution must not apply"),
        seed=2,
        parent_config_id="parent",
        config_id=config_id,
        adr_path=adr.name,
        review=review,
    )
    decision = runtime.governance.admit(mutation)
    assert decision.admitted is False
    assert decision.recorded_for_human is True
    assert decision.applied is False
    assert "protected_recorded_not_applied" in decision.reasons
    with pytest.raises(IntegrityError, match="cannot write"):
        runtime.write_protected(Path(THRESHOLD_TARGET))
    runtime.assert_intact()


@pytest.mark.unit
def test_risk_core_mutation_without_review_is_rejected(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    adr = write_adr(tmp_path / "adr", RISK_CORE_TARGET)
    mutation = runtime.reflector.propose(
        kind="risk_core_change",
        target=RISK_CORE_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("Attempt to raise leverage cap after writing an ADR only"),
        seed=3,
        parent_config_id="parent",
        config_id="risk-no-review",
        adr_path=adr.name,
    )
    decision = runtime.governance.admit(mutation)
    assert decision.admitted is False
    assert "human_review_required" in decision.reasons


@pytest.mark.unit
def test_forged_review_and_agent_reviewer_are_rejected(tmp_path: Path) -> None:
    runtime = make_runtime(tmp_path)
    adr = write_adr(tmp_path / "adr", THRESHOLD_TARGET)
    with pytest.raises(ReviewError, match="human"):
        runtime.reviews.sign_review(
            reviewer_id="reflector_agent",
            adr_bytes=adr.read_bytes(),
            verdict="approve",
            config_id="x",
            kind="threshold_change",
            target=THRESHOLD_TARGET,
        )
    review = sign_protected(
        runtime,
        adr_path=adr,
        config_id="thr-forged",
        kind="threshold_change",
        target=THRESHOLD_TARGET,
    )
    other = ReviewAuthority(key=b"another-human-key-xx")
    with pytest.raises(ReviewError, match="too short"):
        ReviewAuthority(key=b"short")
    forged = review.model_copy(update={"signature": other.sign_review(
        reviewer_id="steve",
        adr_bytes=adr.read_bytes(),
        verdict="approve",
        config_id="thr-forged",
        kind="threshold_change",
        target=THRESHOLD_TARGET,
    ).signature})
    mutation = runtime.reflector.propose(
        kind="threshold_change",
        target=THRESHOLD_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("Forged HMAC review must not unlock thresholds at all"),
        seed=4,
        parent_config_id="parent",
        config_id="thr-forged",
        adr_path=adr.name,
        review=forged,
    )
    decision = runtime.governance.admit(mutation)
    assert decision.admitted is False
    assert "review_invalid" in decision.reasons
    reject_review = sign_protected(
        runtime,
        adr_path=adr,
        config_id="thr-reject",
        kind="threshold_change",
        target=THRESHOLD_TARGET,
        verdict="reject",
    )
    mutation2 = runtime.reflector.propose(
        kind="threshold_change",
        target=THRESHOLD_TARGET,
        genome=dummy_genome(),
        rationale=evolution_rationale("Human reject verdict must not admit a threshold change"),
        seed=5,
        parent_config_id="parent",
        config_id="thr-reject",
        adr_path=adr.name,
        review=reject_review,
    )
    decision2 = runtime.governance.admit(mutation2)
    assert "review_rejected" in decision2.reasons


@pytest.mark.unit
def test_adr_escape_and_incomplete_file_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "adr"
    root.mkdir()
    with pytest.raises(Exception, match="adr_path_escapes_root"):
        read_adr("../secret.md", adr_root=root, target=THRESHOLD_TARGET)
    bad = root / "0057-incomplete.md"
    bad.write_text("# no headings\n", encoding="utf-8")
    with pytest.raises(Exception, match="adr_incomplete"):
        read_adr(bad.name, adr_root=root, target=THRESHOLD_TARGET)
    missing_target = write_adr(root, "unrelated-surface", name="0058-wrong-target.md")
    with pytest.raises(Exception, match="adr_target_missing"):
        read_adr(missing_target.name, adr_root=root, target=THRESHOLD_TARGET)
    assert is_human_reviewer("steve") is True
    assert is_human_reviewer("governance_agent") is False
    assert is_human_reviewer("x") is False


@pytest.mark.unit
def test_subclassing_review_and_governance_is_forbidden(tmp_path: Path) -> None:
    with pytest.raises(TypeError):

        class _R(ReviewAuthority):  # type: ignore[misc]
            pass

    runtime = make_runtime(tmp_path)
    with pytest.raises(TypeError):

        class _G(type(runtime.governance)):  # type: ignore[misc]
            pass
    with pytest.raises(IntegrityError):
        runtime.governance.apply_protected(tmp_path / "gate_thresholds.toml")
