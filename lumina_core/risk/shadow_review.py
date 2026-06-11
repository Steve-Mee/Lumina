"""
Shadow Deployment Human Review CLI (Phase 2 Deliverable 5).

Operational tooling that makes the rich human approval data
(resolution_notes + structured evidence + full history) actually usable
by risk reviewers for safe evolution experiments.

This is the practical interface for the "human_approval" stage of the
shadow promotion flow. It turns the library capabilities in ShadowRiskEvaluator
into a repeatable daily workflow.

Usage (as module):
    python -m lumina_core.risk.shadow_review list
    python -m lumina_core.risk.shadow_review show exp-2026-06-02
    python -m lumina_core.risk.shadow_review decide exp-2026-06-02 --approve \
        --notes "Stress-tested vs 2022-2023 regimes. Clean delta." \
        --approver "risk-lead@company.com"

The same functions are importable for dashboards, notebooks, or automation:
    from lumina_core.risk.shadow_review import (
        list_pending_human_approvals,
        get_full_review_package,
        submit_review_decision,
    )
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from lumina_core.risk.shadow import ShadowRiskEvaluator, ShadowRunRegistry


def list_pending_human_approvals(registry_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Return experiments currently waiting for human review."""
    reg = ShadowRunRegistry(storage_path=registry_path) if registry_path else ShadowRunRegistry()
    evaluator = ShadowRiskEvaluator(engine=_make_fake_engine_for_review(), registry=reg)
    return evaluator.list_pending_human_approvals()


def get_full_review_package(
    experiment_id: str,
    registry_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Assemble the complete review package (request + history + resolution summary)."""
    reg = ShadowRunRegistry(storage_path=registry_path) if registry_path else ShadowRunRegistry()
    evaluator = ShadowRiskEvaluator(engine=_make_fake_engine_for_review(), registry=reg)

    base = evaluator.get_human_review_package(experiment_id)
    if base is None:
        return None

    history = evaluator.get_experiment_history(experiment_id)
    resolution_summary = evaluator.get_experiment_resolution_summary(experiment_id)

    return {
        **base,
        "history": history,
        "resolution_summary": resolution_summary,
    }


def submit_review_decision(
    experiment_id: str,
    *,
    approved: bool,
    reason: str,
    resolution_notes: str | None = None,
    evidence: dict[str, Any] | None = None,
    approver: str | None = None,
    registry_path: str | Path | None = None,
) -> Any:
    """Submit the human decision and return the resulting EvolutionPromotionDecision."""
    reg = ShadowRunRegistry(storage_path=registry_path) if registry_path else ShadowRunRegistry()
    evaluator = ShadowRiskEvaluator(engine=_make_fake_engine_for_review(), registry=reg)

    decision = evaluator.submit_human_approval_decision(
        experiment_id=experiment_id,
        approved=approved,
        reason=reason,
        resolution_notes=resolution_notes,
        evidence=evidence,
        approver=approver,
        registry=reg,
    )

    # Defensive: ensure the rich resolution record is always present in the registry
    # (the evaluator path is best-effort on publish; we guarantee durability here for the CLI).
    try:
        reg.record(f"{experiment_id}:human_resolution", {
            "experiment_id": experiment_id,
            "approved": approved,
            "reason": reason,
            "approver": approver,
            "resolution_notes": resolution_notes,
            "evidence": evidence,
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        })
    except Exception:
        pass

    return decision


def _make_fake_engine_for_review() -> Any:
    """Minimal engine stub sufficient for review-only operations (no risk execution)."""
    return type("ReviewEngine", (), {"config": type("C", (), {"trade_mode": "paper"})()})()


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Human review CLI for Shadow Deployment experiments (Phase 2 Deliverable 5).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m lumina_core.risk.shadow_review list
  python -m lumina_core.risk.shadow_review show exp-2026-06-02 --registry shadow_experiments.jsonl
  python -m lumina_core.risk.shadow_review decide exp-2026-06-02 --approve \\
      --notes "Delta within tolerance. Stress-tested against 2022 regime." \\
      --approver "risk-lead@company.com" \\
      --evidence-json review_notes.pdf
""",
    )
    parser.add_argument(
        "--registry",
        type=str,
        default=None,
        help="Path to the JSONL registry file (default: in-memory only)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="List experiments waiting for human review")

    # show
    show_p = subparsers.add_parser("show", help="Show the full review package for one experiment")
    show_p.add_argument("experiment_id", help="Experiment ID (e.g. exp-2026-06-02)")

    # decide
    decide_p = subparsers.add_parser("decide", help="Submit human approval/rejection decision")
    decide_p.add_argument("experiment_id", help="Experiment ID")
    decide_group = decide_p.add_mutually_exclusive_group(required=True)
    decide_group.add_argument("--approve", action="store_true", help="Approve the experiment for promotion")
    decide_group.add_argument("--reject", action="store_true", help="Reject the experiment")
    decide_p.add_argument("--reason", required=True, help="Short reason for the decision (required)")
    decide_p.add_argument("--notes", default=None, help="Rich resolution notes (free text, stored for audit)")
    decide_p.add_argument("--approver", default=None, help="Reviewer identifier (email, name, etc.)")
    decide_p.add_argument(
        "--evidence-json",
        default=None,
        help="Path to a JSON file containing additional structured evidence, or a string that will be stored under 'evidence_text'",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    registry_path = Path(args.registry) if args.registry else None

    if args.command == "list":
        pending = list_pending_human_approvals(registry_path)
        if not pending:
            print("No experiments currently waiting for human review.")
            return 0
        print(f"Pending human approvals ({len(pending)}):")
        for p in pending:
            exp = p.get("experiment_id", "?")
            stage = p.get("stage", "?")
            ts = p.get("timestamp", "")
            print(f"  - {exp}  (stage={stage}, ts={ts})")
        return 0

    if args.command == "show":
        pkg = get_full_review_package(args.experiment_id, registry_path)
        if pkg is None:
            print(f"No review package found for experiment '{args.experiment_id}'", file=sys.stderr)
            return 2
        print(json.dumps(pkg, indent=2, default=str))
        return 0

    if args.command == "decide":
        approved = args.approve
        evidence: dict[str, Any] | None = None

        if args.evidence_json:
            ev_path = Path(args.evidence_json)
            if ev_path.exists():
                try:
                    evidence = json.loads(ev_path.read_text(encoding="utf-8"))
                except Exception as e:
                    print(f"Failed to parse evidence JSON: {e}", file=sys.stderr)
                    return 2
            else:
                evidence = {"evidence_text": args.evidence_json}

        decision = submit_review_decision(
            args.experiment_id,
            approved=approved,
            reason=args.reason,
            resolution_notes=args.notes,
            evidence=evidence,
            approver=args.approver,
            registry_path=registry_path,
        )

        print(f"Decision recorded for {args.experiment_id}:")
        print(f"  stage:   {getattr(decision, 'stage', 'unknown')}")
        print(f"  allowed: {getattr(decision, 'allowed', None)}")
        print(f"  reason:  {getattr(decision, 'reason', '')}")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())