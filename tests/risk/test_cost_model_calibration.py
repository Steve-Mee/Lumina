from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.risk.cost_model import TradeExecutionCostModel
from lumina_core.risk.cost_model_calibrator import (
    apply_calibration_from_state,
    compute_exit_leg_costs,
    run_daily_calibration,
)


@pytest.mark.unit
class TestCostModelCalibration:
    def test_daily_calibration_computes_bias_and_persists_state(self, tmp_path: Path) -> None:
        # gegeven
        audit_path = tmp_path / "trade_fill_audit.jsonl"
        state_path = tmp_path / "cost_model_calibration.json"
        rows = [
            {
                "event": "reconciled",
                "ts": "2026-05-01T10:00:00+00:00",
                "symbol": "MES JUN26",
                "entry_price": 5000.0,
                "quantity": 1,
                "slippage_points": 1.0,
                "commission": 1.2,
            },
            {
                "event": "reconciled",
                "ts": "2026-05-01T11:00:00+00:00",
                "symbol": "MES JUN26",
                "entry_price": 5001.0,
                "quantity": 2,
                "slippage_points": 0.5,
                "commission": 2.4,
            },
            {"event": "fill_received", "ts": "2026-05-01T11:10:00+00:00"},
        ]
        audit_path.write_text("\n".join(json.dumps(item) for item in rows), encoding="utf-8")
        model = TradeExecutionCostModel.from_config({}, instrument="MES")
        expected_biases: list[float] = []
        for row in rows[:2]:
            real_usd, model_usd, _ = compute_exit_leg_costs(row, model, atr=8.0, time_period="midday")
            expected_biases.append(real_usd - model_usd)

        # wanneer
        result = run_daily_calibration(
            audit_path=audit_path,
            state_path=state_path,
            instrument="MES",
            atr_fallback=8.0,
            time_period="midday",
        )

        # dan
        assert result.sample_count == 2
        assert result.mean_bias_usd == pytest.approx(sum(expected_biases) / 2.0, rel=1e-6)
        assert state_path.exists()
        persisted = json.loads(state_path.read_text(encoding="utf-8"))
        assert persisted["rolling"]["sample_count"] == 2
        assert persisted["rolling"]["recommended_slippage_sigma"] >= 0.0
        assert len(persisted["daily"]) == 1

    def test_apply_calibration_updates_cost_output_and_sigma(self) -> None:
        # gegeven
        model = TradeExecutionCostModel.from_config({}, instrument="MES")
        before = model.cost_for_trade(price=5000.0, quantity=1.0, atr=6.0, avg_volume=10000.0, time_period="midday")

        # wanneer
        model.apply_calibration(bias_slippage_ticks=1.0, slippage_sigma=0.35)
        after = model.cost_for_trade(price=5000.0, quantity=1.0, atr=6.0, avg_volume=10000.0, time_period="midday")

        # dan
        assert after.total_slippage_ticks == pytest.approx(before.total_slippage_ticks + 1.0, rel=1e-6)
        assert after.slippage_usd_per_side == pytest.approx(before.slippage_usd_per_side + 1.25, rel=1e-6)
        assert model.slippage_sigma == pytest.approx(0.35, rel=1e-6)

    def test_empty_audit_produces_zero_bias(self, tmp_path: Path) -> None:
        # gegeven
        audit_path = tmp_path / "empty.jsonl"
        audit_path.write_text("", encoding="utf-8")
        state_path = tmp_path / "state.json"

        # wanneer
        result = run_daily_calibration(audit_path=audit_path, state_path=state_path, instrument="MES")

        # dan
        assert result.sample_count == 0
        assert result.mean_bias_usd == pytest.approx(0.0)
        assert result.stdev_bias_usd == pytest.approx(0.0)

    def test_apply_calibration_from_state_uses_recommended_sigma(self, tmp_path: Path) -> None:
        # gegeven
        state_path = tmp_path / "cost_model_calibration.json"
        state_path.write_text(
            json.dumps(
                {
                    "rolling": {
                        "mean_bias_ticks": 0.8,
                        "stdev_bias_ticks": 0.2,
                        "recommended_slippage_sigma": 0.4,
                    }
                }
            ),
            encoding="utf-8",
        )
        model = TradeExecutionCostModel.from_config({}, instrument="MES")

        # wanneer
        bias_ticks, sigma = apply_calibration_from_state(model, state_path=state_path)

        # dan
        assert bias_ticks == pytest.approx(0.8, rel=1e-6)
        assert sigma == pytest.approx(0.4, rel=1e-6)
        assert model.calibration_bias_ticks == pytest.approx(0.8, rel=1e-6)
        assert model.slippage_sigma == pytest.approx(0.4, rel=1e-6)
