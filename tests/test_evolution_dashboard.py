from __future__ import annotations

import json
from pathlib import Path

from lumina_core.evolution.evolution_metrics_loaders import (
    load_evolution_metrics,
    load_rollout_history,
)


def _write_metrics(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def _complete_cycle(cycle_idx: int = 1, promoted: bool = False) -> dict:
    return {
        "status": "complete",
        "timestamp": f"2026-04-1{cycle_idx}T10:00:00+00:00",
        "generations_run": 3,
        "total_candidates_evaluated": 15,
        "promotions": 1 if promoted else 0,
        "best_fitness": 1.23,
        "generations": [
            {"generation": 0, "candidates": 5, "winner_hash": "abc123", "winner_fitness": 1.0, "promoted": False},
            {"generation": 1, "candidates": 5, "winner_hash": "def456", "winner_fitness": 1.23, "promoted": promoted},
            {"generation": 2, "candidates": 5, "winner_hash": "def456", "winner_fitness": 1.10, "promoted": False},
        ],
    }


def test_load_metrics_filters_complete_rows(tmp_path: Path) -> None:
    path = tmp_path / "metrics.jsonl"
    _write_metrics(path, [{"status": "running"}, _complete_cycle()])
    rows = load_evolution_metrics(path)
    assert len(rows) == 1
    assert rows[0]["status"] == "complete"


def test_load_rollout_history_filters_decisions(tmp_path: Path) -> None:
    path = tmp_path / "rollout.jsonl"
    _write_metrics(
        path,
        [
            {"event": "rollout_decision", "mode": "sim", "allow_promotion": True},
            {"event": "other", "mode": "sim"},
        ],
    )
    rows = load_rollout_history(path)
    assert len(rows) == 1
    assert rows[0]["event"] == "rollout_decision"
