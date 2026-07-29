"""DNA Guardian — truth density heuristics and composite health score."""

from __future__ import annotations

from typing import Any

from structure import DNA_ROOT

try:
    from rules import get_vague_words, get_positive_markers
    VAGUE_WORDS = get_vague_words()
    POSITIVE_MARKERS = get_positive_markers()
except Exception:
    # Safe fallback during transition to external rules
    VAGUE_WORDS = [
        "should", "aims to", "as much as possible", "in the future",
        "we want", "we hope", "try to", "attempt to"
    ]
    POSITIVE_MARKERS = [
        "hypothesis", "falsifiable", "prediction", "measurable",
        "evidence", "score", "metric"
    ]


def calculate_truth_density(relative_path: str) -> dict[str, Any]:
    """
    Very basic Truth Density heuristic for a single file.
    Returns a dict with score (0-10) and findings.

    Scoring parameters are now loaded from external rules (v0.13.0).
    """
    full_path = DNA_ROOT / relative_path
    if not full_path.exists() or not full_path.is_file():
        return {"score": 0.0, "findings": ["File does not exist"]}

    try:
        content = full_path.read_text(encoding="utf-8").lower()
    except Exception:
        return {"score": 0.0, "findings": ["Could not read file"]}

    words = content.split()
    word_count = len(words)
    if word_count == 0:
        return {"score": 0.0, "findings": ["Empty file"]}

    vague_count = sum(1 for w in VAGUE_WORDS if w in content)
    positive_count = sum(1 for w in POSITIVE_MARKERS if w in content)

    # Load scoring parameters from external rules (with fallback)
    try:
        from rules import get_scoring_parameters
        params = get_scoring_parameters()
    except Exception:
        params = {
            "base_score": 7.0,
            "vague_penalty_per_occurrence": 0.4,
            "vague_density_multiplier": 1.2,
            "positive_reward_per_occurrence": 0.6,
            "max_vague_penalty": 4.0,
            "max_positive_reward": 2.5,
            "long_file_penalty_threshold": 1200,
            "long_file_penalty": 1.0,
        }

    # Base score
    score = params["base_score"]

    # Penalize high vague word density
    vague_density = vague_count / max(word_count / 100, 1)
    score -= min(vague_density * params["vague_density_multiplier"], params["max_vague_penalty"])

    # Reward presence of positive markers
    score += min(positive_count * params["positive_reward_per_occurrence"], params["max_positive_reward"])

    # Light penalty for very long files without structure
    if word_count > params["long_file_penalty_threshold"] and "hypothesis" not in content:
        score -= params["long_file_penalty"]

    score = max(0.0, min(10.0, round(score, 1)))

    findings = []
    if vague_count > 3:
        findings.append(f"Contains {vague_count} vague phrases")
    if positive_count >= 2:
        findings.append(f"Contains {positive_count} strong evidence markers")
    if not findings:
        findings.append("No major heuristic signals detected")

    return {
        "score": score,
        "findings": findings
    }


def calculate_dna_health_score(structure_results: list[dict], truth_density_results: dict) -> dict[str, Any]:
    """
    Calculates a composite DNA Health Score (0-10).
    This is a simple but meaningful first version.
    """
    total_checks = len(structure_results)
    passed_checks = sum(1 for r in structure_results if r["exists"])
    structural_rate = (passed_checks / total_checks) if total_checks > 0 else 0.0

    avg_td = (
        sum(r["score"] for r in truth_density_results.values()) / len(truth_density_results)
        if truth_density_results else 0.0
    )

    # Formula (transparent and tunable):
    # 50% Structural Health + 50% Average Truth Density
    health_score = (structural_rate * 5) + (avg_td * 0.5)
    health_score = max(0.0, min(10.0, round(health_score, 2)))

    return {
        "score": health_score,
        "components": {
            "structural_health": round(structural_rate * 10, 1),
            "truth_density_avg": round(avg_td, 2)
        }
    }

