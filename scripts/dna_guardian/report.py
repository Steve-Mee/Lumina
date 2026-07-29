"""DNA Guardian — structured report generation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aperture_integrity import calculate_aperture_integrity
from health_history import (
    detect_per_file_degradation,
    get_longer_trend_summary,
    get_previous_health_score,
    get_short_trend_line,
    update_health_history,
)
from health_export import generate_recommendation
from structure import PROJECT_ROOT
from truth_density import calculate_dna_health_score, calculate_truth_density

def generate_report(structure_results: list[dict], all_ok: bool) -> dict[str, Any]:
    """Generate a structured report (v0.5.0 with DNA Health Score)."""
    timestamp = datetime.now(timezone.utc).isoformat()

    # Run Truth Density on a few key files
    key_files = [
        "core/constitution.md",
        "operating-system/self-improvement-protocol.md",
        "operating-system/truth-metrics.md",
        "current-reality/evolutionary-debt.md",
    ]

    truth_density_results = {}
    for f in key_files:
        truth_density_results[f] = calculate_truth_density(f)

    avg_score = (
        sum(r["score"] for r in truth_density_results.values()) / len(truth_density_results)
        if truth_density_results else 0.0
    )

    health = calculate_dna_health_score(structure_results, truth_density_results)

    # Trend detection (new in v0.6.0)
    previous_score = get_previous_health_score()
    trend = None
    if previous_score is not None:
        delta = round(health["score"] - previous_score, 2)
        trend = {
            "previous_score": previous_score,
            "delta": delta,
            "direction": "up" if delta > 0.05 else ("down" if delta < -0.05 else "stable")
        }

    # Update health history and get short trend line (new in v0.11.0)
    # v0.13.0: also store per-file scores for degradation tracking
    history = update_health_history(health["score"], truth_density_results)
    short_trend = get_short_trend_line(history)
    longer_trend = get_longer_trend_summary(history)

    # New in v0.13.0: detect files that are structurally weak over time
    degradation_warnings = detect_per_file_degradation(history)

    recommendation = generate_recommendation({
        "truth_density": truth_density_results,
        "trend": trend,
        "overall_status": "PASS" if all_ok else "FAIL"
    })

    report = {
        "timestamp": timestamp,
        "dna_version": "2.0",
        "tool_version": "0.17.0-elon-aperture-phase0",
        "overall_status": "PASS" if all_ok else "FAIL",
        "dna_health_score": health,
        "trend": trend,
        "health_trend_line": short_trend,
        "longer_trend_summary": longer_trend,
        "degradation_warnings": degradation_warnings,
        "recommendation": recommendation,
        "structural_validation": structure_results,
        "truth_density": truth_density_results,
        "truth_density_summary": {
            "average_score": round(avg_score, 2),
            "files_scored": len(truth_density_results),
        },
        "summary": {
            "total_checks": len(structure_results),
            "passed": sum(1 for r in structure_results if r["exists"]),
            "failed": sum(1 for r in structure_results if not r["exists"]),
        },
        # Phase 0 Elon aperture track (additive, never breaks existing consumers)
        "aperture_integrity": calculate_aperture_integrity(),
    }

    # Phase 3 D5: constitution invariant + forbidden-pattern scan (fail-hard via main exit)
    try:
        from capital_aperture_scan import run_d5_capital_aperture_checks

        report["d5_capital_aperture"] = run_d5_capital_aperture_checks(PROJECT_ROOT)
    except Exception as e:
        report["d5_capital_aperture"] = {
            "ok": False,
            "alignment": {"ok": False, "issues": [f"d5 check import/run failed: {e}"]},
            "scan": {"ok": False, "violations": [], "scanned_files": 0},
        }

    return report

