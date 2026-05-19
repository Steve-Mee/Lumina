from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.performance_snapshot import build_performance_block  # noqa: E402


def test_build_performance_block_from_runtime(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    runtime = {
        "account_equity": 101_250.0,
        "daily_pnl": 250.0,
        "open_pnl": 75.0,
        "equity_curve": [100_000.0, 100_500.0, 101_250.0],
        "pnl_history": [500.0, 750.0],
        "session_kpis": {
            "winrate": 0.65,
            "sharpe_annualized": 1.42,
            "profit_factor": 1.8,
            "max_drawdown_pct": -2.5,
            "max_drawdown_usd": 500.0,
            "realized_pnl_session": 1250.0,
        },
    }

    block = build_performance_block(runtime=runtime, state_dir=state_dir)
    assert block is not None
    assert block["source"] == "live"
    assert block["account_equity"] == 101_250.0
    assert block["daily_pnl"] == 250.0
    assert block["open_pnl"] == 75.0
    assert block["session_kpis"]["sharpe_annualized"] == 1.42
    assert len(block["equity_series"]) == 3
    assert block["equity_series"][2]["equity"] == 101_250.0


def test_build_performance_block_recomputes_kpis_when_missing(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    runtime = {
        "account_equity": 100_000.0,
        "daily_pnl": 0.0,
        "open_pnl": 0.0,
        "equity_curve": [100_000.0, 99_000.0, 100_500.0],
        "pnl_history": [100.0, -200.0, 300.0],
    }

    block = build_performance_block(runtime=runtime, state_dir=state_dir)
    assert block is not None
    assert block["session_kpis"]["winrate"] == pytest.approx(2 / 3)
    assert block["session_kpis"]["realized_pnl_session"] == 200.0


def test_build_performance_block_fallback_to_last_run_summary(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "last_run_summary.json").write_text(
        json.dumps(
            {
                "win_rate": 0.58,
                "sharpe_annualized": 1.15,
                "max_drawdown": 420.0,
                "pnl_realized": 1800.0,
            }
        ),
        encoding="utf-8",
    )

    block = build_performance_block(runtime={}, state_dir=state_dir)
    assert block is not None
    assert block["source"] == "fallback"
    assert block["session_kpis"]["winrate"] == 0.58
    assert block["session_kpis"]["sharpe_annualized"] == 1.15
    assert block["session_kpis"]["max_drawdown_usd"] == 420.0


def test_build_performance_block_includes_daily_history(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "monitoring_daily_pnl.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"timestamp": "2026-05-17T00:00:00Z", "daily_pnl": 100.0}),
                json.dumps({"timestamp": "2026-05-18T00:00:00Z", "daily_pnl": -50.0}),
                json.dumps({"timestamp": "2026-05-19T00:00:00Z", "daily_pnl": 200.0}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    block = build_performance_block(
        runtime={"account_equity": 100_000.0, "daily_pnl": 200.0, "open_pnl": 0.0},
        state_dir=state_dir,
    )
    assert block is not None
    assert len(block["daily_history"]) == 3
    assert block["daily_history"][-1]["daily_pnl"] == 200.0


def test_build_performance_block_null_when_no_data(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    assert build_performance_block(runtime={}, state_dir=state_dir) is None
