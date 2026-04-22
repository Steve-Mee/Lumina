from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Headless/CI: geen tk startdialoog (parallel realities + OHLC/PPO-stress; lumina_runtime zonder argv).
# Sessie: state/parallel_realities_session.json, state/bot_stress_choices.json.
# Zie parallel_reality_config.py en bot_stress_choices.py
os.environ.setdefault("LUMINA_SKIP_STARTUP_DIALOG", "1")

# Ensure the repository root is always importable in CI/Linux collection runs.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(autouse=True)
def _unit_tests_allow_synthetic_rl_fallback(monkeypatch):
    """Production config sets require_real_simulator_data=true; unit tests use stubs without MarketDataService."""
    from lumina_core.config_loader import ConfigLoader

    orig = ConfigLoader.section.__func__

    @classmethod
    def _section(cls, *keys: str, default=None):
        result = orig(cls, *keys, default=default)
        if keys == ("evolution", "neuroevolution"):
            merged = dict(result) if isinstance(result, dict) else {}
            merged.setdefault("fetch_days_back", 90)
            merged.setdefault("fetch_limit", 20000)
            merged.setdefault("max_bars_in_report", 12000)
            merged["require_real_simulator_data"] = False
            return merged
        return result

    monkeypatch.setattr(ConfigLoader, "section", _section)


def pytest_runtest_setup(item):
    """Apply timeout overrides based on test markers."""
    # Disable timeout for subprocess-heavy safety_gate tests
    if item.get_closest_marker("safety_gate"):
        if not item.config.pluginmanager.hasplugin("timeout"):
            return
        item.pytestmark = item.pytestmark if hasattr(item, "pytestmark") else []
        if not isinstance(item.pytestmark, list):
            item.pytestmark = [item.pytestmark]
        # Remove any existing timeout marker and add a new one with 0 (no timeout)
        import pytest

        item.pytestmark = [m for m in item.pytestmark if m.name != "timeout"]
        item.pytestmark.append(pytest.mark.timeout(0))
