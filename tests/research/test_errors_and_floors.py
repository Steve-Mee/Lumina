"""Error branches, threshold floors, and remaining fail-closed paths."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from lumina_research.risk_core.config import RiskConfig, RiskConfigError
from lumina_research.risk_core.types import DecisionKind, decision_label
from lumina_research.validation.audit import default_audit_path
from lumina_research.validation.contracts import spec_for
from lumina_research.validation.cost_model import CostModel, CostModelError, MarketSnapshot, apply_costs
from lumina_research.validation.cpcv import assign_groups, reconstruct_paths
from lumina_research.validation.pbo import PBOError, probability_of_backtest_overfitting
from lumina_research.validation.regimes import regime_robustness
from lumina_research.validation.thresholds import ThresholdConfigError, load_thresholds
from lumina_research.validation.walk_forward import WalkForwardConfig, WalkForwardError, parameter_stability


@pytest.mark.unit
def test_threshold_file_cannot_weaken_or_add_keys(tmp_path: Path) -> None:
    weak = tmp_path / "weak.toml"
    weak.write_text(
        "dsr_probability_min = 0.1\nwfe_min = 0.5\npbo_hard_reject = 0.50\npbo_warning = 0.25\nmin_oos_windows = 6\n",
        encoding="utf-8",
    )
    with pytest.raises(ThresholdConfigError):
        load_thresholds(weak)
    extra = tmp_path / "extra.toml"
    extra.write_text(
        "dsr_probability_min = 0.95\nwfe_min = 0.5\npbo_hard_reject = 0.50\npbo_warning = 0.25\nmin_oos_windows = 6\nextra = 1\n",
        encoding="utf-8",
    )
    with pytest.raises(ThresholdConfigError):
        load_thresholds(extra)


@pytest.mark.unit
def test_contracts_cost_cpcv_pbo_walk_forward_errors() -> None:
    with pytest.raises(Exception, match="unsupported"):
        spec_for("CL")
    with pytest.raises(CostModelError):
        CostModel(slippage_coefficient=-0.1)
    with pytest.raises(CostModelError):
        apply_costs(
            gross_returns=(0.01,),
            positions=(1.0, 2.0),
            equity=1.0,
            spec="MES",
            markets=(MarketSnapshot(1.0, 1.0, 1.0),),
        )
    with pytest.raises(Exception):
        reconstruct_paths(4, [])
    with pytest.raises(Exception):
        assign_groups(2, 3)
    with pytest.raises(PBOError):
        probability_of_backtest_overfitting([[1.0, 2.0, 3.0], [1.0, 2.0, 3.0]])
    with pytest.raises(WalkForwardError):
        WalkForwardConfig(is_size=20, oos_size=10, mode="rolling", min_oos_windows=5)
    assert math.isnan(parameter_stability(({"a": 1.0},)))
    missing = regime_robustness((0.01, -0.01, 0.02))
    assert math.isnan(missing.robustness)


@pytest.mark.unit
def test_decision_label_and_audit_default_and_nan_config() -> None:
    assert decision_label(DecisionKind.APPROVED) == "approved"
    assert decision_label(DecisionKind.REJECTED) == "rejected"
    assert decision_label(DecisionKind.SCALED) == "scaled"
    assert default_audit_path().name.endswith(".jsonl")
    with pytest.raises(RiskConfigError):
        RiskConfig(
            max_position_pct=float("nan"),
            max_daily_loss_pct=0.02,
            max_total_drawdown_pct=0.1,
            leverage_cap=4.0,
            correlation_cluster_limit_pct=0.15,
            heartbeat_timeout_sec=30.0,
            min_quantity=1.0,
        )
