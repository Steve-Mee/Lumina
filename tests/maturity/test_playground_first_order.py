"""Playground first SIM order must be real evidence, not a health flag."""
from __future__ import annotations

import json
from pathlib import Path

from lumina_core.maturity.phase_runners.playground import _first_sim_order_probe


def test_fabric_health_is_not_first_order(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "fabric_sim_health.json").write_text(
        json.dumps({"ok": True, "healthy": True}), encoding="utf-8"
    )
    probe = _first_sim_order_probe(tmp_path)
    assert probe["ok"] is False
    assert probe["reason"] == "no_first_order_evidence"


def test_first_sim_order_json_counts(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True)
    (state / "first_sim_order.json").write_text(
        json.dumps({"placed": True, "order_id": "SIM-1"}), encoding="utf-8"
    )
    probe = _first_sim_order_probe(tmp_path)
    assert probe["ok"] is True
    assert probe["order_id"] == "SIM-1"
