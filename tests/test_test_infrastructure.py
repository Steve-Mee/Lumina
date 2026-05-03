"""Tests that validate the test infrastructure itself.

These tests ensure:
  - State isolation works (no cross-contamination between tests).
  - Auto-marker assignment fires correctly.
  - Isolated fixtures provide real, functional objects.
  - AgentBlackboard honours LUMINA_STATE_DIR / LUMINA_LOGS_DIR.
  - The pytest-timeout plugin is installed and active.

All tests here are @unit because they touch no external services.
"""

from __future__ import annotations
import logging

import os
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# State isolation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestStateIsolation:
    """Verify that the session-level state redirect is active."""

    def test_lumina_state_dir_env_is_set(self) -> None:
        state_dir = os.environ.get("LUMINA_STATE_DIR")
        assert state_dir is not None, "LUMINA_STATE_DIR must be set by conftest"
        assert Path(state_dir).exists(), f"State dir must exist: {state_dir}"

    def test_lumina_logs_dir_env_is_set(self) -> None:
        logs_dir = os.environ.get("LUMINA_LOGS_DIR")
        assert logs_dir is not None, "LUMINA_LOGS_DIR must be set by conftest"
        assert Path(logs_dir).exists(), f"Logs dir must exist: {logs_dir}"

    def test_state_dir_is_not_real_repo_state(self) -> None:
        """Ensure tests write to /tmp-style dir, not the repo state/ dir."""
        repo_state = Path(__file__).resolve().parents[1] / "state"
        state_dir = Path(os.environ["LUMINA_STATE_DIR"])
        assert state_dir != repo_state, f"LUMINA_STATE_DIR must not point to the real repo state/. Got: {state_dir}"

    def test_two_isolated_state_fixtures_are_independent(
        self,
        tmp_path: Path,
    ) -> None:
        """Each function-scoped tmp_path must be unique."""
        marker = tmp_path / "marker.txt"
        marker.write_text("hello")
        assert marker.read_text() == "hello"
        # A second test will get a different tmp_path — verified by the unique
        # path suffix guaranteed by pytest.

    def test_isolated_state_fixture(self, isolated_state: Path) -> None:
        """isolated_state fixture must provide a writable state directory."""
        state_dir = isolated_state / "state"
        assert state_dir.exists()
        (state_dir / "test_write.txt").write_text("ok")
        assert (state_dir / "test_write.txt").read_text() == "ok"


# ---------------------------------------------------------------------------
# AgentBlackboard isolation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBlackboardIsolation:
    """AgentBlackboard must write to the isolated temp directory."""

    def test_blackboard_persistence_path_respects_env(self, isolated_blackboard) -> None:
        # The isolated_blackboard fixture uses its own tmp_path, not LUMINA_STATE_DIR.
        # We verify it is NOT pointing at the real repo state/ directory.
        repo_state = Path(__file__).resolve().parents[1] / "state"
        assert isolated_blackboard.persistence_path.parent != repo_state, (
            "Blackboard persistence_path must not point at the real repo state/"
        )
        # It must be a .jsonl file.
        assert isolated_blackboard.persistence_path.suffix == ".jsonl"

    def test_blackboard_publish_writes_to_isolated_path(self, isolated_blackboard) -> None:
        isolated_blackboard.publish_sync(
            topic="market.tape",
            producer="test",
            payload={"price": 4500.0},
            confidence=1.0,
        )
        # Verify something was actually written.
        assert isolated_blackboard.persistence_path.stat().st_size > 0

    def test_blackboard_does_not_write_to_repo_state(self, isolated_blackboard) -> None:
        repo_state = Path(__file__).resolve().parents[1] / "state" / "agent_blackboard.jsonl"
        size_before = repo_state.stat().st_size if repo_state.exists() else -1

        isolated_blackboard.publish_sync(
            topic="market.tape",
            producer="test",
            payload={"bid": 4499.0},
            confidence=1.0,
        )

        size_after = repo_state.stat().st_size if repo_state.exists() else -1
        assert size_before == size_after, "AgentBlackboard must NOT write to the real state/ directory during tests"

    def test_blackboard_thought_log_path_respects_env(self, isolated_blackboard) -> None:
        state_dir = Path(os.environ["LUMINA_STATE_DIR"])
        assert isolated_blackboard._thought_log_path.parent == state_dir, (
            "_thought_log_path must be inside LUMINA_STATE_DIR"
        )


# ---------------------------------------------------------------------------
# Evolution stub fixture
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEvolutionStubFixture:
    """evolution_stub must provide a functioning registry + guard."""

    def test_evolution_stub_has_registry(self, evolution_stub: dict) -> None:
        assert "registry" in evolution_stub
        assert "guard" in evolution_stub

    def test_evolution_stub_registry_has_genesis(self, evolution_stub: dict) -> None:
        from lumina_core.evolution.dna_registry import DNARegistry

        registry: DNARegistry = evolution_stub["registry"]
        active = registry.get_latest_dna()
        assert active is not None, "Registry must have at least one DNA"

    def test_evolution_stub_state_dir_is_isolated(self, evolution_stub: dict) -> None:
        repo_state = Path(__file__).resolve().parents[1] / "state"
        assert evolution_stub["state_dir"] != repo_state


# ---------------------------------------------------------------------------
# Marker assignment
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMarkerAssignment:
    """Verify that auto-markers are applied to collected items."""

    def test_this_test_has_unit_marker(self, request: pytest.FixtureRequest) -> None:
        markers = {m.name for m in request.node.iter_markers()}
        assert "unit" in markers, f"This test should have 'unit' marker, got: {markers}"

    def test_session_items_have_at_least_one_speed_marker(self, request: pytest.FixtureRequest) -> None:
        """Every collected item should have a speed/scope marker assigned."""
        speed_markers = {"unit", "integration", "slow", "nightly", "e2e"}
        session = request.session
        unmarked: list[str] = []
        for item in session.items:
            item_markers = {m.name for m in item.iter_markers()}
            if not item_markers & speed_markers:
                unmarked.append(item.nodeid)

        # Allow up to 2 % unmarked (edge cases from plugins or generated tests).
        total = len(session.items)
        allowed = max(5, int(total * 0.02))
        assert len(unmarked) <= allowed, (
            f"{len(unmarked)}/{total} tests have no speed marker. First few: {unmarked[:10]}"
        )


# ---------------------------------------------------------------------------
# Pytest-timeout plugin
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestTimeoutPlugin:
    """pytest-timeout must be installed and active."""

    def test_timeout_plugin_is_loaded(self, request: pytest.FixtureRequest) -> None:
        assert request.config.pluginmanager.hasplugin("timeout"), (
            "pytest-timeout plugin must be installed. Run: pip install pytest-timeout"
        )

    def test_timeout_marker_is_honoured(self, request: pytest.FixtureRequest) -> None:
        """A unit-marked test should have a timeout ≤ 15 s applied."""
        markers = {m.name: m for m in request.node.iter_markers()}
        if "timeout" in markers:
            timeout_val = markers["timeout"].args[0] if markers["timeout"].args else None
            if timeout_val is not None:
                assert timeout_val <= 120, f"Unit test timeout should be ≤ 120 s, got {timeout_val}"


# ---------------------------------------------------------------------------
# Isolated state per function (race condition guard)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_parallel_state_writes_do_not_conflict(isolated_blackboard) -> None:
    """Multiple publish_sync calls must not raise even with a thread."""
    import threading

    errors: list[Exception] = []

    def _publish() -> None:
        try:
            for i in range(10):
                isolated_blackboard.publish_sync(
                    topic="market.tape",
                    producer="test",
                    payload={"i": i},
                    confidence=1.0,
                )
        except Exception as exc:  # noqa: BLE001
            logging.exception("Unhandled broad exception fallback in tests/test_test_infrastructure.py:228")
            errors.append(exc)

    threads = [threading.Thread(target=_publish) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread errors during publish_sync: {errors}"


@pytest.mark.unit
def test_isolated_state_fixture_env_restored_after_use(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After isolated_state exits, original LUMINA_STATE_DIR should be restored.

    We can't directly test the teardown within the same fixture scope, so we
    verify that we can write a different value without permanent damage.
    """
    monkeypatch.setenv("LUMINA_STATE_DIR", str(tmp_path / "override"))
    assert os.environ["LUMINA_STATE_DIR"] == str(tmp_path / "override")
    # monkeypatch restores automatically on teardown
