"""
Shadow Deployment End-to-End Production Demo
============================================

This script demonstrates the complete recommended production usage pattern
for the Shadow Deployment capability (Phase 2 Deliverable 5 of the 2026-05-31
capital aperture hardening plan).

It uses the absolute easiest durable pattern:
- `ShadowRiskEvaluator.with_persistent_registry(...)`

Run this script as a reference or living documentation for actual
evolution experiment teams.

Usage:
    python examples/shadow_deployment_demo.py
"""

from pathlib import Path
from datetime import datetime, timezone

# In a real environment these would come from the actual engine
class FakeEngine:
    def __init__(self):
        self.config = type("Config", (), {"trade_mode": "paper"})()

    class valuation_engine:
        @staticmethod
        def point_value_for(x):
            return 1.0


def main():
    from lumina_core.risk.shadow import (
        ShadowRiskEvaluator,
        ShadowRunRegistry,
    )

    print("=" * 70)
    print("SHADOW DEPLOYMENT - PRODUCTION DEMO")
    print("=" * 70)
    print()

    # ------------------------------------------------------------------
    # 1. One-liner durable evaluator (the new recommended pattern)
    # ------------------------------------------------------------------
    storage_path = Path("demo_shadow_experiments.jsonl")
    evaluator = ShadowRiskEvaluator.with_persistent_registry(
        engine=FakeEngine(),
        storage_path=storage_path,
    )

    print(f"[1] Created durable evaluator with persistence at: {storage_path}")
    print()

    # ------------------------------------------------------------------
    # 2. Run a clean "baseline" experiment (simulating current production logic)
    # ------------------------------------------------------------------
    print("[2] Running baseline experiment (current production logic)...")
    baseline = evaluator.execute_shadow_experiment(
        experiment_id="baseline-2026-06-01",
        dna_hash="risk-policy-v1.2.3",
        signal="BUY",
        confluence_score=0.88,
        proposed_risk=180.0,
        recent_fills=[{"fill_id": "f1", "qty": 2}],
    )

    print(f"    Baseline verdict: {baseline.shadow_result.verdict}")
    print(f"    Recommendation:   {baseline.recommendation}")
    print(f"    Promotion stage:  {baseline.promotion_decision.stage}")
    print()

    # ------------------------------------------------------------------
    # 3. Run a new experiment after a DNA change (the actual shadow test)
    # ------------------------------------------------------------------
    print("[3] Running new experiment (new DNA version under test)...")
    result = evaluator.execute_shadow_experiment(
        experiment_id="exp-2026-06-02",
        dna_hash="risk-policy-v1.2.4",   # new version being tested in shadow
        signal="BUY",
        confluence_score=0.87,
        proposed_risk=185.0,
        recent_fills=[{"fill_id": "f2", "qty": 2}],
        reference_experiment_id="baseline-2026-06-01",
    )

    print(f"    Verdict:         {result.shadow_result.verdict}")
    print(f"    Recommendation:  {result.recommendation}")
    print(f"    Promotion stage: {result.promotion_decision.stage}")
    print()

    # ------------------------------------------------------------------
    # 4. Human review side (simulated)
    # ------------------------------------------------------------------
    if result.human_approval_request:
        print("[4] Human review required.")
        package = evaluator.get_human_review_package(result.experiment_id)
        print(f"    Package prepared for reviewer:")
        print(f"    - Decision summary: {package['human_approval_request']['decision_summary']}")
        print()

        # Simulate human decision
        print("[5] Human submits decision...")
        final = evaluator.submit_human_approval_decision(
            experiment_id=result.experiment_id,
            approved=True,
            reason="Approved after review. Risk increase is acceptable given clean comparison.",
            approver="risk-lead@company.com",
        )
        print(f"    Final promotion decision stage: {final.stage}")
        print(f"    Allowed: {final.allowed}")
    else:
        print("[4] No human review required (promotion_gate or better).")
        print("[5] Promotion decision already emitted with correct stage.")

    print()
    print("=" * 70)
    print("DEMO COMPLETE")
    print(f"Persistence file: {storage_path} (contains full history)")
    print()
    print("For real human review workflows use the dedicated CLI:")
    print("    python -m lumina_core.risk.shadow_review list")
    print("    python -m lumina_core.risk.shadow_review show <experiment_id>")
    print("    python -m lumina_core.risk.shadow_review decide <id> --approve --notes \"...\" --evidence-json path")
    print("=" * 70)


if __name__ == "__main__":
    main()
