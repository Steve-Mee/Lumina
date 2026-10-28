"""Awakening E_EDGE Gate 0 policy-only tables + trigger pins. Floors stay PR #14."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.birth.awakening_edge import (
    EDGE_MEASURE_ONLY,
    EDGE_RELABEL,
    EDGE_WIRED,
    GATE1_ALIGN_CLIP_GAP,
    GATE1_NONE,
    GATE1_RELABEL_CLOSE_REASON,
    GATE1_WIRE_BIRTH_FILL,
    compute_g_mislabel,
    compute_g_miswire,
    compute_t_neutral,
    compute_t_stop_only,
    compute_t_target,
    compute_t_time,
    edge_tag_for_law,
    evaluate_policy_book,
    inspect_grind_geometry_path,
    load_close_jsonl,
    policy_only_rows,
    select_gate1_law,
    table_by_close_reason,
    table_by_regime,
)
from lumina_core.birth.awakening_grind import BIRTH_N, REGRESS_MEAN_USD, TRAIN
from lumina_core.birth.birth_exit_policy_export import (
    candidate_frozen_paths,
    load_frozen_policy,
    resolve_frozen_policy_path,
)
from lumina_core.birth.foundation_metrics import (
    POLICY_EDGE_MIN_TRADES,
    S5_DD_MAX_PCT,
    S5_SHARPE_FLOOR,
)
from lumina_core.birth.notional_cap import birth_gym_point_value
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
    assert "S5_SHARPE_FLOOR = -2.0" in metrics
    assert "S5_DD_MAX_PCT = 25.0" in metrics
    assert "POLICY_EDGE_MIN_TRADES = 150" in metrics
    for rel in (
        "lumina_core/birth/awakening_edge.py",
        "lumina_core/birth/awakening_edge_path.py",
        "lumina_core/birth/awakening_grind.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        for token in ("S5_IDLE_REGIMES", "MAX_TIME_STOP", "if synthetic"):
            assert token not in src


def _row(
    *,
    pnl: float,
    trade_r: float,
    close_reason: str = "stop",
    regime: str = "NEUTRAL",
    gap: bool = False,
    cap_hit: bool = False,
    plant: bool = False,
    force_open: bool = False,
) -> dict[str, object]:
    return {
        "pnl": pnl,
        "trade_r": trade_r,
        "close_reason": close_reason,
        "regime": regime,
        "gap": gap,
        "cap_hit": cap_hit,
        "plant": plant,
        "force_open": force_open,
        "qty": 1,
        "point_value": 5.0,
        "intended_risk_usd": 50.0,
    }


def _policy_fixture() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    rows.extend(_row(pnl=-50.0, trade_r=-1.0, close_reason="stop") for _ in range(8))
    rows.extend(_row(pnl=-50.0, trade_r=-1.0, close_reason="stop", regime="TREND_DOWN") for _ in range(2))
    rows.extend(_row(pnl=60.0, trade_r=1.2, close_reason="target") for _ in range(5))
    rows.append(_row(pnl=60.0, trade_r=1.2, close_reason="target", regime="TREND_UP"))
    rows.extend(_row(pnl=20.0, trade_r=0.4, close_reason="time_stop") for _ in range(3))
    rows.append(_row(pnl=20.0, trade_r=0.4, close_reason="time_stop", regime="TREND_UP"))
    rows.append(_row(pnl=-200.0, trade_r=-4.0, plant=True, force_open=True))
    assert len(rows) == 21
    return rows


def test_b_policy_only_fixture_reason_regime_totals() -> None:
    rows = _policy_fixture()
    policy = policy_only_rows(rows)
    assert len(policy) == 20
    by_r = table_by_close_reason(policy)
    stop = by_r["stop"]
    assert stop["n"] == pytest.approx(10.0)
    assert stop["wr"] == pytest.approx(0.0)
    assert stop["sum_usd"] == pytest.approx(-500.0)
    assert stop["mean_usd"] == pytest.approx(-50.0)
    assert stop["mean_r"] == pytest.approx(-1.0)
    assert stop["median_r"] == pytest.approx(-1.0)
    assert stop["cap_hit"] == pytest.approx(0.0)
    target = by_r["target"]
    assert target["n"] == pytest.approx(6.0)
    assert target["wr"] == pytest.approx(1.0)
    assert target["sum_usd"] == pytest.approx(360.0)
    assert target["mean_usd"] == pytest.approx(60.0)
    assert target["mean_r"] == pytest.approx(1.2)
    assert target["median_r"] == pytest.approx(1.2)
    timed = by_r["time_stop"]
    assert timed["n"] == pytest.approx(4.0)
    assert timed["wr"] == pytest.approx(1.0)
    assert timed["sum_usd"] == pytest.approx(80.0)
    assert timed["mean_r"] == pytest.approx(0.4)
    by_g = table_by_regime(policy)
    neu = by_g["NEUTRAL"]
    assert neu["n"] == pytest.approx(16.0)
    assert neu["loss_share"] == pytest.approx(0.8)
    assert by_g["TREND_DOWN"]["n"] == pytest.approx(2.0)
    assert by_g["TREND_DOWN"]["loss_share"] == pytest.approx(0.2)
    assert by_g["TREND_UP"]["n"] == pytest.approx(2.0)
    assert by_g["TREND_UP"]["loss_share"] == pytest.approx(0.0)
    book = evaluate_policy_book(rows, g_miswire=False)
    assert book["n_policy"] == 20
    assert book["n_plant"] == 1
    assert book["reason_regime"]["trigger"]["stop|NEUTRAL"]["n"] == pytest.approx(8.0)
    assert book["reason_regime"]["small"]["stop|TREND_DOWN"] == pytest.approx(2.0)


def _book(
    n: int,
    *,
    pnl: float,
    trade_r: float,
    close_reason: str = "stop",
    regime: str = "NEUTRAL",
) -> list[dict[str, object]]:
    return [_row(pnl=pnl, trade_r=trade_r, close_reason=close_reason, regime=regime) for _ in range(n)]


def test_c_trigger_g_miswire() -> None:
    assert compute_g_miswire({"G_MISWIRE": True}) is True
    assert compute_g_miswire({"G_MISWIRE": False}) is False
    assert select_gate1_law(g_miswire=True, g_mislabel=False, t_target=False, clip_gap_shared=True) == (
        GATE1_WIRE_BIRTH_FILL
    )
    assert edge_tag_for_law(GATE1_WIRE_BIRTH_FILL) == EDGE_WIRED


def test_c_trigger_g_mislabel() -> None:
    targets = _book(20, pnl=-10.0, trade_r=-0.2, close_reason="target")
    assert compute_g_mislabel(targets) is False
    assert compute_g_mislabel(targets, physical_reasons=["stop"] * 20) is True
    assert compute_g_mislabel(targets, physical_reasons=["target"] * 20) is False
    plus = _book(20, pnl=10.0, trade_r=0.5, close_reason="target")
    assert compute_g_mislabel(plus, physical_reasons=["stop"] * 20) is False
    assert select_gate1_law(g_miswire=False, g_mislabel=True, t_target=True, clip_gap_shared=True) == (
        GATE1_RELABEL_CLOSE_REASON
    )
    assert edge_tag_for_law(GATE1_RELABEL_CLOSE_REASON) == EDGE_RELABEL


def test_c_trigger_t_time() -> None:
    timed = _book(12, pnl=-40.0, trade_r=-0.5, close_reason="time_stop")
    other = _book(10, pnl=-10.0, trade_r=-1.0, close_reason="stop")
    rows = timed + other
    assert compute_t_time(rows) is True
    assert compute_t_stop_only(rows, t_time=True) is False
    short = _book(9, pnl=-40.0, trade_r=-0.5, close_reason="time_stop")
    assert compute_t_time(short) is False


def test_c_trigger_t_target() -> None:
    dead = _book(15, pnl=-5.0, trade_r=0.0, close_reason="target")
    assert compute_t_target(dead) is True
    live = _book(15, pnl=50.0, trade_r=1.2, close_reason="target")
    assert compute_t_target(live) is False
    assert select_gate1_law(g_miswire=False, g_mislabel=False, t_target=True, clip_gap_shared=True) == (GATE1_NONE)
    assert select_gate1_law(g_miswire=False, g_mislabel=False, t_target=True, clip_gap_shared=False) == (
        GATE1_ALIGN_CLIP_GAP
    )


def test_c_trigger_t_neutral() -> None:
    neu = _book(70, pnl=-30.0, trade_r=-0.30, regime="NEUTRAL")
    up = _book(15, pnl=2.0, trade_r=0.02, regime="TREND_UP")
    down = _book(15, pnl=1.0, trade_r=0.01, regime="TREND_DOWN")
    rows = neu + up + down
    assert compute_t_neutral(rows) is True
    bad_trend = neu + _book(25, pnl=-40.0, trade_r=-0.40, regime="TREND_UP")
    assert compute_t_neutral(bad_trend) is False
    tiny = neu + _book(10, pnl=1.0, trade_r=0.02, regime="TREND_UP")
    assert compute_t_neutral(tiny) is False


def test_c_trigger_t_stop_only() -> None:
    stops = _book(80, pnl=-50.0, trade_r=-1.0, close_reason="stop")
    targets = _book(20, pnl=60.0, trade_r=1.2, close_reason="target")
    rows = stops + targets
    assert compute_t_time(rows) is False
    assert compute_t_target(rows) is False
    assert compute_t_stop_only(rows, t_time=False) is True
    assert select_gate1_law(g_miswire=False, g_mislabel=False, t_target=False, clip_gap_shared=True) == (GATE1_NONE)
    assert edge_tag_for_law(GATE1_NONE) == EDGE_MEASURE_ONLY


def test_c_trigger_none() -> None:
    rows = _book(20, pnl=5.0, trade_r=0.10, close_reason="target")
    assert compute_t_time(rows) is False
    assert compute_t_target(rows) is False
    assert compute_t_neutral(rows) is False
    assert compute_t_stop_only(rows, t_time=False) is False
    assert compute_g_mislabel(rows) is False
    assert select_gate1_law(g_miswire=False, g_mislabel=False, t_target=False, clip_gap_shared=True) == (GATE1_NONE)


def test_d_grind_refuses_gitignored_ppo_zip(tmp_path: Path) -> None:
    ppo = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    ppo.parent.mkdir(parents=True)
    ppo.write_bytes(b"PK\x03\x04post_polish_decoy")
    assert resolve_frozen_policy_path(tmp_path) is None
    assert load_frozen_policy(ppo) is None
    for path in candidate_frozen_paths(tmp_path):
        assert "lumina_agents/ppo" not in path.as_posix()
        assert path.name == "birth_exit_pi_star.zip"


def test_e_live_geometry_not_miswired_and_jsonl_is_stop_only() -> None:
    dump = inspect_grind_geometry_path()
    assert dump["G_MISWIRE"] is False
    assert dump["clip_gap_shared"] is True
    assert dump["same_fill"] is True
    assert dump["same_pnl"] is True
    assert dump["mes5_live"] is True
    assert dump["qty_one_live"] is True
    assert compute_g_miswire(dump) is False
    grind_a = Path("reports/birth_cloud_run/artifacts/grind_A_close_ledger.jsonl")
    if not (grind_a.is_file() and grind_a.stat().st_size > 0):
        return
    book = evaluate_policy_book(load_close_jsonl(grind_a), design_net_rr=1.7674031413396907)
    assert book["n_policy"] == 150
    assert book["by_close_reason"]["stop"]["n"] == pytest.approx(96.0)
    assert book["by_close_reason"]["target"]["n"] == pytest.approx(35.0)
    assert book["by_close_reason"]["time_stop"]["n"] == pytest.approx(19.0)
    assert book["policy"]["mean_r"] == pytest.approx(-0.211, abs=0.001)
    assert book["flags"].G_MISWIRE is False
    assert book["flags"].G_MISLABEL is False
    assert book["flags"].T_TIME is False
    assert book["flags"].T_TARGET is False
    assert book["flags"].T_NEUTRAL is False
    assert book["flags"].T_STOP_ONLY is True
    assert book["gate1"] == GATE1_NONE
    assert book["edge_tag"] == EDGE_MEASURE_ONLY
    assert book["target_gap"]["target_no_gap"]["n"] == pytest.approx(35.0)
    assert book["target_gap"]["target_gap"]["n"] == pytest.approx(0.0)
    assert book["realized_vs_design"]["mean_r_target"] > 0.0
    assert book["occupancy_series"]["missing"] is True
