"""Tests for ApprovalGymScheduler – periodic gym session execution."""

import json
import pytest
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from lumina_core.evolution import ApprovalGymScheduler


class TestApprovalGymScheduler:
    """Tests for periodic approval gym scheduler."""

    def teardown_method(self):
        """Reset singleton state between tests."""
        # Stop scheduler if running
        try:
            ApprovalGymScheduler()._running = False
        except Exception:
            pass
        # Reset singleton
        ApprovalGymScheduler._instance = None

    def test_scheduler_singleton(self):
        """Test that scheduler is a singleton."""
        scheduler1 = ApprovalGymScheduler()
        scheduler2 = ApprovalGymScheduler()

        assert scheduler1 is scheduler2

    def test_scheduler_requires_gym(self):
        """Test that scheduler cannot start without ApprovalGym."""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = str(Path(tmpdir) / "history.jsonl")
            scheduler = ApprovalGymScheduler(
                approval_gym=None,
                history_path=history_path,
            )

            # Start without gym should fail
            result = scheduler.start_scheduler()
            assert result is False

    def test_scheduler_cannot_double_start(self):
        """Test that scheduler cannot be started twice."""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = str(Path(tmpdir) / "history.jsonl")
            mock_gym = MagicMock()
            scheduler = ApprovalGymScheduler(
                approval_gym=mock_gym,
                history_path=history_path,
            )

            # First start should succeed
            result1 = scheduler.start_scheduler()
            assert result1 is True

            # Second start should fail
            result2 = scheduler.start_scheduler()
            assert result2 is False

            # Cleanup
            scheduler.stop_scheduler()

    def test_scheduler_stop_when_not_running(self):
        """Test that stopping non-running scheduler returns False."""
        scheduler = ApprovalGymScheduler()

        result = scheduler.stop_scheduler()
        assert result is False

    def test_scheduler_tracks_session_times(self):
        """Test that scheduler tracks last and next session times."""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = str(Path(tmpdir) / "history.jsonl")
            mock_gym = MagicMock()
            scheduler = ApprovalGymScheduler(
                approval_gym=mock_gym,
                interval_hours=1,
                history_path=history_path,
            )

            # Initially no session run
            assert scheduler.get_last_session_time() is None

            # Next session should be estimated
            next_time = scheduler.get_next_session_time()
            assert next_time is not None
            assert (next_time - datetime.now(timezone.utc)).total_seconds() > 3500  # ~1 hour

    def test_scheduler_logs_session_history(self):
        """Test that completed sessions are logged to history file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = str(Path(tmpdir) / "history.jsonl")
            scheduler = ApprovalGymScheduler(history_path=history_path)

            # Manually log a session (simulate _run_scheduled_session)
            session_record = {
                "session_id": "test_session_001",
                "session_time": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
                "proposal_count": 3,
            }
            scheduler._log_session(session_record)

            # Verify history file
            assert Path(history_path).exists()
            with open(history_path) as f:
                lines = f.readlines()
            assert len(lines) == 1

            parsed = json.loads(lines[0])
            assert parsed["session_id"] == "test_session_001"
            assert parsed["status"] == "completed"

    def test_scheduler_set_interval(self):
        """Test dynamic interval update."""
        scheduler = ApprovalGymScheduler(interval_hours=6)

        # Update interval
        scheduler.set_interval_hours(12)
        assert scheduler._interval_hours == 12

        # Minimum 1 hour
        scheduler.set_interval_hours(0)
        assert scheduler._interval_hours == 1

    def test_scheduler_is_running(self):
        """Test running state check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = str(Path(tmpdir) / "history.jsonl")
            mock_gym = MagicMock()
            scheduler = ApprovalGymScheduler(
                approval_gym=mock_gym,
                history_path=history_path,
            )

            assert scheduler.is_running() is False

            scheduler.start_scheduler()
            assert scheduler.is_running() is True

            scheduler.stop_scheduler()
            assert scheduler.is_running() is False


class TestSchedulerIntegration:
    """Integration tests for scheduler with mock gym."""

    def teardown_method(self):
        """Reset singleton state between tests."""
        try:
            ApprovalGymScheduler()._running = False
        except Exception:
            pass
        ApprovalGymScheduler._instance = None

    def test_scheduler_runs_session_loop(self):
        """Test that scheduler loop calls gym sessions (mocked)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = str(Path(tmpdir) / "history.jsonl")

            # Create mock gym that returns empty list
            mock_gym = MagicMock()
            mock_gym.run_session.return_value = []

            scheduler = ApprovalGymScheduler(
                approval_gym=mock_gym,
                interval_hours=24,  # Long interval to prevent multiple runs
                history_path=history_path,
            )

            # Manually trigger one scheduled session
            scheduler._run_scheduled_session()

            # Verify gym was called
            mock_gym.run_session.assert_called_once()

            # Verify history logged
            with open(history_path) as f:
                lines = f.readlines()
            assert len(lines) == 1
            parsed = json.loads(lines[0])
            assert parsed["status"] == "completed"

    def test_scheduler_handles_gym_failures(self):
        """Test that scheduler handles gym exceptions gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            history_path = str(Path(tmpdir) / "history.jsonl")

            # Create mock gym that raises exception
            mock_gym = MagicMock()
            mock_gym.run_session.side_effect = RuntimeError("Gym failure")

            scheduler = ApprovalGymScheduler(
                approval_gym=mock_gym,
                history_path=history_path,
            )

            # Should not raise; should log failure
            scheduler._run_scheduled_session()

            # Verify failure logged
            with open(history_path) as f:
                lines = f.readlines()
            assert len(lines) == 1
            parsed = json.loads(lines[0])
            assert parsed["status"] == "failed"
            assert "error" in parsed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
