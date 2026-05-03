from __future__ import annotations

from types import SimpleNamespace

import pytest

from lumina_core.risk.admission_chain import (
    ADMISSION_STEP_AUDIT_WRITE,
    ADMISSION_STEP_CONSTITUTION,
    ADMISSION_STEP_RISK_POLICY,
    CANONICAL_ADMISSION_STEPS,
    AdmissionChain,
    AdmissionContext,
    default_chain_for_mode,
)
from lumina_core.risk.final_arbitration import FinalArbitration
from lumina_core.risk.risk_policy import RiskPolicy
from lumina_core.risk.schemas import ArbitrationState, OrderIntent, OrderIntentMetadata


def _engine_with_logger(messages: list[str]) -> SimpleNamespace:
    return SimpleNamespace(
        app=SimpleNamespace(
            logger=SimpleNamespace(
                warning=lambda message: messages.append(str(message)),
            )
        )
    )


@pytest.mark.unit
def test_default_chain_for_real_mode_keeps_equity_before_final_arbitration() -> None:
    # gegeven
    chain = default_chain_for_mode("real")

    # wanneer
    steps = tuple(chain.steps)

    # dan
    assert steps == CANONICAL_ADMISSION_STEPS


@pytest.mark.unit
def test_admission_chain_allows_sim_bypass_with_logging() -> None:
    # gegeven
    warnings: list[str] = []
    chain = AdmissionChain(steps=(ADMISSION_STEP_CONSTITUTION, ADMISSION_STEP_RISK_POLICY))
    context = AdmissionContext(
        engine=_engine_with_logger(warnings),
        mode="sim",
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
        step_handlers={
            ADMISSION_STEP_CONSTITUTION: lambda _ctx: (False, "constitution_block"),
            ADMISSION_STEP_RISK_POLICY: lambda _ctx: (True, "risk_ok"),
        },
        experimental_bypass_step_ids=frozenset({ADMISSION_STEP_CONSTITUTION}),
    )

    # wanneer
    allowed, reason, trace = chain.run(context)

    # dan
    assert allowed is True
    assert reason == "risk_ok"
    assert trace.results[0].bypassed is True
    assert "ADMISSION_EXPERIMENTAL_BYPASS" in warnings[0]


@pytest.mark.unit
def test_admission_chain_blocks_real_mode_bypass_fail_closed() -> None:
    # gegeven
    warnings: list[str] = []
    chain = AdmissionChain(steps=(ADMISSION_STEP_CONSTITUTION,))
    context = AdmissionContext(
        engine=_engine_with_logger(warnings),
        mode="real",
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
        step_handlers={ADMISSION_STEP_CONSTITUTION: lambda _ctx: (True, "ok")},
        experimental_bypass_step_ids=frozenset({ADMISSION_STEP_CONSTITUTION}),
    )

    # wanneer
    allowed, reason, trace = chain.run(context)

    # dan
    assert allowed is False
    assert reason.startswith("experimental_bypass_forbidden_in_real")
    assert trace.results[-1].step_id == ADMISSION_STEP_CONSTITUTION
    assert warnings == []


@pytest.mark.unit
def test_admission_chain_blocks_when_step_handler_missing() -> None:
    # gegeven
    chain = AdmissionChain(steps=(ADMISSION_STEP_CONSTITUTION, ADMISSION_STEP_RISK_POLICY))
    context = AdmissionContext(
        engine=_engine_with_logger([]),
        mode="sim",
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
        step_handlers={ADMISSION_STEP_CONSTITUTION: lambda _ctx: (True, "constitution_ok")},
    )

    # wanneer
    allowed, reason, trace = chain.run(context)

    # dan
    assert allowed is False
    assert reason == f"admission_step_handler_missing:{ADMISSION_STEP_RISK_POLICY}"
    assert trace.last_step_id == ADMISSION_STEP_RISK_POLICY


@pytest.mark.unit
def test_admission_chain_blocks_on_denied_step_without_bypass() -> None:
    # gegeven
    chain = AdmissionChain(steps=(ADMISSION_STEP_CONSTITUTION, ADMISSION_STEP_RISK_POLICY))
    context = AdmissionContext(
        engine=_engine_with_logger([]),
        mode="sim",
        symbol="MES JUN26",
        regime="NEUTRAL",
        proposed_risk=50.0,
        step_handlers={
            ADMISSION_STEP_CONSTITUTION: lambda _ctx: (True, "constitution_ok"),
            ADMISSION_STEP_RISK_POLICY: lambda _ctx: (False, "risk_block"),
        },
    )

    # wanneer
    allowed, reason, trace = chain.run(context)

    # dan
    assert allowed is False
    assert reason == "risk_block"
    assert trace.last_step_id == ADMISSION_STEP_RISK_POLICY
    assert trace.approved is False


@pytest.mark.unit
def test_admission_chain_is_modular_for_custom_experimental_steps() -> None:
    # gegeven
    execution_order: list[str] = []
    custom_step = "agent_experiment"
    chain = AdmissionChain(steps=(ADMISSION_STEP_CONSTITUTION, custom_step, ADMISSION_STEP_AUDIT_WRITE))

    def _constitution_step(_ctx: AdmissionContext) -> tuple[bool, str]:
        execution_order.append(ADMISSION_STEP_CONSTITUTION)
        return True, "ok"

    def _custom_step(_ctx: AdmissionContext) -> tuple[bool, str]:
        execution_order.append(custom_step)
        return True, "experiment_ok"

    def _audit_step(_ctx: AdmissionContext) -> tuple[bool, str]:
        execution_order.append(ADMISSION_STEP_AUDIT_WRITE)
        return True, "audit_ok"

    context = AdmissionContext(
        engine=_engine_with_logger([]),
        mode="sim",
        symbol="MES JUN26",
        regime="TREND",
        proposed_risk=75.0,
        step_handlers={
            ADMISSION_STEP_CONSTITUTION: _constitution_step,
            custom_step: _custom_step,
            ADMISSION_STEP_AUDIT_WRITE: _audit_step,
        },
    )

    # wanneer
    allowed, _reason, trace = chain.run(context)

    # dan
    assert allowed is True
    assert execution_order == [ADMISSION_STEP_CONSTITUTION, custom_step, ADMISSION_STEP_AUDIT_WRITE]
    assert [result.step_id for result in trace.results] == execution_order


@pytest.mark.unit
def test_final_arbitration_keeps_equity_snapshot_check_even_when_other_checks_skip() -> None:
    # gegeven
    arbitration = FinalArbitration(
        RiskPolicy(
            runtime_mode="real",
            daily_loss_cap=-1000.0,
            max_open_risk_per_instrument=1000.0,
            max_total_open_risk=4000.0,
            var_95_limit_usd=2500.0,
            var_99_limit_usd=3000.0,
            es_95_limit_usd=2800.0,
            es_99_limit_usd=3200.0,
            margin_min_confidence=0.5,
        )
    )
    intent = OrderIntent(
        instrument="MES",
        side="BUY",
        quantity=1,
        proposed_risk=25.0,
        reference_price=5100.0,
        stop=5075.0,
        confidence=0.8,
        source_agent="unit-test",
        metadata=OrderIntentMetadata(reason="admission_chain"),
    )
    state = ArbitrationState(
        runtime_mode="real",
        equity_snapshot_ok=True,
        equity_snapshot_reason="ok",
        account_equity=25_000.0,
        free_margin=12_500.0,
        used_margin=2_500.0,
        margin_confidence=0.9,
        drawdown_pct=2.0,
        drawdown_kill_percent=25.0,
        daily_pnl=300.0,
        total_open_risk=100.0,
    )

    # wanneer
    result = arbitration.check_order_intent(
        intent,
        state,
        skip_internal_steps=frozenset({"constitution", "risk_policy", "real_equity_snapshot"}),
    )

    # dan
    assert result.status == "APPROVED"
    check_reasons = {check.name: check.reason for check in result.checks}
    assert check_reasons["constitution"] == "skipped_by_admission_chain"
    assert check_reasons["risk_policy"] == "skipped_by_admission_chain"
    assert check_reasons["real_equity_snapshot"] == "ok"
