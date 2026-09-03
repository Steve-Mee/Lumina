"""Awakening grind: floors pinned, evaluate-only, classifier pins, persist isolation."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from lumina_core.birth.awakening_grind import (
    BIRTH_MEAN_USD,
    BIRTH_N,
    CLASS_INCONCLUSIVE,
    CLASS_REGRESS,
    CLASS_STABLE,
    EvaluateOnlyPolicy,
    OVERALL_INCONCLUSIVE,
    OVERALL_REGRESS,
    OVERALL_STABLE,
    REGRESS_MEAN_USD,
    TRAIN,
    classify_grind_leg,
    classify_overall,
    grind_table_from_rows,
)
from lumina_core.birth.awakening_grind_run import (
    grind_ledger_path,
    run_evaluate_only,
    write_grind_closes,
)
from lumina_core.birth.foundation_metrics import (
    POLICY_EDGE_MIN_TRADES,
    S2_OCCUPANCY_MAX,
    S2_OCCUPANCY_MIN,
    S3_OCCUPANCY_MAX,
    S3_OCCUPANCY_MIN,
    S5_DD_EQUITY_USD,
    S5_DD_MAX_PCT,
    S5_EDGE_MIN,
    S5_MIN_TRADES,
    S5_SHARPE_FLOOR,
)
from lumina_core.birth.notional_cap import birth_gym_point_value
from lumina_core.birth.s5_close_ledger_archive import (
    append_archive_rows,
    archive_line_count,
    resolve_archive_path,
)
from lumina_core.rl.gym_stop_fill import birth_force_qty_one


def test_a_floors_still_pinned_pr14() -> None:
    assert S5_SHARPE_FLOOR == pytest.approx(-2.0)
    assert S5_DD_MAX_PCT == pytest.approx(25.0)
    assert S5_DD_EQUITY_USD == pytest.approx(50_000.0)
    assert S5_EDGE_MIN == pytest.approx(-0.03)
    assert S5_MIN_TRADES == 50
    assert POLICY_EDGE_MIN_TRADES == 150
    assert S2_OCCUPANCY_MIN == pytest.approx(0.30)
    assert S2_OCCUPANCY_MAX == pytest.approx(0.70)
    assert S3_OCCUPANCY_MIN == pytest.approx(0.25)
    assert S3_OCCUPANCY_MAX == pytest.approx(0.75)
    assert birth_gym_point_value() == pytest.approx(5.0)
    assert birth_force_qty_one("stage5_probe_handoff") is True
    assert BIRTH_N == 172
    assert BIRTH_MEAN_USD == pytest.approx(-20.7)
    assert REGRESS_MEAN_USD == pytest.approx(-62.0)
    metrics = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    assert "S5_SHARPE_FLOOR = -2.0" in metrics
    assert "S5_DD_MAX_PCT = 25.0" in metrics
    assert "S5_EDGE_MIN = -0.03" in metrics
    assert "POLICY_EDGE_MIN_TRADES = 150" in metrics
    grind = Path("lumina_core/birth/awakening_grind.py").read_text(encoding="utf-8")
    for token in ("S5_IDLE_REGIMES", "MAX_PLANT", "MAX_TIME_STOP", "if synthetic"):
        assert token not in grind
    complete = Path("lumina_core/birth/foundation_complete.py").read_text(encoding="utf-8")
    assert complete.index("export_birth_exit_pi_star") < complete.index("final_birth_polish")


class _StubPolicy:
    def __init__(self) -> None:
        self.learn_calls = 0
        self.predict_calls = 0

    def predict(self, observation, *, deterministic: bool = True):
        self.predict_calls += 1
        _ = observation, deterministic
        import numpy as np

        return np.array([1.0, 0.0, 0.0012, 0.002], dtype=np.float32), None

    def learn(self, *args: object, **kwargs: object) -> None:
        self.learn_calls += 1


def test_b_evaluator_cannot_train(tmp_path: Path) -> None:
    assert TRAIN is False
    inner = _StubPolicy()
    wrapped = EvaluateOnlyPolicy(inner)
    with pytest.raises(RuntimeError, match="train=False"):
        wrapped.learn(timesteps=1)
    assert inner.learn_calls == 0

    closes = [
        {
            "pnl": -10.0,
            "qty": 1,
            "cap_usd": 500.0,
            "close_reason": "stop",
            "gap": False,
            "plant_entry": False,
            "entry_price": 20000.0,
            "risk_usd": 50.0,
            "trade_r": -0.2,
            "point_value": 5.0,
            "regime": "NEUTRAL",
            "reward_on_close": -0.2,
        }
        for _ in range(3)
    ]

    def _stub_rollout(**kwargs: object) -> SimpleNamespace:
        pol = kwargs["policy"]
        assert isinstance(pol, EvaluateOnlyPolicy)
        assert kwargs["exploration_steps"] == 0
        return SimpleNamespace(
            trades=3,
            wins=0,
            trajectories=closes,
            pnl_series=[-10.0, -10.0, -10.0],
            r_series=[-0.2, -0.2, -0.2],
            plant_trades=0,
            plant_wins=0,
            policy_trades=3,
            policy_wins=0,
            participation_force_open=0,
            range_flat_bars=30,
            range_total_signals=100,
            closes_stop=3,
            closes_target=0,
            closes_time_stop=0,
            closes_flatten=0,
            closes_unknown=0,
            rollout_steps=len(closes),
        )

    ticks = [
        {
            "timestamp": f"2026-09-02T00:00:{i:02d}Z",
            "last": 21150.0 + i,
            "close": 21150.0 + i,
            "bid": 21149.75,
            "ask": 21150.25,
            "volume": 10,
            "regime": "NEUTRAL",
            "source": "synthetic_cloud_fixture",
        }
        for i in range(80)
    ]
    result = run_evaluate_only(
        runtime=SimpleNamespace(),
        holdout=ticks,
        workspace_root=tmp_path,
        reports_dir=tmp_path,
        ledger_path=grind_ledger_path(tmp_path, leg="A"),
        policy=inner,
        rollout_fn=_stub_rollout,
    )
    assert result.train is False
    assert result.optimizer_steps == 0
    assert inner.learn_calls == 0
    assert result.n == 3
    assert archive_line_count(grind_ledger_path(tmp_path, leg="A")) == 3


def test_c_classifier_pins() -> None:
    assert (
        classify_grind_leg(
            n=500,
            oos_sharpe=-1.5,
            oos_dd_pct=20.0,
            mean_usd=-10.0,
            holdout_exhausted=False,
            frozen_loaded=True,
        )
        == CLASS_STABLE
    )
    assert (
        classify_grind_leg(
            n=200,
            oos_sharpe=-1.0,
            oos_dd_pct=10.0,
            mean_usd=-5.0,
            holdout_exhausted=True,
            frozen_loaded=True,
        )
        == CLASS_STABLE
    )
    assert (
        classify_grind_leg(
            n=500,
            oos_sharpe=-3.0,
            oos_dd_pct=10.0,
            mean_usd=-10.0,
            holdout_exhausted=True,
            frozen_loaded=True,
        )
        == CLASS_REGRESS
    )
    assert (
        classify_grind_leg(
            n=500,
            oos_sharpe=-1.0,
            oos_dd_pct=26.0,
            mean_usd=-10.0,
            holdout_exhausted=True,
            frozen_loaded=True,
        )
        == CLASS_REGRESS
    )
    assert (
        classify_grind_leg(
            n=500,
            oos_sharpe=-1.0,
            oos_dd_pct=10.0,
            mean_usd=-62.0,
            holdout_exhausted=True,
            frozen_loaded=True,
        )
        == CLASS_REGRESS
    )
    assert (
        classify_grind_leg(
            n=500,
            oos_sharpe=-1.0,
            oos_dd_pct=10.0,
            mean_usd=-10.0,
            holdout_exhausted=True,
            frozen_loaded=True,
            full_series_dd_pct=51.0,
        )
        == CLASS_REGRESS
    )
    assert (
        classify_grind_leg(
            n=100,
            oos_sharpe=-1.0,
            oos_dd_pct=10.0,
            mean_usd=-10.0,
            holdout_exhausted=True,
            frozen_loaded=True,
        )
        == CLASS_INCONCLUSIVE
    )
    assert (
        classify_grind_leg(
            n=800,
            oos_sharpe=-0.5,
            oos_dd_pct=5.0,
            mean_usd=1.0,
            holdout_exhausted=True,
            frozen_loaded=False,
        )
        == CLASS_INCONCLUSIVE
    )
    assert classify_overall(CLASS_STABLE, CLASS_STABLE) == OVERALL_STABLE
    assert classify_overall(CLASS_STABLE, CLASS_REGRESS) == OVERALL_REGRESS
    assert classify_overall(CLASS_STABLE, CLASS_INCONCLUSIVE) == OVERALL_INCONCLUSIVE


def test_d_persist_grind_does_not_truncate_birth_archive(tmp_path: Path) -> None:
    birth = resolve_archive_path(tmp_path)
    birth_rows = [
        {
            "pnl": -1.0,
            "qty": 1,
            "point_value": 5.0,
            "close_reason": "stop",
            "gap": False,
            "regime": "NEUTRAL",
            "intended_risk_usd": 50.0,
            "trade_r": -0.02,
            "reward_on_close": -0.02,
            "cap_hit": False,
            "stage": "stage5_probe_handoff",
        }
        for _ in range(7)
    ]
    append_archive_rows(birth, birth_rows)
    assert archive_line_count(birth) == 7
    grind = grind_ledger_path(tmp_path, leg="A")
    write_grind_closes(
        grind,
        [
            {
                "pnl": -10.0,
                "qty": 1,
                "cap_usd": 500.0,
                "close_reason": "stop",
                "gap": False,
                "plant_entry": False,
                "entry_price": 20000.0,
                "risk_usd": 50.0,
                "trade_r": -0.2,
                "point_value": 5.0,
                "regime": "TREND_DOWN",
                "reward_on_close": -0.2,
            }
            for _ in range(3)
        ],
    )
    assert archive_line_count(grind) == 3
    assert archive_line_count(birth) == 7
    with pytest.raises(RuntimeError, match="Birth s5 archive"):
        write_grind_closes(birth, [{"pnl": 1.0, "qty": 1, "point_value": 5.0}])


def test_d_missing_frozen_is_inconclusive(tmp_path: Path) -> None:
    ticks = [
        {
            "timestamp": "2026-09-02T00:00:00Z",
            "last": 21150.0,
            "close": 21150.0,
            "bid": 21149.75,
            "ask": 21150.25,
            "volume": 10,
            "regime": "NEUTRAL",
            "source": "synthetic_cloud_fixture",
        }
        for _ in range(40)
    ]
    called = {"n": 0}

    def _boom(**_kwargs: object) -> SimpleNamespace:
        called["n"] += 1
        raise AssertionError("rollout must not run without frozen weights")

    result = run_evaluate_only(
        runtime=SimpleNamespace(),
        holdout=ticks,
        workspace_root=tmp_path,
        reports_dir=tmp_path,
        ledger_path=grind_ledger_path(tmp_path, leg="A"),
        rollout_fn=_boom,
    )
    assert called["n"] == 0
    assert result.classification == CLASS_INCONCLUSIVE
    assert result.frozen_loaded is False
    assert result.n < BIRTH_N


def test_table_reports_realized_r() -> None:
    rows = [
        {
            "pnl": -20.7,
            "trade_r": -0.089,
            "intended_risk_usd": 232.0,
            "close_reason": "stop",
            "gap": False,
            "regime": "TREND_DOWN",
            "cap_hit": False,
            "plant": False,
        }
        for _ in range(172)
    ]
    metrics = grind_table_from_rows(rows, holdout_exhausted=True, frozen_loaded=True)
    assert metrics.n == 172
    assert metrics.realized_r_mean == pytest.approx(-0.089)
    assert metrics.mean_usd == pytest.approx(-20.7)
