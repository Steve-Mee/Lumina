"""Global test configuration for the LUMINA test suite.

Key responsibilities:
  1. Session-scoped state isolation — redirects all state/ and logs/ writes
     to a temporary directory so tests cannot pollute the real repository state.
  2. Auto-marker assignment — classifies every test with a speed/scope marker
     (unit | integration | slow | nightly | e2e) based on file/name heuristics.
  3. Per-marker timeout overrides — tighter constraints enforce the contract.
  4. Shared fixtures — isolated AgentBlackboard, EvolutionOrchestrator stubs,
     config monkeypatching.

Design rule: no test file should need to import conftest directly. All shared
behaviour is delivered via fixtures and hooks.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: headless mode + repo root on sys.path
# ---------------------------------------------------------------------------

os.environ.setdefault("LUMINA_SKIP_STARTUP_DIALOG", "1")
# Disable dual thought-log writes during tests (avoid race conditions)
os.environ.setdefault("LUMINA_DUAL_THOUGHT_LOG", "false")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Session-scoped state isolation
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _session_state_isolation(tmp_path_factory: pytest.TempPathFactory) -> Generator[Path, None, None]:
    """Redirect ALL state/ and logs/ writes to a session-scoped temp directory.

    This fixture is autouse=True so it applies to every test without any
    explicit opt-in.  It sets LUMINA_STATE_DIR and LUMINA_LOGS_DIR environment
    variables before the first test runs and restores them at session end.

    AgentBlackboard, DNARegistry, VetoRegistry and similar modules read these
    env vars at construction time, so any instance created during tests will
    write to the isolated temp dir rather than the real repository state/.
    """
    base = tmp_path_factory.mktemp("lumina_session_state")
    state_dir = base / "state"
    logs_dir = base / "logs"
    state_dir.mkdir()
    logs_dir.mkdir()

    # Seed files that the engine expects to find on startup.
    for fname in (
        "agent_blackboard.jsonl",
        "thought_log.jsonl",
        "lumina_thought_log.jsonl",
        "evolution_log.jsonl",
        "dna_registry.jsonl",
        "veto_registry.jsonl",
    ):
        (state_dir / fname).write_text("")
    for fname in ("security_audit.jsonl",):
        (logs_dir / fname).write_text("")

    # Persist the SQLite files the registry uses.
    for fname in ("dna_registry.sqlite3", "veto_registry.db"):
        (state_dir / fname).touch()

    old_state = os.environ.get("LUMINA_STATE_DIR")
    old_logs = os.environ.get("LUMINA_LOGS_DIR")

    os.environ["LUMINA_STATE_DIR"] = str(state_dir)
    os.environ["LUMINA_LOGS_DIR"] = str(logs_dir)

    yield base

    # Restore original environment
    if old_state is None:
        os.environ.pop("LUMINA_STATE_DIR", None)
    else:
        os.environ["LUMINA_STATE_DIR"] = old_state
    if old_logs is None:
        os.environ.pop("LUMINA_LOGS_DIR", None)
    else:
        os.environ["LUMINA_LOGS_DIR"] = old_logs


@pytest.fixture(scope="session")
def session_state_dir(_session_state_isolation: Path) -> Path:
    """Return the session-scoped isolated state base directory."""
    return _session_state_isolation


@pytest.fixture()
def isolated_state(tmp_path: Path) -> Generator[Path, None, None]:
    """Function-scoped isolated state directory.

    Use this when a single test must not share state even within the session.
    Overrides LUMINA_STATE_DIR/LUMINA_LOGS_DIR for the duration of the test.
    """
    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir()
    logs_dir.mkdir()

    # Seed minimal required state files.
    for fname in ("agent_blackboard.jsonl", "evolution_log.jsonl", "dna_registry.jsonl"):
        (state_dir / fname).write_text("")
    (logs_dir / "security_audit.jsonl").write_text("")

    old_state = os.environ.get("LUMINA_STATE_DIR")
    old_logs = os.environ.get("LUMINA_LOGS_DIR")
    os.environ["LUMINA_STATE_DIR"] = str(state_dir)
    os.environ["LUMINA_LOGS_DIR"] = str(logs_dir)

    yield tmp_path

    if old_state is None:
        os.environ.pop("LUMINA_STATE_DIR", None)
    else:
        os.environ["LUMINA_STATE_DIR"] = old_state
    if old_logs is None:
        os.environ.pop("LUMINA_LOGS_DIR", None)
    else:
        os.environ["LUMINA_LOGS_DIR"] = old_logs


# ---------------------------------------------------------------------------
# Config loader: synthetic RL fallback (required for unit tests)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _unit_tests_allow_synthetic_rl_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production config sets require_real_simulator_data=true; tests use stubs."""
    from lumina_core.config_loader import ConfigLoader

    orig = ConfigLoader.section.__func__

    @classmethod  # type: ignore[misc]
    def _section(cls, *keys: str, default=None):  # type: ignore[override]
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


# ---------------------------------------------------------------------------
# Isolated AgentBlackboard fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def isolated_blackboard(tmp_path: Path):
    """Return an AgentBlackboard wired to a fresh, isolated temp directory.

    Use this fixture whenever a test needs a real blackboard but must not touch
    the repository state/ directory.
    """
    from lumina_core.engine.agent_blackboard import AgentBlackboard

    state_dir = tmp_path / "state"
    logs_dir = tmp_path / "logs"
    state_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)

    return AgentBlackboard(
        persistence_path=state_dir / "agent_blackboard.jsonl",
        audit_path=logs_dir / "security_audit.jsonl",
    )


# ---------------------------------------------------------------------------
# Isolated EvolutionOrchestrator stub fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def evolution_stub(tmp_path: Path):
    """Return a lightweight EvolutionOrchestrator with in-process mocks.

    This avoids touching vLLM, xAI, or real DNA registry state.
    """
    from lumina_core.evolution.dna_registry import DNARegistry, PolicyDNA
    from lumina_core.evolution.evolution_guard import EvolutionGuard

    state_dir = tmp_path / "state"
    state_dir.mkdir(exist_ok=True)
    registry = DNARegistry(
        jsonl_path=state_dir / "dna_registry.jsonl",
        sqlite_path=state_dir / "dna_registry.sqlite3",
    )
    guard = EvolutionGuard()

    # Seed one genesis DNA so the registry isn't empty.
    genesis = PolicyDNA.create(
        prompt_id="self_evolution_policy",
        version="active",
        content='{"mutation_depth": "conservative"}',
        fitness_score=1.0,
        generation=0,
        lineage_hash="GENESIS",
    )
    registry.register_dna(genesis)

    return {
        "registry": registry,
        "guard": guard,
        "state_dir": state_dir,
        "genesis_dna": genesis,
    }


# ---------------------------------------------------------------------------
# Minimal runtime context stub
# ---------------------------------------------------------------------------

@pytest.fixture()
def minimal_runtime_ctx():
    """Return a minimal MagicMock runtime context accepted by most engine methods."""
    ctx = MagicMock()
    ctx.engine.config.instrument = "MES"
    ctx.engine.config.trade_mode = "sim"
    ctx.get_current_dream_snapshot.return_value = {
        "signal": "HOLD",
        "confluence_score": 0.0,
        "stop": 0.0,
        "target": 0.0,
    }
    return ctx


# ---------------------------------------------------------------------------
# Marker registration (pytest_configure)
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers so --strict-markers does not reject them."""
    config.addinivalue_line("markers", "unit: fast isolated unit test (no I/O, <10 s)")
    config.addinivalue_line("markers", "integration: requires external services or real data")
    config.addinivalue_line("markers", "slow: takes >5 s (heavy sim, PPO training)")
    config.addinivalue_line("markers", "nightly: runs in nightly batch only")
    config.addinivalue_line("markers", "e2e: end-to-end test spanning multiple subsystems")


# ---------------------------------------------------------------------------
# Auto-marker assignment (pytest_collection_modifyitems)
# ---------------------------------------------------------------------------

# Filename patterns → marker.  Order matters: first match wins.
_SLOW_FILE_PATTERNS: frozenset[str] = frozenset({
    "test_multi_day_sim_runner",
    "test_stress_suite_runner",
    "test_self_evolution_auto_finetune",
    "test_evolution_orchestrator_bootstrap",
    "test_reality_ppo_aggregate",
    "test_reality_ohlc_stress",
    "test_ppo_trainer_weights",
    "test_ppo_risk_penalty",
    "test_rl_smoke",
    "test_rl_guardrails",
    "test_rl_environment_risk_costs",
    "test_headless_runtime",
    "test_launcher_headless_cli",
    "test_swarm_context_integration",
    "test_emotional_twin_and_swarm",
    "test_backtest_workers",
    "test_multi_day_sim_runner",
})

_NIGHTLY_FILE_PATTERNS: frozenset[str] = frozenset({
    "test_blackboard_integration_nightly",
    "test_sim_stability_checker",
    "test_phase1_validation",
})

_INTEGRATION_FILE_PATTERNS: frozenset[str] = frozenset({
    "test_broker_bridge",
    "test_xai_client",
    "test_chroma_community",
    "test_vector_api_community",
    "test_community_knowledge",
    "test_local_inference_engine",
    "test_simulator_data_support",
    "test_lumina_bible",
    "test_concurrent_state",
})

_E2E_FILE_PATTERNS: frozenset[str] = frozenset({
    "test_startup_integration",
    "test_dashboard_smoke",
    "test_dashboard_drawdown_runtime_e2e",
    "test_risk_transparency_e2e",
    "test_app_agents_orchestration",
    "test_trade_mode_golden_paths",
    "test_runtime_api_contract",
})

_SAFETY_GATE_FILE_PATTERNS: frozenset[str] = frozenset({
    "test_phase1_validation",
    "test_rollout_release_gate",
    "test_rollout_b_bootstrap",
    "test_rollout_b_automation",
    "test_rollout_b_schedule",
    "test_security",
    "test_order_path_regression",
    "test_trade_workers_gateway",
    "test_order_gatekeeper_contracts",
})

# Test name patterns (substring match) → slow
_SLOW_NAME_PATTERNS: tuple[str, ...] = (
    "sim_300",
    "nightly",
    "multi_gen",
    "stress_suite",
    "neuro",
    "ppo_train",
    "real_mes_data",
    "backtest_engine_with_real",
    "streamlit",
    "headless_boot",
)


def _classify_item(item: pytest.Item) -> str | None:
    """Return the auto-marker for *item*, or None if already marked."""
    # Skip items that already have an explicit speed marker.
    existing = {m.name for m in item.iter_markers()}
    speed_markers = {"unit", "integration", "slow", "nightly", "e2e"}
    if existing & speed_markers:
        return None

    fpath = Path(item.fspath).stem  # filename without .py

    if fpath in _NIGHTLY_FILE_PATTERNS:
        return "nightly"
    if fpath in _SLOW_FILE_PATTERNS:
        return "slow"
    if fpath in _INTEGRATION_FILE_PATTERNS:
        return "integration"
    if fpath in _E2E_FILE_PATTERNS:
        return "e2e"

    # Name-based slow detection
    node_name = item.name.lower()
    if any(pat in node_name for pat in _SLOW_NAME_PATTERNS):
        return "slow"

    # Chaos tests: treat as unit (they mock everything)
    if fpath.startswith("chaos") or "chaos" in existing:
        return "unit"

    # Safety gate tests: mark slow (they spawn subprocesses) unless small
    if fpath in _SAFETY_GATE_FILE_PATTERNS:
        return "slow"

    # Default: unit
    return "unit"


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Auto-assign speed/scope markers and enforce timeout overrides.

    This hook runs after all tests are collected.  It:
      1. Assigns a marker from the classification above.
      2. Sets a per-marker timeout via the pytest-timeout plugin.
    """
    has_timeout = config.pluginmanager.hasplugin("timeout")

    marker_timeouts: dict[str, int] = {
        "safety_gate": 0,   # 0 = no limit (subprocess-heavy)
        "nightly": 600,
        "slow": 120,
        "e2e": 90,
        "integration": 60,
        "unit": 15,
    }

    for item in items:
        # --- Auto-assign marker ---
        auto = _classify_item(item)
        if auto:
            item.add_marker(getattr(pytest.mark, auto), append=True)

        # --- Set timeout ---
        if not has_timeout:
            continue
        existing_markers = {m.name for m in item.iter_markers()}
        for marker_name, timeout_value in marker_timeouts.items():
            if marker_name in existing_markers:
                # Remove any previously-set timeout, then apply ours.
                item.own_markers = [
                    m for m in item.own_markers if m.name != "timeout"
                ]
                item.add_marker(pytest.mark.timeout(timeout_value), append=True)
                break


# ---------------------------------------------------------------------------
# Timeout override hook (belt-and-suspenders)
# ---------------------------------------------------------------------------

def pytest_runtest_setup(item: pytest.Item) -> None:
    """Apply timeout overrides from the marker — belt-and-suspenders guard."""
    if not item.config.pluginmanager.hasplugin("timeout"):
        return

    marker_timeouts: dict[str, int] = {
        "safety_gate": 0,
        "nightly": 600,
        "slow": 120,
        "e2e": 90,
        "integration": 60,
        "unit": 15,
    }

    for marker_name, timeout_val in marker_timeouts.items():
        if item.get_closest_marker(marker_name):
            item.own_markers = [m for m in item.own_markers if m.name != "timeout"]
            item.add_marker(pytest.mark.timeout(timeout_val), append=True)
            return
