from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.validation.run_sim_real_guard_rollout_b import _build_rollout_decision, _build_window_report


def _write_metrics_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            """CREATE TABLE IF NOT EXISTS metrics (
               ts REAL NOT NULL,
               name TEXT NOT NULL,
               labels TEXT NOT NULL,
               type TEXT NOT NULL,
               value REAL NOT NULL
            )"""
        )
        rows = [
            (
                1.0,
                "lumina_mode_guard_block_total",
                json.dumps({"mode": "sim_real_guard", "reason": "risk_daily_loss_cap"}),
                "counter",
                2.0,
            ),
            (1.0, "lumina_mode_eod_force_close_total", json.dumps({"mode": "sim_real_guard"}), "counter", 1.0),
            (
                1.0,
                "lumina_mode_parity_drift_total",
                json.dumps({"baseline": "real", "candidate": "sim_real_guard"}),
                "counter",
                0.4,
            ),
        ]
        con.executemany("INSERT INTO metrics(ts, name, labels, type, value) VALUES (?,?,?,?,?)", rows)
        con.commit()
    finally:
        con.close()


def test_build_window_report_extracts_automated_parity_evidence(tmp_path: Path) -> None:
    control_root = tmp_path / "control"
    candidate_root = tmp_path / "candidate"
    (control_root / "state").mkdir(parents=True, exist_ok=True)
    (control_root / "logs").mkdir(parents=True, exist_ok=True)
    (candidate_root / "state").mkdir(parents=True, exist_ok=True)
    (candidate_root / "logs").mkdir(parents=True, exist_ok=True)

    (control_root / "state" / "last_run_summary.json").write_text(json.dumps({"mode": "sim"}), encoding="utf-8")
    (candidate_root / "state" / "last_run_summary.json").write_text(
        json.dumps({"mode": "sim_real_guard"}), encoding="utf-8"
    )
    (candidate_root / "state" / "trade_reconciler_status.json").write_text(
        json.dumps({"pending_count": 0, "last_error": ""}), encoding="utf-8"
    )
    (control_root / "logs" / "lumina_full_log.csv").write_text(
        "2026-04-15,WARNING,RISK_ADVISORY,mode=sim,symbol=MES JUN26,reason=daily_loss_cap\n",
        encoding="utf-8",
    )
    (candidate_root / "logs" / "trade_fill_audit.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"event": "reconciled", "status": "reconciled_fill", "fill_latency_ms": 400.0}),
                json.dumps({"event": "reconciled", "status": "reconciled_fill", "fill_latency_ms": 600.0}),
            ]
        ),
        encoding="utf-8",
    )
    _write_metrics_db(candidate_root / "state" / "metrics.db")

    report = _build_window_report(control_root, candidate_root, "D1_09-30_10-00", "30m")

    assert report["decision"] == "GO_WINDOW"
    assert report["candidate"]["guard_blocks_by_reason"]["risk_daily_loss_cap"] == 2
    assert report["candidate"]["force_close_count"] == 1
    assert report["candidate"]["parity_drift_total"] == 0.4
    assert report["candidate"]["p95_fill_latency_ms"] == 600.0


def test_build_rollout_decision_requires_full_green_history() -> None:
    history = [
        {
            "decision": "GO_WINDOW",
            "candidate": {"timeout_ratio": 0.0, "p95_fill_latency_ms": 800.0, "force_close_count": 0, "last_error": ""},
            "unmatched_candidate_reasons": [],
        }
        for _ in range(15)
    ]

    decision = _build_rollout_decision(history)

    assert decision["ready_for_rollout_c"] is True
    assert decision["decision"] == "GO_TO_ROLLOUT_C"
