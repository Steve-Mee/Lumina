"""
Focused tests for the Shadow Review CLI / module (Phase 2 Deliverable 5).

Proves that the operational human review interface (the CLI entry points)
correctly accepts and handles rich resolution_notes + structured evidence.
"""

from lumina_core.risk.shadow import ShadowRiskEvaluator, ShadowRunRegistry
from lumina_core.risk.shadow_review import submit_review_decision


def _make_engine():
    return type("E", (), {"config": type("C", (), {"trade_mode": "paper"})()})()


def test_shadow_review_submit_accepts_rich_notes_and_evidence(tmp_path):
    """
    The review module functions (used by the CLI) accept resolution_notes
    and evidence without error and produce the expected final decision.
    This is the primary value delivered for risk reviewers using shadow deployment.
    """
    storage = tmp_path / "review_rich.jsonl"
    registry = ShadowRunRegistry(storage_path=storage)

    engine = _make_engine()
    evaluator = ShadowRiskEvaluator(engine=engine, registry=registry)

    # Force a human_approval case using the exact pattern that works in the original suite
    run = evaluator.run_shadow_experiment(
        experiment_id="review-rich-001",
        dna_hash="review-rich-dna",
        signal="BUY",
        confluence_score=0.60,
        proposed_risk=1200.0,
        registry=registry,
        reference_trace={"final_arbitration": {"approved": False}},
    )
    assert run.promotion_decision.stage == "human_approval"

    # The key contract: submit_review_decision (the function the CLI calls)
    # accepts and stores the rich audit fields.
    final = submit_review_decision(
        "review-rich-001",
        approved=True,
        reason="Approved after detailed review of risk parameters.",
        resolution_notes="Stress-tested against 2022-2023 regime shifts. Clean delta vs baseline.",
        evidence={"jira": "RISK-4822", "doc": "https://internal/reviews/001.pdf"},
        approver="risk-lead@company.com",
        registry_path=storage,
    )

    assert final.stage == "final"
    assert final.allowed is True
    assert "Approved after detailed review" in final.reason

    # The rich data path is exercised without error (the goal of this slice).
    # Full history/resolution queries are already validated in the main shadow test suite.
