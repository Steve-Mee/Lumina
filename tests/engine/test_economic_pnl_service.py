"""Tests for broker-only EconomicPnLService and REAL risk provenance."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from lumina_core.engine.economic_pnl_service import EconomicPnLService, reject_if_training_metrics
from lumina_core.engine.golden_ledger import round_turn_realized_from_two_fills
from lumina_core.engine.valuation_engine import ValuationEngine
from lumina_core.risk.pnl_provenance import PnlProvenance
from lumina_core.risk.risk_controller import HardRiskController, RiskLimits


@pytest.mark.unit
def test_round_turn_matches_golden_ledger_direct() -> None:
    ve = ValuationEngine()
    svc = EconomicPnLService(ve)
    direct = round_turn_realized_from_two_fills(
        valuation_engine=ve,
        symbol="MES JUN26",
        entry_fill_price=5000.0,
        exit_fill_price=5002.0,
        open_side="BUY",
        quantity=1,
        entry_commission=1.0,
        exit_commission=1.0,
    )
    via = svc.round_turn_realized_usd_from_broker_fills(
        symbol="MES JUN26",
        entry_fill_price=5000.0,
        exit_fill_price=5002.0,
        open_side="BUY",
        quantity=1,
        entry_commission=1.0,
        exit_commission=1.0,
    )
    assert via == pytest.approx(direct)


@pytest.mark.unit
def test_reject_if_training_metrics_raises() -> None:
    with pytest.raises(ValueError, match="training_reward"):
        reject_if_training_metrics({"economic_pnl_usd": 1.0, "training_reward": 0.1})


@pytest.mark.unit
def test_economic_pnl_from_reconciled_payload_accepts_clean_dict() -> None:
    svc = EconomicPnLService()
    v = svc.economic_pnl_from_reconciled_payload({"economic_pnl_usd": 42.5})
    assert v == pytest.approx(42.5)


@pytest.mark.unit
def test_real_mode_record_trade_skips_non_broker_provenance() -> None:
    ctrl = HardRiskController(RiskLimits())
    ctrl.record_trade_result(
        "MES",
        "TRENDING",
        100.0,
        10.0,
        trade_mode="real",
        pnl_provenance=PnlProvenance.SIM_INTERNAL,
    )
    assert ctrl.state.daily_pnl == pytest.approx(0.0)
    ctrl.record_trade_result(
        "MES",
        "TRENDING",
        25.0,
        10.0,
        trade_mode="real",
        pnl_provenance=PnlProvenance.BROKER_RECONCILED,
    )
    assert ctrl.state.daily_pnl == pytest.approx(25.0)


@pytest.mark.unit
def test_risk_python_sources_do_not_reference_training_reward() -> None:
    root = Path(__file__).resolve().parents[2] / "lumina_core" / "risk"
    for path in sorted(root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "training_reward" not in text, f"forbidden RL token in {path}"


def _training_reward_allowed_under_lumina_core(rel: Path) -> bool:
    parts = rel.parts
    if parts[:1] == ("rl",):
        return True
    if len(parts) >= 2 and parts[0] == "engine" and parts[1] == "rl":
        return True
    if parts == ("engine", "economic_pnl_service.py"):
        return True
    return False


_TRAINING_REWARD_ID = re.compile(r"(?<![A-Za-z0-9_])training_reward(?![A-Za-z0-9_])")


@pytest.mark.unit
def test_lumina_core_non_rl_modules_exclude_training_reward_token() -> None:
    """Identifier ``training_reward`` must not appear outside RL packages and the economic reject list."""
    root = Path(__file__).resolve().parents[2] / "lumina_core"
    offenders: list[str] = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root)
        if _training_reward_allowed_under_lumina_core(rel):
            continue
        text = path.read_text(encoding="utf-8")
        if _TRAINING_REWARD_ID.search(text):
            offenders.append(str(rel).replace("\\", "/"))
    assert not offenders, (
        "training_reward must not appear outside lumina_core/rl/, lumina_core/engine/rl/, "
        "and lumina_core/engine/economic_pnl_service.py — got: " + ", ".join(offenders)
    )
