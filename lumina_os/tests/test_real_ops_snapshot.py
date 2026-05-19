from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.real_ops_snapshot import build_real_ops_block, window_metrics  # noqa: E402


def test_window_metrics_aggregates_summary(tmp_path: Path) -> None:
    summary = {"pnl_realized": 100.0, "total_trades": 10, "wins": 6, "sharpe_annualized": 1.2}
    metrics = window_metrics(summary, [], 7)
    assert metrics["pnl"] == 100.0
    assert metrics["win_rate"] == 0.6


def test_build_real_ops_block_protocol_gates(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "last_run_summary.json").write_text(
        json.dumps(
            {
                "pnl_realized": 500.0,
                "max_drawdown": 200.0,
                "risk_events": 0,
                "var_breach_count": 0,
                "sharpe_annualized": 1.5,
                "win_rate": 0.65,
                "total_trades": 20,
            }
        ),
        encoding="utf-8",
    )
    block = build_real_ops_block(
        runtime={"live_position_qty": 2, "pending_reconciliations": 0},
        state_dir=state,
    )
    assert block is not None
    assert block["capital_preservation"]["protocol_green"] is True
    assert block["window_pnl"]["d7"] == 500.0
