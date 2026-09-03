"""Awakening mechanism Gate 0 splitter + trigger pins. Floors stay PR #14."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.awakening_grind import BIRTH_N, REGRESS_MEAN_USD, TRAIN
from lumina_core.birth.awakening_grind_run import s5_envelope_kwargs
from lumina_core.birth.awakening_mech import (
    GATE1_NONE,
    GATE1_WIRE_BIRTH_PARTICIPATION,
    GATE1_WIRE_CHATTER_BOUND,
    MECH_MEASURE_ONLY,
    compute_both_bad,
    compute_pe_flags,
    compute_w_wire,
    evaluate_book,
    inspect_grind_live_path,
    load_close_jsonl,
    occupancy_band_fractions,
    row_is_force_open,
    row_is_plant,
    select_gate1_law,
    split_table,
)
from lumina_core.birth.birth_exit_policy_export import (
    candidate_frozen_paths,
    load_frozen_policy,
    resolve_frozen_policy_path,
)
from lumina_core.birth.config_curriculum import BirthCurriculumConfig
from lumina_core.birth.foundation_metrics import (
    POLICY_EDGE_MIN_TRADES,
    S5_DD_MAX_PCT,
    S5_SHARPE_FLOOR,
)
from lumina_core.birth.notional_cap import birth_gym_point_value
from lumina_core.birth.s5_close_ledger_trace import close_ledger_row
from lumina_core.rl.gym_stop_fill import birth_force_qty_one


def test_a_floors_pinned_pr14() -> None:
    assert S5_SHARPE_FLOOR == pytest.approx(-2.0)
    assert S5_DD_MAX_PCT == pytest.approx(25.0)
    assert POLICY_EDGE_MIN_TRADES == 150
    assert birth_gym_point_value() == pytest.approx(5.0)
    assert birth_force_qty_one("stage5_probe_handoff") is True
    assert BIRTH_N == 172
    assert REGRESS_MEAN_USD == pytest.approx(-62.0)
    assert TRAIN is False
    metrics = Path("lumina_core/birth/foundation_metrics.py").read_text(encoding="utf-8")
    grind = Path("lumina_core/birth/awakening_grind.py").read_text(encoding="utf-8")
    mech = Path("lumina_core/birth/awakening_mech.py").read_text(encoding="utf-8")
    assert "S5_SHARPE_FLOOR = -2.0" in metrics
    assert "S5_DD_MAX_PCT = 25.0" in metrics
    assert "POLICY_EDGE_MIN_TRADES = 150" in metrics
    for token in ("S5_IDLE_REGIMES", "MAX_PLANT", "MAX_TIME_STOP", "if synthetic"):
        assert token not in grind
        assert token not in mech


def _row(
    *,
    pnl: float,
    plant: bool = False,
    force_open: bool = False,
    trade_r: float = 0.0,
    close_reason: str = "stop",
    gap: bool = False,
    regime: str = "NEUTRAL",
    cap_hit: bool = False,
) -> dict[str, object]:
    return {
        "pnl": pnl,
        "plant": plant,
        "force_open": force_open,
        "trade_r": trade_r,
        "close_reason": close_reason,
        "gap": gap,
        "regime": regime,
        "cap_hit": cap_hit,
        "qty": 1,
        "point_value": 5.0,
        "intended_risk_usd": 50.0,
    }


def test_b_splitter_ten_row_fixture_totals() -> None:
    rows = [
        _row(pnl=10.0, trade_r=0.2, close_reason="target"),
        _row(pnl=-20.0, trade_r=-0.4, close_reason="stop"),
        _row(pnl=5.0, trade_r=0.1, close_reason="target", regime="TREND_UP"),
        _row(pnl=-15.0, trade_r=-0.3, close_reason="time_stop", regime="TREND_DOWN"),
        _row(pnl=-50.0, force_open=True, trade_r=-1.0, close_reason="stop"),
        _row(pnl=-30.0, force_open=True, trade_r=-0.6, close_reason="stop"),
        _row(pnl=20.0, force_open=True, trade_r=0.4, close_reason="target", regime="TREND_UP"),
        _row(pnl=-40.0, plant=True, trade_r=-0.8, close_reason="stop", regime="TREND_DOWN"),
        _row(pnl=8.0, plant=True, trade_r=0.16, close_reason="target"),
        _row(
            pnl=-25.0,
            plant=True,
            force_open=True,
            trade_r=-0.5,
            close_reason="stop",
            cap_hit=True,
        ),
    ]
    assert len(rows) == 10
    table = split_table(rows)
    policy = table["policy"]
    assert policy["n"] == pytest.approx(4.0)
    assert policy["wr"] == pytest.approx(0.5)
    assert policy["sum_usd"] == pytest.approx(-20.0)
    assert policy["mean_usd"] == pytest.approx(-5.0)
    assert policy["mean_r"] == pytest.approx(-0.1)
    assert policy["stop"] == pytest.approx(1.0)
    assert policy["target"] == pytest.approx(2.0)
    assert policy["time_stop"] == pytest.approx(1.0)
    assert policy["cap_hit"] == pytest.approx(0.0)
    force = table["force_open"]
    assert force["n"] == pytest.approx(4.0)
    assert force["wr"] == pytest.approx(0.25)
    assert force["sum_usd"] == pytest.approx(-85.0)
    assert force["mean_usd"] == pytest.approx(-21.25)
    assert force["mean_r"] == pytest.approx(-0.425)
    assert force["stop"] == pytest.approx(3.0)
    assert force["target"] == pytest.approx(1.0)
    assert force["cap_hit"] == pytest.approx(1.0)
    plant = table["plant"]
    assert plant["n"] == pytest.approx(3.0)
    assert plant["wr"] == pytest.approx(1.0 / 3.0)
    assert plant["sum_usd"] == pytest.approx(-57.0)
    assert plant["mean_usd"] == pytest.approx(-19.0)
    assert plant["mean_r"] == pytest.approx(-1.14 / 3.0)
    assert plant["stop"] == pytest.approx(2.0)
    assert plant["target"] == pytest.approx(1.0)
    assert plant["cap_hit"] == pytest.approx(1.0)
    overlap = table["overlap"]
    assert overlap["n"] == pytest.approx(1.0)
    assert overlap["sum_usd"] == pytest.approx(-25.0)
    assert overlap["mean_r"] == pytest.approx(-0.5)
    assert overlap["cap_hit"] == pytest.approx(1.0)
    overall = table["all"]
    assert overall["n"] == pytest.approx(10.0)
    assert overall["sum_usd"] == pytest.approx(-137.0)
    counted = int(policy["n"] + force["n"] + plant["n"] - overlap["n"])
    assert counted == 10


def _book(n: int, *, pnl: float, trade_r: float, plant: bool = False, force: bool = False) -> list[dict[str, object]]:
    return [_row(pnl=pnl, trade_r=trade_r, plant=plant, force_open=force) for _ in range(n)]


def test_c_trigger_p_participation() -> None:
    rows = _book(50, pnl=-10.0, trade_r=-0.05) + _book(50, pnl=-100.0, trade_r=-0.5, plant=True, force=True)
    pe = compute_pe_flags(rows)
    assert pe["P_PARTICIPATION"] is True
    assert pe["E_EDGE"] is False
    assert pe["union_frac"] == pytest.approx(0.5)
    assert pe["n_policy"] == 50
    assert pe["policy_mean_usd"] > pe["overall_mean_usd"]
    assert (
        select_gate1_law(p_participation=True, e_edge=False, w_wire=False, both_bad=False) == GATE1_WIRE_CHATTER_BOUND
    )


def test_c_trigger_e_edge() -> None:
    rows = _book(80, pnl=-20.0, trade_r=-0.20)
    pe = compute_pe_flags(rows)
    assert pe["P_PARTICIPATION"] is False
    assert pe["E_EDGE"] is True
    assert pe["n_policy"] == 80
    assert pe["policy_mean_r"] == pytest.approx(-0.20)
    assert select_gate1_law(p_participation=False, e_edge=True, w_wire=False, both_bad=False) == GATE1_NONE


def test_c_trigger_w_wire() -> None:
    assert (
        compute_w_wire(
            envelope_enabled=False,
            chatter_bound_live=True,
            refractory_live=True,
            min_dwell_in_kwargs=True,
            plant_tag_present=True,
        )
        is True
    )
    assert (
        compute_w_wire(
            envelope_enabled=True,
            chatter_bound_live=False,
            refractory_live=True,
            min_dwell_in_kwargs=True,
            plant_tag_present=True,
        )
        is True
    )
    assert (
        compute_w_wire(
            envelope_enabled=True,
            chatter_bound_live=True,
            refractory_live=False,
            min_dwell_in_kwargs=True,
            plant_tag_present=True,
        )
        is True
    )
    assert (
        compute_w_wire(
            envelope_enabled=True,
            chatter_bound_live=True,
            refractory_live=True,
            min_dwell_in_kwargs=True,
            plant_tag_present=False,
        )
        is True
    )
    assert (
        compute_w_wire(
            envelope_enabled=True,
            chatter_bound_live=True,
            refractory_live=True,
            min_dwell_in_kwargs=True,
            plant_tag_present=True,
        )
        is False
    )
    assert (
        select_gate1_law(p_participation=False, e_edge=True, w_wire=True, both_bad=False)
        == GATE1_WIRE_BIRTH_PARTICIPATION
    )


def test_c_trigger_both_bad() -> None:
    rows = _book(100, pnl=-40.0, trade_r=-0.20) + _book(100, pnl=-60.0, trade_r=-0.40, plant=True, force=True)
    pe = compute_pe_flags(rows)
    assert pe["P_PARTICIPATION"] is True
    assert pe["E_EDGE"] is True
    both = compute_both_bad(
        p_participation=True,
        e_edge=True,
        policy_mean_usd=float(pe["policy_mean_usd"]),
        overall_mean_usd=float(pe["overall_mean_usd"]),
    )
    assert both is True
    assert pe["policy_mean_usd"] == pytest.approx(-40.0)
    assert pe["overall_mean_usd"] == pytest.approx(-50.0)
    assert select_gate1_law(p_participation=True, e_edge=True, w_wire=False, both_bad=True) == GATE1_NONE


def test_c_trigger_none() -> None:
    rows = _book(50, pnl=5.0, trade_r=0.10)
    pe = compute_pe_flags(rows)
    assert pe["P_PARTICIPATION"] is False
    assert pe["E_EDGE"] is False
    assert select_gate1_law(p_participation=False, e_edge=False, w_wire=False, both_bad=False) == GATE1_NONE


def test_d_grind_refuses_gitignored_ppo_zip(tmp_path: Path) -> None:
    ppo = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    ppo.parent.mkdir(parents=True)
    ppo.write_bytes(b"PK\x03\x04post_polish_decoy")
    assert resolve_frozen_policy_path(tmp_path) is None
    assert load_frozen_policy(ppo) is None
    for path in candidate_frozen_paths(tmp_path):
        assert "lumina_agents/ppo" not in path.as_posix()
        assert path.name == "birth_exit_pi_star.zip"


def test_e_gate1_measure_only_live_path_already_has_envelope() -> None:
    dump = inspect_grind_live_path()
    assert dump["envelope_enabled_kwarg"] is True
    assert dump["min_dwell_in_kwargs"] is True
    assert dump["chatter_bound_constructed"] is True
    assert dump["refractory_passed_to_decide"] is True
    assert dump["plant_column_on_close_row"] is True
    assert dump["force_open_column_on_close_row"] is True
    assert dump["W_WIRE"] is False
    assert dump["skill_clock_in_grind_kwargs"] is False
    cfg = BirthCurriculumConfig()
    geo = type("G", (), {"stop_pct": 0.001, "target_pct": 0.002})()
    kwargs = s5_envelope_kwargs(cfg, geo)
    assert kwargs["participation_envelope_enabled"] is True
    assert int(kwargs["participation_min_dwell_bars"]) >= 1
    grind_a = Path("reports/birth_cloud_run/artifacts/grind_A_close_ledger.jsonl")
    if grind_a.is_file() and grind_a.stat().st_size > 0:
        book = evaluate_book(load_close_jsonl(grind_a))
        assert book["gate1"] == GATE1_NONE
        assert book["mech_tag"] == MECH_MEASURE_ONLY
        assert book["flags"].E_EDGE is True
        assert book["flags"].W_WIRE is False


def test_close_ledger_row_writes_force_open() -> None:
    row = close_ledger_row(
        {
            "pnl": -10.0,
            "qty": 1,
            "cap_usd": 500.0,
            "close_reason": "stop",
            "gap": False,
            "plant_entry": True,
            "entry_price": 20000.0,
            "risk_usd": 50.0,
            "trade_r": -0.2,
            "point_value": 5.0,
            "regime": "NEUTRAL",
            "reward_on_close": -0.2,
        }
    )
    assert row["plant"] is True
    assert row["force_open"] is True
    policy = close_ledger_row(
        {
            "pnl": 1.0,
            "qty": 1,
            "cap_usd": 500.0,
            "close_reason": "target",
            "gap": False,
            "plant_entry": False,
            "risk_usd": 50.0,
            "trade_r": 0.02,
            "point_value": 5.0,
            "regime": "NEUTRAL",
        }
    )
    assert policy["plant"] is False
    assert policy["force_open"] is False


def test_missing_force_open_falls_back_to_plant() -> None:
    row = {"pnl": -1.0, "plant": True, "trade_r": -0.1, "close_reason": "stop"}
    assert row_is_plant(row) is True
    assert row_is_force_open(row) is True
    explicit = {"pnl": -1.0, "plant": True, "force_open": False}
    assert row_is_force_open(explicit) is False


def test_occupancy_bands_missing_is_fail_closed() -> None:
    missing = occupancy_band_fractions(None)
    assert missing["missing"] is True
    assert missing["in_025_030"] is None
    present = occupancy_band_fractions([0.28, 0.28, 0.50, 0.80])
    assert present["missing"] is False
    assert present["in_025_030"] == pytest.approx(0.5)
    assert present["in_030_075"] == pytest.approx(0.25)
    assert present["gt_075"] == pytest.approx(0.25)
