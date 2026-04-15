from __future__ import annotations

import json
from pathlib import Path

from lumina_core.engine.valuation_engine import ValuationEngine


def test_valuation_engine_applies_symbol_commission_calibration() -> None:
    engine = ValuationEngine()
    base = engine.commission_dollars(symbol="MES JUN26", quantity=2, sides=2)

    engine.apply_calibration({"symbol_commission_multiplier": {"MES": 1.5}})
    calibrated = engine.commission_dollars(symbol="MES JUN26", quantity=2, sides=2)

    assert calibrated > base


def test_valuation_engine_loads_calibration_file(tmp_path: Path) -> None:
    payload = {
        "symbol_commission_multiplier": {"MES": 1.2},
        "symbol_spread_multiplier": {"default": 1.3},
        "fill_latency_multiplier": {"default": 1.1, "volatile": 1.5},
    }
    path = tmp_path / "fill_calibration.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    engine = ValuationEngine()
    assert engine.load_calibration_file(path) is True

    slow = engine.estimate_fill_latency_ms(volume=1.0, avg_volume=1.0, pending_age=1, regime="VOLATILE")
    calm = engine.estimate_fill_latency_ms(volume=1.0, avg_volume=1.0, pending_age=1, regime="RANGING")
    assert slow > calm
