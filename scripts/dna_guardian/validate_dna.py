#!/usr/bin/env python3
"""
DNA Guardian - Validation & Scoring Tool for Lumina Project DNA 2.0

v0.16.0-experimental: First narrow slice of Increment 4 — optional --llm-review (local Ollama only, weakest file, heuristic remains source of truth). Clearly labeled experimental.

Recommended usage for meta-improvements:
    python scripts/dna_guardian/validate_dna.py --create-entry

This generates a proper entry in evolution/log/ that follows the Recursive Self-Improvement Protocol.

Implementation is split across colocated modules; this file remains the CLI entrypoint and public import façade.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Ensure sibling modules are importable when invoked as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_context import update_agent_context
from aperture_integrity import calculate_aperture_integrity
from evolution_entry import create_evolution_entry
from health_export import (
    generate_health_summary,
    generate_recommendation,
    generate_structured_health,
    write_dna_health_latest,
)
from health_history import (
    HEALTH_HISTORY_FILE,
    MAX_HISTORY_ENTRIES,
    detect_per_file_degradation,
    get_longer_trend_summary,
    get_previous_health_score,
    get_short_trend_line,
    update_health_history,
)
from llm_review import run_llm_review_on_file
from report import generate_report
from report_markdown import print_markdown_report
from structure import (
    DNA_ROOT,
    PROJECT_ROOT,
    check_path_exists,
    validate_structure,
)
from truth_density import (
    POSITIVE_MARKERS,
    VAGUE_WORDS,
    calculate_dna_health_score,
    calculate_truth_density,
)

__all__ = [
    "PROJECT_ROOT",
    "DNA_ROOT",
    "HEALTH_HISTORY_FILE",
    "MAX_HISTORY_ENTRIES",
    "VAGUE_WORDS",
    "POSITIVE_MARKERS",
    "check_path_exists",
    "validate_structure",
    "calculate_truth_density",
    "calculate_dna_health_score",
    "get_previous_health_score",
    "update_health_history",
    "get_short_trend_line",
    "get_longer_trend_summary",
    "calculate_aperture_integrity",
    "detect_per_file_degradation",
    "generate_recommendation",
    "generate_health_summary",
    "generate_structured_health",
    "write_dna_health_latest",
    "run_llm_review_on_file",
    "update_agent_context",
    "generate_report",
    "print_markdown_report",
    "create_evolution_entry",
    "main",
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="DNA Guardian - Validator & Scorer for Lumina DNA 2.0 (v0.16.0-experimental — --llm-review available)"
    )
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON report")
    parser.add_argument("--report", action="store_true", help="Print human-readable Markdown report (default)")
    parser.add_argument(
        "--create-entry",
        action="store_true",
        help="Create a proper evolution log entry (recommended for meta-improvements)"
    )
    parser.add_argument(
        "--llm-review",
        action="store_true",
        help="EXPERIMENTAL: Run local LLM second-opinion review on the weakest file (requires Ollama). Never affects official Health Score."
    )
    parser.add_argument(
        "--d1-audits",
        dest="d1_audits",
        action="store_true",
        default=True,
        help="Phase 3 D1: Auto-generate and embed aperture audit artifacts (one human 20 min view) for recent decisions (default: on). Use --no-d1-audits to disable."
    )
    parser.add_argument(
        "--no-d1-audits",
        dest="d1_audits",
        action="store_false",
        help="Disable Phase 3 D1 aperture audit generation in this Guardian run."
    )
    parser.add_argument(
        "--strict-self-score",
        action="store_true",
        help="Phase 3 D6: fail (exit 1) if Guardian self-score is below 6.0 (aperture contract).",
    )
    args = parser.parse_args()

    structure_results, all_ok = validate_structure()
    report = generate_report(structure_results, all_ok)

    # Persist aperture panel + self-score for JSON export (--create-entry) and --json consumers
    try:
        from guardian_self_score import enrich_report_with_phase3_panel

        enrich_report_with_phase3_panel(report, repo_root=PROJECT_ROOT, d1_audits=args.d1_audits)
    except Exception as e:
        report["guardian_self_score"] = {
            "ok": False,
            "overall_score": 0.0,
            "status": "RED",
            "error": str(e),
        }

    d5 = report.get("d5_capital_aperture") or {}
    if not d5.get("ok", True):
        all_ok = False
        report["overall_status"] = "FAIL"

    gss = report.get("guardian_self_score") or {}
    if args.strict_self_score and float(gss.get("overall_score", 0)) < float(gss.get("fail_below", 6.0)):
        all_ok = False
        report["overall_status"] = "FAIL"

    # v0.16 experimental: optional narrow LLM review (only when explicitly requested)
    llm_review_result = None
    weakest_path = None
    if args.llm_review and args.create_entry:
        # Find the weakest file from the just-generated truth density results
        td = report.get("truth_density", {})
        if td:
            weakest = min(td.items(), key=lambda x: x[1]["score"])
            weakest_path, weakest_data = weakest

            context_summary = report.get("recommendation", "") + " | " + report.get("longer_trend_summary", "")
            llm_review_result = run_llm_review_on_file(weakest_path, weakest_data, context_summary)

            if llm_review_result:
                print(f"LLM review completed on weakest file: {weakest_path}")
            else:
                print("LLM review requested but unavailable (Ollama not running / timeout / error) — falling back to heuristic only.")

    # Attach to report so downstream functions can use it
    if llm_review_result:
        report["llm_review"] = {
            "enabled": True,
            "file": weakest_path,
            "result": llm_review_result,
        }
    elif args.llm_review:
        report["llm_review"] = {
            "enabled": True,
            "error": "LLM unavailable — pure heuristic used",
            "attempted_file": weakest_path,
        }

    if args.create_entry:
        entry_path = create_evolution_entry(report)
        print(f"Evolution log entry created: {entry_path}")

        # New in v0.9.0: also keep the compact agent context up to date
        context_path = update_agent_context(report)
        if "updated" in context_path.lower() or context_path.endswith(".md"):
            print(f"Agent context updated: {context_path}")

        # v0.15 continuation (Increment 5 slice 2): write standalone structured export
        latest_json_path = write_dna_health_latest(report)
        print(f"DNA health latest export written: {latest_json_path}")
    elif args.json:
        write_dna_health_latest(report)
        print(json.dumps(report, indent=2))
    else:
        print_markdown_report(report, d1_audits=args.d1_audits)
        try:
            write_dna_health_latest(report)
        except Exception:
            pass

    # Exit with error code if validation failed
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
