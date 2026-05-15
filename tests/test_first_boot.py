"""
High-quality unit tests for FirstBootManager.
"""

import tempfile
from pathlib import Path

from core.first_boot import FirstBootManager


def test_first_boot_manager_initialization():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        manager = FirstBootManager(root)
        assert manager.workspace_root == root


def test_save_and_read_settings():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        manager = FirstBootManager(root)

        # Gebruiker kiest zelf het aantal training trades
        manager.save_settings(5000)
        settings = manager.read_settings()

        # Het getal moet overeenkomen met wat de gebruiker heeft ingegeven
        assert settings["training_trades"] == 5000
        assert "prefer_real_data_only" in settings


def test_artifacts_missing_when_no_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        manager = FirstBootManager(root)
        assert manager.artifacts_missing() is True


def test_get_stage_progress():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        manager = FirstBootManager(root)

        assert manager.get_stage_progress("training_running") == 0.75
        assert manager.get_stage_progress("completed") == 1.0
        assert manager.get_stage_progress("unknown") == 0.1
