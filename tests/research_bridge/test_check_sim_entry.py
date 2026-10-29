"""check_sim_entry.py exits 0 only when S3 criteria pass."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import importlib.util

from tests.research_bridge.s3_helpers import passing_context


def _load_main():
    path = Path(__file__).resolve().parents[2] / "scripts" / "research" / "check_sim_entry.py"
    spec = importlib.util.spec_from_file_location("check_sim_entry_s3", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


def _dump(ctx_payload: dict[str, object], path: Path) -> Path:
    path.write_text(json.dumps(ctx_payload), encoding="utf-8")
    return path


def _payload_from_context() -> dict[str, object]:
    ctx = passing_context()
    return {
        "research_execution_mode_boot": ctx.research_execution_mode_boot,
        "trade_mode": ctx.trade_mode,
        "sim_real_guard_env": ctx.sim_real_guard_env,
        "connected_account": ctx.connected_account,
        "whitelist": list(ctx.whitelist),
        "live_release_record": ctx.live_release_record,
        "instrument": ctx.instrument,
        "survivors": [
            {
                "hypothesis_id": row.hypothesis_id,
                "config_id": row.config_id,
                "family": row.family,
                "instrument": row.instrument,
                "stage": row.stage,
                "tape_kind": row.tape_kind,
                "passed_validation_gate": row.passed_validation_gate,
                "expected_horizon_bars": row.expected_horizon_bars,
                "fill_history_bars": row.fill_history_bars,
                "returns": list(row.returns),
                "validation_mac": row.validation_mac,
                "report_sha256": row.report_sha256,
                "promotion_gate_promoted": row.promotion_gate_promoted,
            }
            for row in ctx.survivors
        ],
        "use_fixture_daily_tape": True,
        "promotion_hmac_ok": ctx.promotion_hmac_ok,
        "approval_required": ctx.approval_required,
        "approval_present": ctx.approval_present,
        "market_connected": ctx.market_connected,
        "equity_snapshot_stale": ctx.equity_snapshot_stale,
    }


@pytest.mark.unit
def test_check_sim_entry_ok_and_fail(tmp_path: Path) -> None:
    main = _load_main()
    good = _dump(_payload_from_context(), tmp_path / "good.json")
    assert main(["--evidence", str(good)]) == 0
    bad = _payload_from_context()
    bad["survivors"] = []
    bad_path = _dump(bad, tmp_path / "bad.json")
    assert main(["--evidence", str(bad_path)]) == 1
    assert main([]) == 1
    invented = _payload_from_context()
    invented["far_healthy"] = 0.02
    invented.pop("use_fixture_daily_tape", None)
    invented_path = _dump(invented, tmp_path / "far.json")
    assert main(["--evidence", str(invented_path)]) == 1
