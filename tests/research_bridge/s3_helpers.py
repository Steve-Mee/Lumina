"""S3 test fixtures. NT-PIT survivors only; synthetic never counts."""

from __future__ import annotations

import traceback
from collections.abc import Sequence
from datetime import datetime, timezone
from types import SimpleNamespace

from lumina_core.broker.broker_bridge.schemas import Order, OrderResult
from lumina_core.research_bridge.sim_gate import SimGateContext, SurvivorRecord, bind_sim_gate

_HEX = "a" * 64
_HEX_B = "b" * 64


class RecordingSubmitter:
    def __init__(self, *, accept: bool = True) -> None:
        self.orders: list[Order] = []
        self.accept = accept
        self.stack_at_submit: list[str] = []

    def submit_order(self, order: Order) -> OrderResult:
        self.stack_at_submit = traceback.format_stack()
        self.orders.append(order)
        if self.accept is not True:
            return OrderResult(accepted=False, order_id="", status="rejected", message="admission_blocked")
        return OrderResult(accepted=True, order_id="sim-1", status="accepted", message="ok")


def _returns(seed: int, n: int = 16) -> tuple[float, ...]:
    sign = 1.0 if seed % 2 == 0 else -1.0
    return tuple(sign * (0.01 if index % 2 == 0 else -0.004) for index in range(n))


def survivor(*, tag: str, family: str, instrument: str = "MES", tape_kind: str = "nt_pit") -> SurvivorRecord:
    seed = sum(ord(ch) for ch in tag)
    return SurvivorRecord(
        hypothesis_id=f"hyp-{tag}",
        config_id=f"cfg-{tag}",
        family=family,
        instrument=instrument,
        stage="active",
        tape_kind=tape_kind,
        passed_validation_gate=True,
        expected_horizon_bars=8,
        fill_history_bars=24,
        returns=_returns(seed),
        validation_mac=_HEX if tag != "b" else _HEX_B,
        report_sha256=_HEX_B if tag != "b" else _HEX,
        promotion_gate_promoted=True,
    )


def passing_context(
    *,
    survivors: Sequence[SurvivorRecord] | None = None,
    instrument: str = "MES",
    trade_mode: str = "sim_real_guard",
    boot: str = "sim",
    far: float | None = 0.02,
    yaml_now: str = "sim",
    stale: bool = False,
    reduce_only: bool = False,
    live_release: dict[str, object] | None = None,
    connected: str = "Sim101",
    whitelist: tuple[str, ...] = ("Sim101",),
    env: bool = True,
    hmac_ok: bool = True,
    market: bool = True,
    approval_required: bool = True,
    approval_present: bool = True,
) -> SimGateContext:
    rows = tuple(survivors) if survivors is not None else (survivor(tag="a", family="trend"), survivor(tag="b", family="meanrev", instrument="MNQ"))
    return SimGateContext(
        research_execution_mode_boot=boot,
        trade_mode=trade_mode,
        sim_real_guard_env=env,
        connected_account=connected,
        whitelist=whitelist,
        live_release_record=live_release,
        instrument=instrument,
        survivors=rows,
        far_healthy=far,
        promotion_hmac_ok=hmac_ok,
        approval_required=approval_required,
        approval_present=approval_present,
        market_connected=market,
        equity_snapshot_stale=stale,
        reduce_only=reduce_only,
        yaml_mode_now=yaml_now,
    )


def bind_passing() -> SimGateContext:
    ctx = passing_context()
    bind_sim_gate(ctx)
    return ctx


def fake_engine() -> SimpleNamespace:
    return SimpleNamespace(config=SimpleNamespace(trade_mode="sim_real_guard", instrument="MES"))


UTC = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
