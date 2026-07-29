"""DNA Guardian — structural layout validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DNA_ROOT = PROJECT_ROOT / "project-dna" / "lumina"


def check_path_exists(relative_path: str) -> bool:
    """Check if a path exists relative to DNA_ROOT."""
    return (DNA_ROOT / relative_path).exists()


def validate_structure() -> list[dict[str, Any]]:
    """Perform structural validation of the DNA 2.0 layout.

    Tries to load the list from the external rules file.
    Falls back to a minimal hardcoded list if loading fails (for robustness during transition).
    """
    try:
        # Attempt to load from external rules (best effort)
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from rules import get_required_paths
        required_paths = get_required_paths()
        if not required_paths:
            raise RuntimeError("External rules returned empty list")
    except Exception:
        # Safe fallback during the transition to external rules
        required_paths = [
            "core/constitution.md",
            "core/north-star.md",
            "core/invariants.json",
            "operating-system/self-improvement-protocol.md",
            "operating-system/truth-metrics.md",
            "operating-system/decision-framework.md",
            "operating-system/anti-patterns.md",
            "operating-system/dna-validation-rules.md",
            "current-reality/architecture.md",
            "current-reality/evolutionary-debt.md",
            "interfaces/README.md",
            "interfaces/export/agent-context.md",
            "evolution-log.md",
            "evolution/log",
            "evolution/experiments",
        ]

    results = []
    all_ok = True

    for path in required_paths:
        exists = check_path_exists(path)
        if not exists:
            all_ok = False
        results.append({
            "path": path,
            "exists": exists,
            "status": "OK" if exists else "MISSING"
        })

    return results, all_ok

