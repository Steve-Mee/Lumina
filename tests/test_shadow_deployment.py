"""Tests for ShadowDeploymentTracker and ABExperimentFramework (P5 - Rollout Framework).

All tests are unit-level — uses tmp_path for state isolation.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.evolution.shadow_deployment import ShadowDeploymentTracker, _cohens_d, _welch_t_pvalue
from lumina_core.experiments.ab_framework import ABExperimentFramework


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestStatisticalHelpers:
    def test_welch_t_pvalue_returns_1_for_tiny_samples(self):
        assert _welch_t_pvalue([1.0, 2.0], [3.0]) == 1.0

    def test_welch_t_pvalue_identical_distributions_high_pvalue(self):
        a = [1.0] * 20
        b = [1.0] * 20
        p = _welch_t_pvalue(a, b)
        assert p >= 0.9

    def test_welch_t_pvalue_clearly_different_low_pvalue(self):
        import random
        rng = random.Random(42)
        a = [rng.gauss(0.0, 1.0) for _ in range(100)]
        b = [rng.gauss(5.0, 1.0) for _ in range(100)]
        p = _welch_t_pvalue(a, b)
        assert p < 0.05

    def test_cohens_d_zero_for_identical(self):
        a = [1.0, 2.0, 3.0, 4.0, 5.0]
        d = _cohens_d(a, a)
        assert abs(d) < 1e-9

    def test_cohens_d_large_for_very_different(self):
        import random
        rng = random.Random(7)
        # Means separated by 10 sigma apart — Cohen's d should be large
        a = [rng.gauss(0.0, 1.0) for _ in range(40)]
        b = [rng.gauss(10.0, 1.0) for _ in range(40)]
        d = _cohens_d(b, a)
        assert d > 5.0, f"Expected Cohen's d > 5.0 for 10-sigma separation, got {d:.2f}"


# ---------------------------------------------------------------------------
# ShadowDeploymentTracker
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestShadowDeploymentTracker:
    def _make_tracker(self, tmp_path: Path, min_days: float = 0.0, min_trades: int = 3) -> ShadowDeploymentTracker:
        return ShadowDeploymentTracker(
            state_path=tmp_path / "shadow_runs.json",
            min_days=min_days,
            min_trades=min_trades,
        )

    def test_start_shadow_creates_run(self, tmp_path: Path):
        tracker = self._make_tracker(tmp_path)
        run = tracker.start_shadow("abc123")
        assert run.dna_hash == "abc123"
        assert run.status == "running"

    def test_start_shadow_idempotent(self, tmp_path: Path):
        tracker = self._make_tracker(tmp_path)
        run1 = tracker.start_shadow("abc123")
        run2 = tracker.start_shadow("abc123")
        assert run1.start_ts == run2.start_ts

    def test_record_pnl_accumulates(self, tmp_path: Path):
        tracker = self._make_tracker(tmp_path)
        tracker.start_shadow("abc123")
        tracker.record_pnl("abc123", sim_pnl=100.0)
        tracker.record_pnl("abc123", sim_pnl=200.0)
        tracker.record_pnl("abc123", paper_pnl=50.0)
        runs = tracker.get_all_runs()
        run = runs["abc123"]
        assert run.trade_count == 3
        assert abs(run.total_sim_pnl - 300.0) < 1e-9

    def test_shadow_verdict_pending_without_enough_trades(self, tmp_path: Path):
        tracker = self._make_tracker(tmp_path, min_trades=10)
        tracker.start_shadow("abc123")
        tracker.record_pnl("abc123", sim_pnl=50.0)
        assert tracker.compute_shadow_verdict("abc123") == "pending"

    def test_shadow_verdict_pass_for_profitable(self, tmp_path: Path):
        tracker = self._make_tracker(tmp_path, min_days=0.0, min_trades=3)
        tracker.start_shadow("abc123")
        for _ in range(5):
            tracker.record_pnl("abc123", sim_pnl=100.0)
        assert tracker.compute_shadow_verdict("abc123") == "pass"

    def test_shadow_verdict_fail_for_losing(self, tmp_path: Path):
        tracker = self._make_tracker(tmp_path, min_days=0.0, min_trades=3)
        tracker.start_shadow("abc123")
        for _ in range(5):
            tracker.record_pnl("abc123", sim_pnl=-100.0)
        assert tracker.compute_shadow_verdict("abc123") == "fail"

    def test_mark_promoted_sets_status(self, tmp_path: Path):
        tracker = self._make_tracker(tmp_path, min_days=0.0, min_trades=3)
        tracker.start_shadow("abc123")
        for _ in range(5):
            tracker.record_pnl("abc123", sim_pnl=50.0)
        tracker.mark_promoted("abc123")
        runs = tracker.get_all_runs()
        assert runs["abc123"].status == "promoted"

    def test_shadow_ab_inconclusive_with_too_few_samples(self, tmp_path: Path):
        tracker = self._make_tracker(tmp_path)
        result = tracker.run_shadow_ab([1.0, 2.0], [3.0, 4.0], n_min=30)
        assert result["verdict"] == "inconclusive"

    def test_shadow_ab_variant_wins_clear_difference(self, tmp_path: Path):
        import random
        rng = random.Random(99)
        ctrl = [rng.gauss(0.0, 1.0) for _ in range(60)]
        variant = [rng.gauss(5.0, 1.0) for _ in range(60)]
        tracker = self._make_tracker(tmp_path)
        result = tracker.run_shadow_ab(ctrl, variant, n_min=30)
        assert result["verdict"] == "variant_wins"


# ---------------------------------------------------------------------------
# ABExperimentFramework.run_shadow_ab
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestABFrameworkShadowAB:
    def test_run_shadow_ab_inconclusive_small_samples(self):
        fw = ABExperimentFramework()
        result = fw.run_shadow_ab([10.0] * 5, [15.0] * 5, n_min=30)
        assert result.verdict == "inconclusive"

    def test_run_shadow_ab_variant_wins(self):
        import random
        rng = random.Random(123)
        ctrl = [rng.gauss(1.0, 1.0) for _ in range(60)]
        variant = [rng.gauss(6.0, 1.0) for _ in range(60)]
        fw = ABExperimentFramework()
        result = fw.run_shadow_ab(ctrl, variant, n_min=30)
        assert result.verdict == "variant_wins"
        assert result.significant
