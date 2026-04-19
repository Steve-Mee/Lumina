"""Tests for PHASE 3: Veto registry, window, and Telegram integration."""

import json
import pytest
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from lumina_core.evolution import VetoRecord, VetoRegistry, VetoWindow, TelegramNotifier


class TestVetoRegistry:
    """Tests for immutable append-only veto registry."""

    def test_veto_registry_append_and_list_recent(self):
        """Test veto record append-only persistence (SQLite + JSONL)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test_veto.db")
            log_path = str(Path(tmpdir) / "test_veto.jsonl")

            registry = VetoRegistry(db_path=db_path, log_path=log_path)

            # Append veto record
            record1 = VetoRecord(
                veto_timestamp=datetime.utcnow().isoformat(),
                dna_id="dna_001",
                dna_fitness=0.85,
                reason="High risk mutation",
                issuer="steve",
                metadata={"proposal_id": "prop_123"},
            )
            registry.append_veto(record1)

            # Verify JSONL line written
            with open(log_path) as f:
                lines = f.readlines()
            assert len(lines) == 1
            parsed = json.loads(lines[0])
            assert parsed["dna_id"] == "dna_001"

            # Append second record
            record2 = VetoRecord(
                veto_timestamp=(datetime.utcnow() + timedelta(seconds=1)).isoformat(),
                dna_id="dna_002",
                dna_fitness=0.90,
                reason="Excessive drawdown",
                issuer="approval_twin_gate",
                metadata={},
            )
            registry.append_veto(record2)

            # List recent
            recent = registry.list_recent(limit=10)
            assert len(recent) == 2
            assert recent[0].dna_id == "dna_002"  # Most recent first
            assert recent[1].dna_id == "dna_001"

    def test_veto_registry_is_veto_active_within_window(self):
        """Test veto window check (fail-closed)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test_veto.db")
            log_path = str(Path(tmpdir) / "test_veto.jsonl")

            registry = VetoRegistry(db_path=db_path, log_path=log_path)

            # Append recent veto (within window)
            now = datetime.utcnow()
            record_recent = VetoRecord(
                veto_timestamp=now.isoformat(),
                dna_id="dna_active_recent",
                dna_fitness=0.80,
                reason="Test veto",
                issuer="steve",
                metadata={},
            )
            registry.append_veto(record_recent)

            # Append old veto (outside window)
            old_time = datetime.utcnow() - timedelta(hours=1)
            record_old = VetoRecord(
                veto_timestamp=old_time.isoformat(),
                dna_id="dna_active_old",
                dna_fitness=0.80,
                reason="Old test veto",
                issuer="steve",
                metadata={},
            )
            registry.append_veto(record_old)

            # Check: recent veto should be active within 30-min window (1800 seconds)
            assert registry.is_veto_active("dna_active_recent", window_seconds=1800) is True

            # Check: old veto should NOT be active (1 hour ago, outside default window)
            assert registry.is_veto_active("dna_active_old", window_seconds=1800) is False

            # Check: non-existent DNA should have no veto
            assert registry.is_veto_active("dna_nonexistent", window_seconds=1800) is False

    def test_veto_registry_fail_closed_on_error(self):
        """Test fail-closed behavior on query errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test_veto.db")
            log_path = str(Path(tmpdir) / "test_veto.jsonl")

            registry = VetoRegistry(db_path=db_path, log_path=log_path)

            # Close connection to force error on next query
            try:
                # Corrupt the database path
                registry._db_path = Path(tmpdir) / "nonexistent_dir" / "test.db"
                # Fail-closed: returns True (assumes veto is active, blocks promotion)
                assert registry.is_veto_active("dna_test") is True
            finally:
                # Restore original path for cleanup
                registry._db_path = Path(db_path)


class TestVetoWindow:
    """Tests for veto window promotion blocking logic."""

    def test_veto_window_blocks_promotion_on_active_veto(self):
        """Test that veto window blocks promotion when veto is active."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test_veto.db")
            log_path = str(Path(tmpdir) / "test_veto.jsonl")

            veto_registry = VetoRegistry(db_path=db_path, log_path=log_path)
            veto_window = VetoWindow(veto_registry=veto_registry, window_seconds=1800)

            # Append veto for dna_test
            record = VetoRecord(
                veto_timestamp=datetime.utcnow().isoformat(),
                dna_id="dna_test",
                dna_fitness=0.85,
                reason="Blocked by veto",
                issuer="steve",
                metadata={},
            )
            veto_registry.append_veto(record)

            # Veto window should block promotion
            assert veto_window.is_promotion_blocked("dna_test") is True

            # Other DNA should not be blocked
            assert veto_window.is_promotion_blocked("dna_other") is False

    def test_veto_window_detailed_check(self):
        """Test detailed veto window check with metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test_veto.db")
            log_path = str(Path(tmpdir) / "test_veto.jsonl")

            veto_registry = VetoRegistry(db_path=db_path, log_path=log_path)
            veto_window = VetoWindow(veto_registry=veto_registry, window_seconds=1800)

            # No veto yet
            result = veto_window.check_with_details("dna_check")
            assert result["is_blocked"] is False
            assert result["active_veto_records"] == []

            # Add veto
            record = VetoRecord(
                veto_timestamp=datetime.utcnow().isoformat(),
                dna_id="dna_check",
                dna_fitness=0.90,
                reason="Test veto for detail check",
                issuer="telegram_steve",
                metadata={"proposal_id": "prop_456"},
            )
            veto_registry.append_veto(record)

            # Should be blocked with details
            result = veto_window.check_with_details("dna_check")
            assert result["is_blocked"] is True
            assert len(result["active_veto_records"]) > 0
            assert result["active_veto_records"][0].reason == "Test veto for detail check"

    def test_veto_window_no_registry_allows_promotion(self):
        """Test that missing registry doesn't block promotion (veto window disabled)."""
        veto_window = VetoWindow(veto_registry=None, window_seconds=1800)

        # Without registry, promotions are not blocked
        assert veto_window.is_promotion_blocked("dna_any") is False


class TestTelegramNotifier:
    """Tests for Telegram notification system (without actual API calls)."""

    def test_telegram_notifier_missing_credentials_no_op(self):
        """Test that missing Telegram credentials result in safe no-op behavior."""
        notifier = TelegramNotifier(api_token="", chat_id="")

        # Should handle gracefully with missing credentials
        result = notifier.send_proposal_notification(
            dna_id="dna_test",
            fitness=0.85,
            twin_confidence=0.92,
            proposal_summary="Test proposal",
        )
        # Fail-open: notifications missing creds don't block evolution
        assert result is True

    def test_telegram_notifier_records_veto_in_registry(self):
        """Test that veto recording integrates with VetoRegistry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test_veto.db")
            log_path = str(Path(tmpdir) / "test_veto.jsonl")

            veto_registry = VetoRegistry(db_path=db_path, log_path=log_path)
            notifier = TelegramNotifier(veto_registry=veto_registry, api_token="", chat_id="")

            # Record veto
            result = notifier.record_veto(
                dna_id="dna_veto_test",
                dna_fitness=0.88,
                reason="Steve vetoed via Telegram",
            )
            assert result is True

            # Verify in registry
            recent = veto_registry.list_recent(limit=10)
            assert len(recent) == 1
            assert recent[0].dna_id == "dna_veto_test"
            assert recent[0].issuer == "telegram_steve"

    def test_telegram_notifier_cleanup_expired_proposals(self):
        """Test cleanup of expired veto windows."""
        notifier = TelegramNotifier(api_token="", chat_id="")

        # Add old proposal to pending dict
        old_time = datetime.utcnow() - timedelta(hours=2)
        notifier._pending_proposals["dna_old"] = {
            "sent_at": old_time.isoformat(),
            "dna_fitness": 0.85,
            "twin_confidence": 0.90,
            "summary": "Old proposal",
            "veto_window_minutes": 30,
            "veto_deadline": (old_time + timedelta(minutes=30)).isoformat(),
            "tags": [],
        }

        # Add fresh proposal
        fresh_time = datetime.utcnow()
        notifier._pending_proposals["dna_fresh"] = {
            "sent_at": fresh_time.isoformat(),
            "dna_fitness": 0.87,
            "twin_confidence": 0.91,
            "summary": "Fresh proposal",
            "veto_window_minutes": 30,
            "veto_deadline": (fresh_time + timedelta(minutes=30)).isoformat(),
            "tags": [],
        }

        # Cleanup
        notifier.cleanup_expired_proposals(window_seconds=1800)

        # Old should be removed, fresh should remain
        assert "dna_old" not in notifier._pending_proposals
        assert "dna_fresh" in notifier._pending_proposals


class TestVetoIntegrationWithOrchestrator:
    """Integration tests for veto window in orchestrator promotion gate."""

    def test_orchestrator_blocks_promotion_with_active_veto(self):
        """Test that orchestrator respects veto window (integration test)."""
        from lumina_core.evolution import EvolutionOrchestrator

        # Get orchestrator singleton
        orchestrator = EvolutionOrchestrator()

        # Verify veto components initialized
        assert orchestrator._veto_registry is not None
        assert orchestrator._veto_window is not None

        # Add test veto for a specific DNA
        test_dna_id = "veto_integration_test_dna"
        record = VetoRecord(
            veto_timestamp=datetime.utcnow().isoformat(),
            dna_id=test_dna_id,
            dna_fitness=0.85,
            reason="Integration test veto",
            issuer="test",
            metadata={},
        )
        orchestrator._veto_registry.append_veto(record)

        # Verify veto is active
        assert orchestrator._veto_window.is_promotion_blocked(test_dna_id) is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
