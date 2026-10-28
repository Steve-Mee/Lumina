"""Playground first SIM order must be a venue fill, not a health flag or JSON stamp."""
from __future__ import annotations

import json
from pathlib import Path

from lumina_core.maturity.playground.fills import (
    first_honest_fill,
    json_stamp_exists,
    record_orderpath_fill,
)


def test_fabric_health_is_not_first_order(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "fabric_sim_health.json").write_text(
        json.dumps({"ok": True, "healthy": True}), encoding="utf-8"
    )
    assert first_honest_fill(tmp_path) is None


def test_first_sim_order_json_does_not_count(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "first_sim_order.json").write_text(
        json.dumps({"placed": True, "order_id": "SIM-1"}), encoding="utf-8"
    )
    assert json_stamp_exists(tmp_path) is True
    assert first_honest_fill(tmp_path) is None


def test_orderpath_fill_is_honest_evidence(tmp_path: Path) -> None:
    rec = record_orderpath_fill(
        tmp_path,
        order_id="SIM-1",
        fill_px=5124.25,
        qty=1,
        instrument="MES",
        mode="sim",
        source="ops_place_order",
    )
    assert rec["ok"] is True
    fill = first_honest_fill(tmp_path)
    assert fill is not None
    assert fill["order_id"] == "SIM-1"
