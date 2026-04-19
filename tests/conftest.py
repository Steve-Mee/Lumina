from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repository root is always importable in CI/Linux collection runs.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def pytest_configure(config):
    """Configure pytest plugins based on markers."""
    # Allow safety_gate tests to run without timeout constraints
    # since they spawn long-running subprocess simulations
    if hasattr(config, "option") and hasattr(config.option, "timeout"):
        # Mark will be applied per-test via pytest_runtest_setup
        pass


def pytest_runtest_setup(item):
    """Apply timeout overrides based on test markers."""
    # Disable timeout for subprocess-heavy safety_gate tests
    if item.get_closest_marker("safety_gate"):
        item.pytestmark = item.pytestmark if hasattr(item, "pytestmark") else []
        if not isinstance(item.pytestmark, list):
            item.pytestmark = [item.pytestmark]
        # Remove any existing timeout marker and add a new one with 0 (no timeout)
        import pytest

        item.pytestmark = [m for m in item.pytestmark if m.name != "timeout"]
        item.pytestmark.append(pytest.mark.timeout(0))
