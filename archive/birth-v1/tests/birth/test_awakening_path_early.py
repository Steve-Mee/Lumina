"""Awakening PATH_EARLY: protocol, flags, telem, eval wrap."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.awakening_grind import EvaluateOnlyPolicy, TRAIN
from lumina_core.birth.awakening_path_early import (
    FORBIDDEN_WRITE_NAMES,
    OVERALL_INCONCLUSIVE,
    PATH_A_NAME,
    PATH_B_NAME,
    TRAIN_SEED,
    PathEarlyProtocolError,
    assert_eval_seed,
    assert_isolated_write,
    assert_not_evaluated_policy,
    isolated_workspace,
    overall_path_early_string,
)
from lumina_core.birth.awakening_path_early_flags import (
    FAMILY_H_NONE,
    K_LOCKED,
    PATH_CANDIDATE_NAMES,
    P_K3_MAE_DEEP,
    P_K3_UNREAL_RED,
    P_K5_MAE_DEEP,
    P_K5_UNREAL_RED,
    compute_path_early_flags,
    license_from_ab,
)
from lumina_core.birth.awakening_path_early_path import (
    compute_k_medians,
    inspect_path_early_protocol,
    pred_mae_deep,
    universe_k,
)
from lumina_core.birth.awakening_path_early_tables import table_t1b, table_t5
from lumina_core.birth.s5_close_ledger_trace import close_ledger_row


def _row(
    *,
    entry: str | None = "NEUTRAL",
    close_reason: str = "stop",
    regime: str = "NEUTRAL",
    trade_r: float = -1.04,
    pnl: float = -117.0,
    plant: bool = False,
    bars_held: int = 8,
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "pnl": pnl,
        "trade_r": trade_r,
        "close_reason": close_reason,
        "regime": regime,
        "plant": plant,
        "force_open": plant,
        "bars_held": bars_held,
    }
    if entry is not None:
        row["entry_regime"] = entry
    row.update(extra)
    return row


def _split_k3(
    *,
    n_h_deep: int,
    n_h_shallow: int,
    n_w_deep: int,
    n_w_shallow: int,
    n_other_deep: int,
    n_other_shallow: int,
    also_unreal: bool = False,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def _add(n: int, *, deep: bool, winner: bool, other: bool) -> None:
        mae = -2.0 if deep else 0.0
        extra: dict[str, Any] = {"path_k3_mae_r": mae, "path_k3_mfe_r": 0.5}
        if also_unreal:
            extra["path_k3_unreal_r"] = mae
        if other:
            rows.extend(
                _row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0, **extra) for _ in range(n)
            )
        elif winner:
            rows.extend(_row(close_reason="target", trade_r=1.21, pnl=60.0, **extra) for _ in range(n))
        else:
            rows.extend(_row(**extra) for _ in range(n))

    _add(n_h_deep, deep=True, winner=False, other=False)
    _add(n_h_shallow, deep=False, winner=False, other=False)
    _add(n_w_deep, deep=True, winner=True, other=False)
    _add(n_w_shallow, deep=False, winner=True, other=False)
    _add(n_other_deep, deep=True, winner=False, other=True)
    _add(n_other_shallow, deep=False, winner=False, other=True)
    return rows


def test_inspect_path_early_protocol_complete() -> None:
    dump = inspect_path_early_protocol()
    assert dump["gate0_complete"] is True, f"missing: {dump['missing_sites']}"
    assert dump["missing_sites"] == []
    assert K_LOCKED == (3, 5)


def test_training_reward_absent_from_birth() -> None:
    birth_root = Path("lumina_core/birth")
    ident = re.compile(r"(?<![A-Za-z0-9_])training_reward(?![A-Za-z0-9_])")
    for path in sorted(birth_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert ident.search(text) is None, f"training_reward in {path}"


def test_runner_refuses_train_seed_20260901() -> None:
    with pytest.raises(PathEarlyProtocolError, match="train seed"):
        assert_eval_seed(TRAIN_SEED)


def test_forbidden_write_parent_zip_and_policy_signal_jsonl(tmp_path: Path) -> None:
    with pytest.raises(PathEarlyProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "birth_exit_pi_star.zip")
    with pytest.raises(PathEarlyProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "policy_signal_A_close_ledger.jsonl")
    with pytest.raises(PathEarlyProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "open_split_A_close_ledger.jsonl")
    assert PATH_A_NAME not in FORBIDDEN_WRITE_NAMES
    assert PATH_B_NAME not in FORBIDDEN_WRITE_NAMES
    assert isolated_workspace(tmp_path).as_posix().endswith("awakening_path_early/workspace")
    assert TRAIN is False


def test_assert_not_evaluated_policy_refuses_control_sha(tmp_path: Path) -> None:
    control = tmp_path / "awakening_select_pi_star.zip"
    control.write_bytes(b"PK\x03\x04select-child")
    with pytest.raises(PathEarlyProtocolError, match="evaluated policy"):
        assert_not_evaluated_policy(control)


def test_skip_replay_overall_is_inconclusive() -> None:
    assert overall_path_early_string(parent_loaded=True, skip_replay=True) == OVERALL_INCONCLUSIVE


def test_license_none_is_h_none_not_open_decision() -> None:
    flags = {
        "tag": "S_NONE",
        "winning_P": "none",
        "S_MISSING_U": False,
        "S_THIN": False,
        "S_MISSING_PATH": False,
    }
    licensed = license_from_ab(flags, flags)
    assert licensed["licensed_next_family"] == FAMILY_H_NONE
    assert licensed["licensed_next_family"] != "OPEN_DECISION"


def test_license_missing_is_h_none_not_open_decision() -> None:
    flags = {
        "tag": "S_MISSING",
        "winning_P": "none",
        "S_MISSING_U": True,
        "S_THIN": False,
        "S_MISSING_PATH": False,
    }
    licensed = license_from_ab(flags, flags)
    assert licensed["licensed_next_family"] == FAMILY_H_NONE
    assert "OPEN_DECISION" not in licensed.values()


def test_empty_u_marks_candidates_missing() -> None:
    flags = compute_path_early_flags([])
    assert flags["n_U"] == 0
    assert flags["S_MISSING_U"] is True
    for name in PATH_CANDIDATE_NAMES:
        cand = flags["candidates"][name]
        assert cand["missing"] is True
        assert cand["missing_share"] == pytest.approx(1.0)
        assert cand["n_defined"] == 0


def test_s_split_true_lift_060() -> None:
    rows = _split_k3(
        n_h_deep=40, n_h_shallow=10, n_w_deep=6, n_w_shallow=24, n_other_deep=4, n_other_shallow=16
    )
    flags = compute_path_early_flags(rows)
    cand = flags["candidates"][P_K3_MAE_DEEP]
    assert cand["lift"] == pytest.approx(0.60)
    assert cand["S_SPLIT"] is True
    assert flags["tag"] == "S_SPLIT"
    assert flags["winning_P"] == P_K3_MAE_DEEP


def test_s_split_false_lift_013() -> None:
    rows = _split_k3(
        n_h_deep=40, n_h_shallow=10, n_w_deep=20, n_w_shallow=10, n_other_deep=0, n_other_shallow=20
    )
    flags = compute_path_early_flags(rows)
    cand = flags["candidates"][P_K3_MAE_DEEP]
    assert cand["lift"] == pytest.approx(0.8 - (20.0 / 30.0))
    assert cand["S_SPLIT"] is False


def test_s_harm_true() -> None:
    rows = _split_k3(
        n_h_deep=10, n_h_shallow=40, n_w_deep=20, n_w_shallow=10, n_other_deep=20, n_other_shallow=0
    )
    flags = compute_path_early_flags(rows)
    cand = flags["candidates"][P_K3_MAE_DEEP]
    assert cand["S_HARM"] is True
    assert cand["S_SPLIT"] is False


def test_s_thin_at_k() -> None:
    rows = _split_k3(
        n_h_deep=20, n_h_shallow=10, n_w_deep=6, n_w_shallow=8, n_other_deep=20, n_other_shallow=20
    )
    flags = compute_path_early_flags(rows)
    assert flags["k"][3]["S_THIN"] is True
    assert flags["candidates"][P_K3_MAE_DEEP]["S_SPLIT"] is False


def test_s_missing_path() -> None:
    rows = [_row(bars_held=8) for _ in range(80)]
    for i in range(25):
        rows[i]["close_reason"] = "target"
        rows[i]["trade_r"] = 1.21
    flags = compute_path_early_flags(rows)
    assert flags["S_MISSING_PATH"] is True
    assert flags["tag"] == "S_MISSING"


def test_s_multi_two_predicates() -> None:
    rows = _split_k3(
        n_h_deep=40,
        n_h_shallow=10,
        n_w_deep=6,
        n_w_shallow=24,
        n_other_deep=4,
        n_other_shallow=16,
        also_unreal=True,
    )
    flags = compute_path_early_flags(rows)
    assert flags["candidates"][P_K3_MAE_DEEP]["S_SPLIT"] is True
    assert flags["candidates"][P_K3_UNREAL_RED]["S_SPLIT"] is True
    assert flags["tag"] == "S_MULTI"
    assert flags["winning_P"] == "none"


def test_s_ab_disagree() -> None:
    rows_a = _split_k3(
        n_h_deep=40, n_h_shallow=10, n_w_deep=6, n_w_shallow=24, n_other_deep=4, n_other_shallow=16
    )
    flags_a = compute_path_early_flags(rows_a)
    rows_b = _split_k3(
        n_h_deep=40,
        n_h_shallow=10,
        n_w_deep=6,
        n_w_shallow=24,
        n_other_deep=4,
        n_other_shallow=16,
        also_unreal=True,
    )
    for row in rows_b:
        row["path_k3_mae_r"] = 0.0
    flags_b = compute_path_early_flags(rows_b)
    assert flags_a["winning_P"] == P_K3_MAE_DEEP
    assert flags_b["winning_P"] == P_K3_UNREAL_RED
    licensed = license_from_ab(flags_a, flags_b)
    assert licensed["tag"] == "S_AB_DISAGREE"
    assert licensed["licensed_next_family"] == FAMILY_H_NONE


def test_median_uk_does_not_use_hw_labels() -> None:
    rows = _split_k3(
        n_h_deep=40, n_h_shallow=10, n_w_deep=6, n_w_shallow=24, n_other_deep=4, n_other_shallow=16
    )
    from lumina_core.birth.awakening_edge import policy_only_rows
    from lumina_core.birth.awakening_open_split_flags import universe_rows

    universe = universe_rows(policy_only_rows(rows))
    u_k = universe_k(universe, 3)
    thr = compute_k_medians(u_k, 3)
    flipped = []
    for row in universe:
        copy = dict(row)
        if copy.get("close_reason") == "stop":
            copy["close_reason"] = "target"
            copy["trade_r"] = 1.21
        elif copy.get("close_reason") == "target":
            copy["close_reason"] = "stop"
            copy["trade_r"] = -1.04
        flipped.append(copy)
    thr_flip = compute_k_medians(universe_k(universe_rows(policy_only_rows(flipped)), 3), 3)
    assert thr["mae_r"] == pytest.approx(thr_flip["mae_r"] or 0.0)


def test_missing_path_key_does_not_impute_zero() -> None:
    row = close_ledger_row(
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
        }
    )
    assert "path_k3_mae_r" not in row
    assert pred_mae_deep(row, k=3, threshold=0.0) is False
    t1b = table_t1b([])
    assert t1b["path_k3_mae_r"]["U_k"]["missing_share"] == pytest.approx(1.0)
    assert t1b["path_k3_mae_r"]["U_k"]["mean"] is None


def test_died_before_k_not_in_uk() -> None:
    dead = _row(bars_held=2, path_k3_mae_r=-2.0)
    live = _row(bars_held=8, path_k3_mae_r=-2.0)
    from lumina_core.birth.awakening_open_split_flags import universe_rows

    u_k = universe_k(universe_rows([dead, live]), 3)
    assert len(u_k) == 1
    assert u_k[0]["bars_held"] == 8
    flags = compute_path_early_flags([dead] + [_row(bars_held=8, path_k3_mae_r=-1.0) for _ in range(59)])
    assert flags["k"][3]["n_died_before_k"] >= 1


def test_candidate_names_only_four() -> None:
    assert PATH_CANDIDATE_NAMES == (P_K3_MAE_DEEP, P_K3_UNREAL_RED, P_K5_MAE_DEEP, P_K5_UNREAL_RED)
    assert len(PATH_CANDIDATE_NAMES) == 4


def test_predicates_do_not_read_close_mae_or_open_split_f() -> None:
    for rel in (
        "lumina_core/birth/awakening_path_early.py",
        "lumina_core/birth/awakening_path_early_flags.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        assert re.search(r'row\.get\([\'"]mae_r', src) is None
        assert re.search(r'\[[\'"]mae_r[\'"]\]', src) is None
        assert re.search(r'get\([\'"]bars_held', src) is None
        assert re.search(r'\[[\'"]bars_held[\'"]\]', src) is None
        for name in ("F_OCC_FLOOR", "F_SESSION_EARLY", "F_TIGHT_RANGE", "F_AFTER_STOP", "F_IMBAL_FLAT"):
            assert name not in src


def test_flip_tail_cannot_be_winning_candidate() -> None:
    rows = _split_k3(
        n_h_deep=40, n_h_shallow=10, n_w_deep=6, n_w_shallow=24, n_other_deep=4, n_other_shallow=16
    )
    t5 = table_t5(rows)
    for name in PATH_CANDIDATE_NAMES:
        assert t5[name]["READ_ONLY_FLIP"] is True
        assert t5[name]["S_SPLIT"] is False


def test_evaluate_only_policy_learn_raises() -> None:
    class _Inner:
        def predict(self, *args: Any, **kwargs: Any) -> Any:
            _ = args, kwargs
            return [0.0, 0.5, 0.002, 0.003], None

        def learn(self, *args: Any, **kwargs: Any) -> Any:
            return self

    wrapped = EvaluateOnlyPolicy(_Inner())
    with pytest.raises(RuntimeError, match="learn\\(\\) forbidden"):
        wrapped.learn(total_timesteps=1)


def test_path_early_runner_never_calls_learn() -> None:
    src = Path("lumina_core/birth/awakening_path_early_run.py").read_text(encoding="utf-8")
    assert "learn_fn" not in src
    assert "model.learn(" not in src
    assert "model.learn" not in src


def test_telem_snapshot_writes_k3_k5_while_open() -> None:
    from lumina_core.birth.sim_runner_entry_telem import (
        apply_open_excursion,
        close_open_telem,
        snapshot_path_at_k,
        start_open_telem,
        update_open_telem,
    )

    stash = start_open_telem(entry_regime="NEUTRAL", entry_bar_index=10, entry_price=20000.0, side=1)
    apply_open_excursion(stash, {"high": 20002.0, "low": 19990.0})
    tick = {"high": 20002.0, "low": 19990.0, "close": 19995.0}
    snapshot_path_at_k(stash, tick, 3)
    snapshot_path_at_k(stash, tick, 5)
    assert "path_k3_mae_usd" in stash
    assert "path_k5_mae_usd" in stash
    assert "path_k3_unreal_usd" in stash
    closed = close_open_telem(stash, 15, "NEUTRAL", {"intended_risk_usd": 50.0})
    assert "path_k3_mae_r" in closed
    assert "path_k5_unreal_r" in closed

    class _Env:
        _entry_side = 1
        _entry_price = 20000.0
        _idx = 13

    ticks = [{"regime": "NEUTRAL", "high": 20001.0, "low": 19990.0, "close": 19995.0}]
    opened = start_open_telem(entry_regime="NEUTRAL", entry_bar_index=10, entry_price=20000.0, side=1)
    hit = update_open_telem(opened, _Env(), {}, 1, 1, ticks[0], ticks)
    assert hit is not None
    assert "path_k3_mae_usd" in hit


def test_no_snapshot_if_closed_earlier() -> None:
    from lumina_core.birth.sim_runner_entry_telem import start_open_telem, update_open_telem

    class _Env:
        _entry_side = 1
        _entry_price = 20000.0
        _idx = 13

    ticks = [{"regime": "NEUTRAL", "high": 20001.0, "low": 19999.0, "close": 20000.0}]
    stash = start_open_telem(entry_regime="NEUTRAL", entry_bar_index=10, entry_price=20000.0, side=1)
    out = update_open_telem(stash, _Env(), {}, 0, 0, ticks[0], ticks)
    assert out is not None
    assert "path_k3_mae_usd" not in out


def test_start_open_telem_old_kwargs_still_work() -> None:
    from lumina_core.birth.sim_runner_entry_telem import start_open_telem

    stash = start_open_telem(entry_regime="NEUTRAL", entry_bar_index=2, entry_price=20000.0, side=1)
    assert stash["entry_regime"] == "NEUTRAL"
    assert "path_k3_mae_usd" not in stash
    assert "open_occ_flat" not in stash


def test_close_ledger_row_copies_path_keys_only_when_present() -> None:
    bare = close_ledger_row(
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
        }
    )
    assert "path_k3_mae_r" not in bare
    filled = close_ledger_row(
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
            "path_k3_mae_r": -0.8,
            "path_k5_unreal_r": -0.2,
        }
    )
    assert filled["path_k3_mae_r"] == pytest.approx(-0.8)
    assert filled["path_k5_unreal_r"] == pytest.approx(-0.2)
    assert "path_k5_mae_r" not in filled
