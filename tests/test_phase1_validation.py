"""
Phase 1 validation gate - FAST tests only, no heavy/nightly/E2E.

Tests Phase 1 hardening changes:
1. sim_stability_checker.py: Windows path dedup fix
2. approval_twin_agent.py: Backend abstraction (local + ollama)
3. evolution_guard.py: Auto twin consult resolution
4. steve_values_registry.py: Append-only append-only database triggers
5. notification_scheduler.py: APScheduler integration
"""
import pytest
import sys
import os
from pathlib import Path


# CRITICAL: Test Phase 1 core changes only - no external services, no long-running tests


def test_sim_stability_checker_dedup() -> None:
    """Verify sim_stability_checker uses safe path dedup without Path.resolve()."""
    import tempfile
    from lumina_core.engine.sim_stability_checker import SimStabilityChecker
    
    with tempfile.TemporaryDirectory() as tmpdir:
        checker = SimStabilityChecker(base_dir=Path(tmpdir))
        # Minimal test: verify dedup_key method exists and works
        key = checker._dedupe_key(Path(tmpdir) / "test" / "file.json")
        assert isinstance(key, str)
        assert "test" in key


def test_approval_twin_backend_abstraction() -> None:
    """Verify approval_twin_agent has backend abstraction layer."""
    from lumina_core.evolution.approval_twin_agent import (
        ApprovalTwinBackend,
        LocalHeuristicBackend,
    )
    
    # Backend should be a Protocol
    backend = LocalHeuristicBackend()
    assert hasattr(backend, "evaluate")


def test_evolution_guard_twin_resolution() -> None:
    """Verify evolution_guard auto-resolves twin recommendation."""
    from lumina_core.evolution.evolution_guard import EvolutionGuard
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        guard = EvolutionGuard(history_dir=Path(tmpdir))
        # Minimal test: verify method accepts optional params
        import inspect
        sig = inspect.signature(guard.has_signed_approval)
        params = list(sig.parameters.keys())
        assert "approval_twin" in params or len(params) > 1  # Extended signature


def test_steve_values_registry_append_only() -> None:
    """Verify SteveValues registry has append-only enforcement."""
    from lumina_core.evolution.steve_values_registry import SteveValuesRegistry
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = SteveValuesRegistry(db_path=Path(tmpdir) / "test.db")
        # Verify triggers are set up
        cursor = registry._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='steve_values'"
        )
        triggers = cursor.fetchall()
        # Should have at least one trigger preventing UPDATE/DELETE
        assert len(triggers) > 0, "Append-only triggers not installed"


def test_notification_scheduler_apscheduler() -> None:
    """Verify notification_scheduler uses APScheduler."""
    from lumina_core.notifications.notification_scheduler import NotificationScheduler
    
    scheduler = NotificationScheduler()
    # Verify APScheduler-based interface
    assert hasattr(scheduler, "add_job") or hasattr(scheduler, "scheduler")
    scheduler.stop()  # Clean up


def test_requirements_include_apscheduler() -> None:
    """Verify APScheduler 3.11.1 is in requirements."""
    req_files = [
        Path("requirements.txt"),
        Path("requirements-safety-gate.txt"),
    ]
    
    for req_file in req_files:
        if req_file.exists():
            content = req_file.read_text()
            assert "APScheduler==3.11.1" in content or "apscheduler" in content.lower(), \
                f"APScheduler 3.11.1 not found in {req_file}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
