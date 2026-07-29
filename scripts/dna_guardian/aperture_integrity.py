"""DNA Guardian — capital aperture integrity scoring."""

from __future__ import annotations

from typing import Any

def calculate_aperture_integrity() -> dict[str, Any]:
    """
    Calculates a simple Aperture Integrity Score based on the external aperture.yaml baseline.
    Returns a dict with score (0-10), counts, status, and active warning if applicable.
    This is the first forcing function that makes bypass erosion visible in every Guardian run.
    """
    try:
        # Safe import pattern matching the rest of the Guardian (handles running as script)
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent))
        from rules import get_aperture_baseline, get_aperture_scoring_params, load_aperture_rules

        baseline = get_aperture_baseline()
        scoring = get_aperture_scoring_params()
        rules = load_aperture_rules()
    except Exception:
        # Guardian must never break
        return {
            "score": 5.0,
            "fatal_count": 0,
            "high_count": 0,
            "status": "UNKNOWN",
            "warning": "Aperture rules could not be loaded — check project-dna/lumina/operating-system/rules/aperture.yaml",
        }

    fatal = int(baseline.get("fatal_count", 0))
    high = int(baseline.get("high_count", 0))
    medium = int(baseline.get("medium_count", 0))

    base = float(scoring.get("base_score", 10.0))
    penalty = (
        fatal * float(scoring.get("fatal_penalty_per_item", 2.0))
        + high * float(scoring.get("high_penalty_per_item", 0.8))
        + medium * float(scoring.get("medium_penalty_per_item", 0.3))
    )
    penalty = min(penalty, float(scoring.get("max_penalty", 8.0)))

    score = max(0.0, round(base - penalty, 2))

    # Phase 1.1 light mitigation: enforcement active reduces effective risk
    enforcement = rules.get("enforcement", {})
    if enforcement.get("active") and fatal > 0:
        mitigation_bonus = 3.0  # Enforcement makes the remaining count less dangerous
        score = min(10.0, round(score + mitigation_bonus, 2))

    if fatal > 0:
        status = "CRITICAL"
    elif fatal > int(rules.get("targets", {}).get("fatal_max_for_yellow", 1)):
        status = "RED"
    elif high > 0:
        status = "YELLOW"
    else:
        status = "GREEN"

    warning = rules.get("active_warning", "") if fatal > 0 else ""

    return {
        "score": score,
        "fatal_count": fatal,
        "high_count": high,
        "medium_count": medium,
        "total_tracked": int(baseline.get("total_tracked", fatal + high + medium)),
        "status": status,
        "warning": warning,
    }

