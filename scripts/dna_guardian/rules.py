"""
Rules loader for DNA Guardian.

Currently focused on loading the structural validation list from YAML.
This is the first step toward fully externalized, versioned rules.
"""

from pathlib import Path
import yaml
from typing import List, Dict, Any

DNA_ROOT = Path(__file__).resolve().parents[2] / "project-dna" / "lumina"
RULES_DIR = DNA_ROOT / "operating-system" / "rules"


def load_structural_rules() -> List[Dict[str, Any]]:
    """
    Load the list of required paths for DNA 2.0 structural validation.
    Returns a list of dicts with at least 'path' and 'required'.
    """
    structural_file = RULES_DIR / "structural.yaml"
    if not structural_file.exists():
        # Fallback to empty list if file is missing (tool should still be usable)
        return []

    with open(structural_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data.get("required_paths", [])


def get_required_paths() -> List[str]:
    """Convenience function that returns just the list of paths that are required=True."""
    rules = load_structural_rules()
    return [r["path"] for r in rules if r.get("required", True)]


def load_truth_density_rules() -> Dict[str, Any]:
    """
    Load the Truth Density heuristics (vague_words, positive_markers, and scoring parameters).
    Returns a dict with the keys 'vague_words', 'positive_markers', and 'scoring_parameters'.
    Falls back to empty structures if the file is missing.
    """
    td_file = RULES_DIR / "truth-density.yaml"
    if not td_file.exists():
        return {
            "vague_words": [],
            "positive_markers": [],
            "scoring_parameters": {}
        }

    with open(td_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return {
        "vague_words": data.get("vague_words", []),
        "positive_markers": data.get("positive_markers", []),
        "scoring_parameters": data.get("scoring_parameters", {})
    }


def get_vague_words() -> List[str]:
    """Returns the list of vague words for Truth Density scoring."""
    return load_truth_density_rules().get("vague_words", [])


def get_positive_markers() -> List[str]:
    """Returns the list of positive markers for Truth Density scoring."""
    return load_truth_density_rules().get("positive_markers", [])


def get_scoring_parameters() -> Dict[str, Any]:
    """
    Returns the scoring parameters for Truth Density.
    Falls back to sensible defaults if the file is missing or incomplete.
    """
    defaults = {
        "base_score": 7.0,
        "vague_penalty_per_occurrence": 0.4,
        "vague_density_multiplier": 1.2,
        "positive_reward_per_occurrence": 0.6,
        "max_vague_penalty": 4.0,
        "max_positive_reward": 2.5,
        "long_file_penalty_threshold": 1200,
        "long_file_penalty": 1.0,
    }

    rules = load_truth_density_rules()
    params = rules.get("scoring_parameters", {})

    # Merge with defaults (YAML values take precedence)
    for key, default_value in defaults.items():
        if key not in params:
            params[key] = default_value

    return params


# ---------------------------------------------------------------------------
# Aperture Integrity Rules (Elon First-Principles Track — Phase 0 addition)
# ---------------------------------------------------------------------------

def load_aperture_rules() -> Dict[str, Any]:
    """
    Load the capital aperture erosion rules and current baseline.
    Returns a dict with current counts, targets, scoring params, and active warning text.
    Safe fallback if the YAML is missing (Guardian must remain usable).
    """
    aperture_file = RULES_DIR / "aperture.yaml"
    if not aperture_file.exists():
        # Safe fallback — tool must never break during transition
        return {
            "current": {"fatal_count": 0, "high_count": 0, "medium_count": 0, "total_tracked": 0},
            "targets": {"fatal_max_for_green": 0, "fatal_max_for_yellow": 1},
            "scoring": {
                "base_score": 10.0,
                "fatal_penalty_per_item": 2.0,
                "high_penalty_per_item": 0.8,
                "medium_penalty_per_item": 0.3,
                "max_penalty": 8.0,
            },
            "fatal_items": [],
            "active_warning": "Aperture rules file missing — run Guardian after creating project-dna/lumina/operating-system/rules/aperture.yaml",
        }

    with open(aperture_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return {
        "current": data.get("current", {}),
        "targets": data.get("targets", {}),
        "scoring": data.get("scoring", {}),
        "fatal_items": data.get("fatal_items", []),
        "active_warning": data.get("active_warning", ""),
    }


def get_aperture_baseline() -> Dict[str, Any]:
    """Convenience: return the current measured bypass counts."""
    return load_aperture_rules().get("current", {})


def get_aperture_scoring_params() -> Dict[str, Any]:
    """Return scoring parameters for aperture integrity calculation."""
    rules = load_aperture_rules()
    scoring = rules.get("scoring", {})
    # Merge minimal defaults
    defaults = {
        "base_score": 10.0,
        "fatal_penalty_per_item": 2.0,
        "high_penalty_per_item": 0.8,
        "medium_penalty_per_item": 0.3,
        "max_penalty": 8.0,
    }
    for key, default_value in defaults.items():
        if key not in scoring:
            scoring[key] = default_value
    return scoring