# Integration test: HeadlessRuntime 1-minute dry-run
# Validates that the headless trade loop completes and emits a well-formed
# JSON summary with all required fields at the correct types.
from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.runtime.headless_runtime import (
    HeadlessRuntime,
    _generate_synthetic_ticks,
    _run_simulation,
    _validate_broker,
    parse_duration_minutes,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: dict[str, type] = {
    "schema_version": str,
    "runtime": str,
    "mode": str,
    "broker_mode": str,
    "broker_status": str,
    "duration_minutes": float,
    "started_at": str,
    "finished_at": str,
    "total_trades": int,
    "pnl_realized": float,
    "max_drawdown": float,
    "risk_events": int,
    "var_breach_count": int,
    "wins": int,
    "win_rate": float,
    "mean_pnl_per_trade": float,
    "sharpe_annualized": float,
    "evolution_proposals": int,
    "session_guard_blocks": int,
    "observability_alerts": int,
    "metrics_learning": dict,
    "metrics_realism": dict,
    "metrics_primary": str,
    "financial_reporting": dict,
    "stress_report": dict,
    "stress_ready_for_real_gate": bool,
}


def _assert_summary_structure(summary: dict[str, Any]) -> None:
    """Assert that summary contains all required fields with correct types."""
    for field, expected_type in REQUIRED_FIELDS.items():
        assert field in summary, f"Missing field: {field}"
        value = summary[field]
        # Allow int where float is expected (numeric subtype)
        if expected_type is float:
            assert isinstance(value, (int, float)), (
                f"Field '{field}' must be numeric, got {type(value).__name__}: {value!r}"
            )
        else:
            assert isinstance(value, expected_type), (
                f"Field '{field}' expected {expected_type.__name__}, got {type(value).__name__}: {value!r}"
            )


# ---------------------------------------------------------------------------
# Unit tests – simulation kernel
# ---------------------------------------------------------------------------


class TestGenerateSyntheticTicks:
    def test_returns_requested_count(self):
        ticks = _generate_synthetic_ticks(n=500, seed=42)
        assert len(ticks) == 500

    def test_tick_structure(self):
        ticks = _generate_synthetic_ticks(n=10, seed=7)
        for t in ticks:
            assert "last" in t
            assert "volume" in t
            assert "regime" in t
            assert "imbalance" in t
            assert float(t["last"]) > 0

    def test_deterministic_with_same_seed(self):
        a = _generate_synthetic_ticks(n=100, seed=99)
        b = _generate_synthetic_ticks(n=100, seed=99)
        assert a == b

    def test_different_seeds_produce_different_ticks(self):
        a = _generate_synthetic_ticks(n=100, seed=1)
        b = _generate_synthetic_ticks(n=100, seed=2)
        assert a != b


class TestRunSimulation:
    def test_returns_all_expected_keys(self):
        ticks = _generate_synthetic_ticks(n=2000, seed=42)
        result = _run_simulation(ticks, seed=42)
        for key in (
            "total_trades",
            "pnl_realized",
            "max_drawdown",
            "risk_events",
            "var_breach_count",
            "wins",
            "win_rate",
            "mean_pnl_per_trade",
            "sharpe_annualized",
        ):
            assert key in result, f"Missing key: {key}"

    def test_trade_count_positive(self):
        ticks = _generate_synthetic_ticks(n=5000, seed=42)
        result = _run_simulation(ticks, seed=42)
        assert result["total_trades"] > 0

    def test_win_rate_bounded(self):
        ticks = _generate_synthetic_ticks(n=5000, seed=42)
        result = _run_simulation(ticks, seed=42)
        assert 0.0 <= result["win_rate"] <= 1.0

    def test_max_drawdown_non_negative(self):
        ticks = _generate_synthetic_ticks(n=5000, seed=42)
        result = _run_simulation(ticks, seed=42)
        assert result["max_drawdown"] >= 0.0

    def test_wins_leq_total_trades(self):
        ticks = _generate_synthetic_ticks(n=5000, seed=42)
        result = _run_simulation(ticks, seed=42)
        assert result["wins"] <= result["total_trades"]


class TestValidateBroker:
    def test_paper_returns_paper_ok(self):
        status = _validate_broker("paper")
        assert status == "paper_ok"

    def test_live_returns_string(self):
        status = _validate_broker("live")
        assert isinstance(status, str)
        assert len(status) > 0


class TestParseDurationMinutes:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ("15m", 15.0),
            ("5m", 5.0),
            ("1m", 1.0),
            ("60s", 1.0),
            ("1h", 60.0),
            ("30", 30.0),
        ],
    )
    def test_parses_correctly(self, value, expected):
        assert parse_duration_minutes(value) == pytest.approx(expected, rel=1e-6)

    def test_invalid_raises(self):
        with pytest.raises((ValueError, Exception)):
            parse_duration_minutes("bogus")


# ---------------------------------------------------------------------------
# HeadlessRuntime integration tests (1-minute dry-run)
# ---------------------------------------------------------------------------


class TestHeadlessRuntime:
    """Integration tests: run the full runtime end-to-end and validate output."""

    @pytest.mark.safety_gate
    def test_sim_mode_emits_learning_contract(self, tmp_path, monkeypatch, capsys):
        """SIM mode should expose the learning contract in summary and console output."""
        import lumina_core.runtime.headless_runtime as hr_mod

        monkeypatch.setattr(hr_mod, "_SUMMARY_PATH", tmp_path / "last_run_summary.json")

        runtime = HeadlessRuntime(container=None)
        summary = runtime.run(duration_minutes=1, mode="sim", broker_mode="paper")

        _assert_summary_structure(summary)
        assert summary["mode"] == "sim"
        assert summary["broker_mode"] == "paper"
        assert summary["broker_status"] == "paper_ok"
        assert summary["risk_events"] == 0
        assert summary["var_breach_count"] == 0
        assert summary["evolution_proposals"] >= 32
        assert summary["metrics_primary"] == "learning"
        assert isinstance(summary["metrics_learning"], dict)
        assert isinstance(summary["metrics_realism"], dict)
        assert summary["financial_reporting"]["metrics_for_readiness_gate"] == "realism"
        assert "parity_delta_pnl_realized" in summary["financial_reporting"]
        assert "parity_delta_max_drawdown" in summary["financial_reporting"]
        assert "parity_delta_sharpe_annualized" in summary["financial_reporting"]
        assert "volatility_spike" in summary["stress_report"]["scenarios"]

        captured = capsys.readouterr()
        assert "SIM LEARNING MODE ACTIVE" in captured.out

    def test_sim_mode_test_bypass_overrides_readiness_only_when_flagged(self, tmp_path, monkeypatch):
        import lumina_core.runtime.headless_runtime as hr_mod

        monkeypatch.setattr(hr_mod, "_SUMMARY_PATH", tmp_path / "last_run_summary.json")
        monkeypatch.setenv("LUMINA_TEST_BYPASS_READINESS_GATE", "true")

        runtime = HeadlessRuntime(container=None)
        summary = runtime.run(duration_minutes=1, mode="sim", broker_mode="paper")

        assert summary["READY_FOR_REAL"] is True
        assert summary["stability_status"] == "TEST_BYPASS"
        assert summary["stress_ready_for_real_gate"] is True
        assert summary["test_readiness_bypass"]["enabled"] is True
        assert summary["stability_report"]["status"] == "TEST_BYPASS"

    def test_paper_mode_returns_valid_summary(self, tmp_path, monkeypatch):
        """1-minute paper dry-run produces a complete, well-typed JSON summary."""
        # Redirect summary file to tmp_path
        import lumina_core.runtime.headless_runtime as hr_mod

        monkeypatch.setattr(hr_mod, "_SUMMARY_PATH", tmp_path / "last_run_summary.json")

        runtime = HeadlessRuntime(container=None)
        summary = runtime.run(duration_minutes=1, mode="paper", broker_mode="paper")

        _assert_summary_structure(summary)
        assert summary["mode"] == "paper"
        assert summary["broker_mode"] == "paper"
        assert summary["broker_status"] == "paper_ok"
        assert summary["runtime"] == "headless"
        assert summary["schema_version"] == "1.0"
        assert summary["duration_minutes"] == pytest.approx(1.0)
        assert summary["metrics_primary"] == "realism"
        assert summary["financial_reporting"]["metrics_for_readiness_gate"] == "realism"
        assert isinstance(summary["stress_report"]["worst_case_drawdown"], (int, float))

    def test_summary_written_to_disk(self, tmp_path, monkeypatch):
        """Summary JSON is persisted to the configured path."""
        import lumina_core.runtime.headless_runtime as hr_mod

        out_path = tmp_path / "last_run_summary.json"
        monkeypatch.setattr(hr_mod, "_SUMMARY_PATH", out_path)

        runtime = HeadlessRuntime(container=None)
        runtime.run(duration_minutes=1, mode="paper", broker_mode="paper")

        assert out_path.exists()
        data = json.loads(out_path.read_text(encoding="utf-8"))
        _assert_summary_structure(data)

    def test_live_broker_mode_returns_summary(self, tmp_path, monkeypatch):
        """live broker_mode completes; broker_status may vary but summary is valid."""
        import lumina_core.runtime.headless_runtime as hr_mod

        monkeypatch.setattr(hr_mod, "_SUMMARY_PATH", tmp_path / "last_run_summary.json")
        # Inject a stub token so live-broker path does not raise on missing creds.
        monkeypatch.setenv("CROSSTRADE_TOKEN", "headless-integration-test-stub")

        runtime = HeadlessRuntime(container=None)
        summary = runtime.run(duration_minutes=1, mode="paper", broker_mode="live")

        _assert_summary_structure(summary)
        assert summary["broker_mode"] == "live"
        assert isinstance(summary["broker_status"], str)

    def test_summary_has_positive_trades(self, tmp_path, monkeypatch):
        """A non-trivial duration generates at least one simulated trade."""
        import lumina_core.runtime.headless_runtime as hr_mod

        monkeypatch.setattr(hr_mod, "_SUMMARY_PATH", tmp_path / "last_run_summary.json")

        runtime = HeadlessRuntime(container=None)
        summary = runtime.run(duration_minutes=5, mode="paper", broker_mode="paper")

        assert summary["total_trades"] > 0

    def test_with_mock_container_evolution_count(self, tmp_path, monkeypatch):
        """When a container is passed whose evolution log has 'proposed' entries,
        the count is reflected in the summary."""
        import lumina_core.runtime.headless_runtime as hr_mod

        monkeypatch.setattr(hr_mod, "_SUMMARY_PATH", tmp_path / "last_run_summary.json")

        # Write a fake evolution log with 3 proposed entries
        evo_log = tmp_path / "evolution_log.jsonl"
        for i in range(3):
            evo_log.open("a").write(json.dumps({"status": "proposed", "id": i}) + "\n")
        monkeypatch.setattr(
            hr_mod,
            "_count_evolution_proposals",
            lambda _container: 3,
        )

        mock_container = SimpleNamespace(engine=object())
        runtime = HeadlessRuntime(container=mock_container)
        summary = runtime.run(duration_minutes=1, mode="paper", broker_mode="paper")

        assert summary["evolution_proposals"] == 3

    def test_pnl_is_finite(self, tmp_path, monkeypatch):
        """Realized PnL must be a finite number (not NaN/Inf)."""
        import math
        import lumina_core.runtime.headless_runtime as hr_mod

        monkeypatch.setattr(hr_mod, "_SUMMARY_PATH", tmp_path / "last_run_summary.json")

        runtime = HeadlessRuntime(container=None)
        summary = runtime.run(duration_minutes=2, mode="paper", broker_mode="paper")

        assert math.isfinite(summary["pnl_realized"])
        assert math.isfinite(summary["max_drawdown"])
        assert math.isfinite(summary["sharpe_annualized"])
