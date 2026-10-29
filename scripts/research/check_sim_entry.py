"""Exit 0 only when S3 sim_gate criteria pass on bound or JSON evidence.

Fails closed: missing file, synthetic survivors, supervisor armed, REAL HMAC.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping, Sequence

from lumina_core.order_gatekeeper.ungated_place_block import assert_validation_gate_or_block
from lumina_core.research_bridge.sim_gate import (
    SimGateContext,
    SurvivorRecord,
    evaluate,
)


def _record(raw: Mapping[str, object]) -> SurvivorRecord:
    returns_raw = raw.get("returns") or ()
    returns = tuple(float(item) for item in returns_raw) if isinstance(returns_raw, Sequence) else ()
    return SurvivorRecord(
        hypothesis_id=str(raw.get("hypothesis_id") or ""),
        config_id=str(raw.get("config_id") or ""),
        family=str(raw.get("family") or ""),
        instrument=str(raw.get("instrument") or ""),
        stage=str(raw.get("stage") or "active"),
        tape_kind=str(raw.get("tape_kind") or "synthetic"),
        passed_validation_gate=raw.get("passed_validation_gate") is True,
        expected_horizon_bars=int(raw.get("expected_horizon_bars") or 0),
        fill_history_bars=int(raw.get("fill_history_bars") or 0),
        returns=returns,
        validation_mac=str(raw.get("validation_mac") or ""),
        report_sha256=str(raw.get("report_sha256") or ""),
        promotion_gate_promoted=raw.get("promotion_gate_promoted") is True,
    )


def context_from_mapping(payload: Mapping[str, object]) -> SimGateContext:
    survivors_raw = payload.get("survivors") or ()
    rows = tuple(_record(item) for item in survivors_raw if isinstance(item, Mapping))
    live_release = payload.get("live_release_record")
    record = dict(live_release) if isinstance(live_release, Mapping) else None
    whitelist_raw = payload.get("whitelist") or ()
    whitelist = tuple(str(item) for item in whitelist_raw) if isinstance(whitelist_raw, Sequence) else ()
    far = payload.get("far_healthy")
    far_value = float(far) if isinstance(far, (int, float)) and not isinstance(far, bool) else None
    return SimGateContext(
        research_execution_mode_boot=str(payload.get("research_execution_mode_boot") or "off"),
        trade_mode=str(payload.get("trade_mode") or "sim"),
        sim_real_guard_env=payload.get("sim_real_guard_env") is True,
        connected_account=str(payload.get("connected_account") or ""),
        whitelist=whitelist,
        live_release_record=record,
        instrument=str(payload.get("instrument") or "MES"),
        survivors=rows,
        far_healthy=far_value,
        promotion_hmac_ok=payload.get("promotion_hmac_ok") is True,
        approval_required=payload.get("approval_required") is not False,
        approval_present=payload.get("approval_present") is True,
        market_connected=payload.get("market_connected") is True,
        equity_snapshot_stale=payload.get("equity_snapshot_stale") is True,
        yaml_mode_now=str(payload.get("yaml_mode_now") or ""),
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="S3 sim_gate entry check")
    parser.add_argument("--evidence", type=Path, default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.evidence is None or not args.evidence.is_file():
        print("research_sim_gated: evidence missing", file=sys.stderr)
        return 1
    payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print("research_sim_gated: evidence not object", file=sys.stderr)
        return 1
    ctx = context_from_mapping(payload)
    ok, reason = evaluate(ctx)
    blocked, freeze_reason = assert_validation_gate_or_block(
        "supervisor_tick_exec.run_tick_exec",
        order_side="BUY",
        live_position_qty=0,
        order_qty=1,
    )
    if blocked is True:
        print("supervisor_not_blocked", file=sys.stderr)
        return 1
    if freeze_reason != "UNGATED_PLACE_BLOCKED_S0":
        print(f"supervisor_reason:{freeze_reason}", file=sys.stderr)
        return 1
    if ok is not True:
        print(reason, file=sys.stderr)
        return 1
    print(reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
