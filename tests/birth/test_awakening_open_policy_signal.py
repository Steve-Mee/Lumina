"""Awakening OPEN_POLICY_SIGNAL: protocol, flags, extraction, eval wrap."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from lumina_core.birth.awakening_grind import EvaluateOnlyPolicy, TRAIN
from lumina_core.birth.awakening_open_policy_signal import (
    FORBIDDEN_WRITE_NAMES,
    OVERALL_INCONCLUSIVE,
    SIGNAL_A_NAME,
    SIGNAL_B_NAME,
    TRAIN_SEED,
    OpenPolicySignalProtocolError,
    assert_eval_seed,
    assert_isolated_write,
    assert_not_evaluated_policy,
    isolated_workspace,
    overall_policy_signal_string,
)
from lumina_core.birth.awakening_open_policy_signal_flags import (
    FAMILY_H_NONE,
    POLICY_CANDIDATE_NAMES,
    P_ACTION_MARGIN,
    P_ENTROPY,
    P_VALUE,
    compute_adaptive_thresholds,
    compute_open_policy_signal_flags,
    license_from_ab,
    pred_action_margin_low,
    pred_entropy_high,
    pred_value_below_median,
)
from lumina_core.birth.awakening_open_policy_signal_path import (
    inspect_open_policy_signal_protocol,
)
from lumina_core.birth.awakening_open_policy_signal_tables import table_t5
from lumina_core.birth.policy_signal_extract import extract_policy_signals
from lumina_core.birth.s5_close_ledger_trace import close_ledger_row


def _row(
    *,
    entry: str | None = "NEUTRAL",
    close_reason: str = "stop",
    regime: str = "NEUTRAL",
    trade_r: float = -1.04,
    pnl: float = -117.0,
    plant: bool = False,
    **extra: Any,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "pnl": pnl,
        "trade_r": trade_r,
        "close_reason": close_reason,
        "regime": regime,
        "plant": plant,
        "force_open": plant,
    }
    if entry is not None:
        row["entry_regime"] = entry
    row.update(extra)
    return row


def _split_universe(*, n_h_low: int, n_h_high: int, n_w_low: int, n_w_high: int, n_other: int = 20) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _ in range(n_h_low):
        rows.append(_row(open_policy_value=-1.0, open_policy_entropy=1.0, open_policy_action_margin=0.4))
    for _ in range(n_h_high):
        rows.append(_row(open_policy_value=1.0, open_policy_entropy=1.0, open_policy_action_margin=0.4))
    for _ in range(n_w_low):
        rows.append(
            _row(
                close_reason="target",
                trade_r=1.21,
                pnl=60.0,
                open_policy_value=-1.0,
                open_policy_entropy=1.0,
                open_policy_action_margin=0.4,
            )
        )
    for _ in range(n_w_high):
        rows.append(
            _row(
                close_reason="target",
                trade_r=1.21,
                pnl=60.0,
                open_policy_value=1.0,
                open_policy_entropy=1.0,
                open_policy_action_margin=0.4,
            )
        )
    for _ in range(n_other):
        rows.append(
            _row(
                close_reason="time_stop",
                trade_r=-0.1,
                pnl=-5.0,
                open_policy_value=0.0,
                open_policy_entropy=1.0,
                open_policy_action_margin=0.4,
            )
        )
    return rows


def test_inspect_open_policy_signal_protocol_complete() -> None:
    dump = inspect_open_policy_signal_protocol()
    assert dump["gate0_complete"] is True, f"missing: {dump['missing_sites']}"
    assert dump["missing_sites"] == []


def test_training_reward_absent_from_birth() -> None:
    birth_root = Path("lumina_core/birth")
    ident = re.compile(r"(?<![A-Za-z0-9_])training_reward(?![A-Za-z0-9_])")
    for path in sorted(birth_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert ident.search(text) is None, f"training_reward in {path}"


def test_runner_refuses_train_seed_20260901() -> None:
    with pytest.raises(OpenPolicySignalProtocolError, match="train seed"):
        assert_eval_seed(TRAIN_SEED)


def test_forbidden_write_open_split_jsonl(tmp_path: Path) -> None:
    with pytest.raises(OpenPolicySignalProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "open_split_A_close_ledger.jsonl")
    with pytest.raises(OpenPolicySignalProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "open_split_B_close_ledger.jsonl")
    assert SIGNAL_A_NAME not in FORBIDDEN_WRITE_NAMES
    assert SIGNAL_B_NAME not in FORBIDDEN_WRITE_NAMES
    assert isolated_workspace(tmp_path).as_posix().endswith("awakening_open_policy_signal/workspace")
    assert TRAIN is False


def test_assert_not_evaluated_policy_refuses_control_sha(tmp_path: Path) -> None:
    control = tmp_path / "awakening_select_pi_star.zip"
    control.write_bytes(b"PK\x03\x04select-child")
    with pytest.raises(OpenPolicySignalProtocolError, match="evaluated policy"):
        assert_not_evaluated_policy(control)


def test_skip_replay_overall_is_inconclusive() -> None:
    assert (
        overall_policy_signal_string(parent_loaded=True, skip_replay=True)
        == OVERALL_INCONCLUSIVE
    )


def test_license_none_is_h_none_not_open_decision() -> None:
    flags = {"tag": "S_NONE", "winning_P": "none", "S_MISSING_U": False, "S_THIN": False, "S_MISSING_SIGNAL": False}
    licensed = license_from_ab(flags, flags)
    assert licensed["licensed_next_family"] == FAMILY_H_NONE
    assert licensed["licensed_next_family"] != "OPEN_DECISION"


def test_license_missing_is_h_none_not_open_decision() -> None:
    flags = {"tag": "S_MISSING", "winning_P": "none", "S_MISSING_U": True, "S_THIN": False, "S_MISSING_SIGNAL": False}
    licensed = license_from_ab(flags, flags)
    assert licensed["licensed_next_family"] == FAMILY_H_NONE
    assert "OPEN_DECISION" not in licensed.values()


def test_empty_u_marks_candidates_missing() -> None:
    flags = compute_open_policy_signal_flags([])
    assert flags["n_U"] == 0
    assert flags["S_MISSING_U"] is True
    for name in POLICY_CANDIDATE_NAMES:
        cand = flags["candidates"][name]
        assert cand["missing"] is True
        assert cand["missing_share"] == pytest.approx(1.0)
        assert cand["n_defined"] == 0


def test_s_missing_signal_when_all_keys_absent() -> None:
    rows = [_row() for _ in range(80)]
    for i in range(20):
        rows[i]["close_reason"] = "target"
        rows[i]["trade_r"] = 1.21
    flags = compute_open_policy_signal_flags(rows)
    assert flags["S_MISSING_SIGNAL"] is True
    assert flags["tag"] == "S_MISSING"


def test_s_split_true_lift_060() -> None:
    rows = _split_universe(n_h_low=40, n_h_high=10, n_w_low=6, n_w_high=24, n_other=20)
    flags = compute_open_policy_signal_flags(rows)
    cand = flags["candidates"][P_VALUE]
    assert cand["lift"] == pytest.approx(0.60)
    assert cand["S_SPLIT"] is True
    assert flags["tag"] == "S_SPLIT"
    assert flags["winning_P"] == P_VALUE


def test_s_split_false_lift_013() -> None:
    rows = _split_universe(n_h_low=40, n_h_high=10, n_w_low=20, n_w_high=10, n_other=20)
    flags = compute_open_policy_signal_flags(rows)
    cand = flags["candidates"][P_VALUE]
    assert cand["lift"] == pytest.approx(0.8 - (20.0 / 30.0))
    assert cand["S_SPLIT"] is False


def test_s_harm_true() -> None:
    rows = _split_universe(n_h_low=10, n_h_high=40, n_w_low=20, n_w_high=10, n_other=20)
    flags = compute_open_policy_signal_flags(rows)
    cand = flags["candidates"][P_VALUE]
    assert cand["S_HARM"] is True
    assert cand["S_SPLIT"] is False


def test_median_u_does_not_use_hw_labels() -> None:
    rows = _split_universe(n_h_low=40, n_h_high=10, n_w_low=6, n_w_high=24, n_other=20)
    from lumina_core.birth.awakening_edge import policy_only_rows
    from lumina_core.birth.awakening_open_split_flags import universe_rows

    universe = universe_rows(policy_only_rows(rows))
    thr = compute_adaptive_thresholds(universe)
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
    thr_flip = compute_adaptive_thresholds(universe_rows(policy_only_rows(flipped)))
    assert thr["value_median"] == pytest.approx(thr_flip["value_median"])
    assert thr["entropy_median"] == pytest.approx(thr_flip["entropy_median"])
    assert thr["action_margin_median"] == pytest.approx(thr_flip["action_margin_median"])


def test_missing_open_policy_value_does_not_impute_zero() -> None:
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
    assert "open_policy_value" not in row
    assert pred_value_below_median(row, threshold=0.0) is False


def test_flip_tail_cannot_be_winning_candidate() -> None:
    rows = _split_universe(n_h_low=40, n_h_high=10, n_w_low=6, n_w_high=24, n_other=20)
    t5 = table_t5(rows)
    for name in POLICY_CANDIDATE_NAMES:
        assert t5[name]["READ_ONLY_FLIP"] is True
        assert t5[name]["S_SPLIT"] is False


def test_extract_uses_taken_action_for_margin() -> None:
    class _Dist:
        def entropy(self) -> Any:
            return np.array([0.9], dtype=np.float64)

        @property
        def distribution(self) -> Any:
            return type("P", (), {"probs": np.array([0.7, 0.2, 0.1], dtype=np.float64)})()

    class _Policy:
        training = False

        def eval(self) -> None:
            return None

        def train(self) -> None:
            return None

        def obs_to_tensor(self, obs: Any) -> tuple[Any, None]:
            return np.asarray(obs, dtype=np.float32), None

        def predict_values(self, obs: Any) -> Any:
            _ = obs
            return np.array([[-0.4]], dtype=np.float64)

        def get_distribution(self, obs: Any) -> Any:
            _ = obs
            return _Dist()

    model = type("M", (), {"policy": _Policy()})()
    obs = np.zeros(4, dtype=np.float32)
    taken = extract_policy_signals(model, obs, action=np.array([1.0, 0.5, 0.002, 0.003]))
    assert taken["open_policy_value"] == pytest.approx(-0.4)
    assert taken["open_policy_entropy"] == pytest.approx(0.9)
    assert taken["open_policy_p_chosen"] == pytest.approx(0.2)
    assert taken["open_policy_action_margin"] == pytest.approx(0.2 - 0.7)
    assert taken["open_policy_margin_is_top2"] is False
    fallback = extract_policy_signals(model, obs, action=None)
    assert fallback["open_policy_margin_is_top2"] is True
    assert fallback["open_policy_action_margin"] == pytest.approx(0.5)


def test_extract_empty_when_api_absent() -> None:
    result = extract_policy_signals(object(), np.zeros(4, dtype=np.float32), action=0)
    assert result["open_policy_value"] is None
    assert result["open_policy_entropy"] is None
    assert result["open_policy_action_margin"] is None


def test_extract_does_not_call_learn() -> None:
    class _Bad:
        def learn(self, *args: Any, **kwargs: Any) -> Any:
            raise AssertionError("learn must not be called")

        @property
        def policy(self) -> None:
            return None

    out = extract_policy_signals(_Bad(), np.zeros(4, dtype=np.float32), action=0)
    assert out["open_policy_value"] is None


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


def test_evaluate_only_policy_stores_last_open_signal() -> None:
    class _Inner:
        def predict(self, *args: Any, **kwargs: Any) -> Any:
            _ = args, kwargs
            return [1.0, 0.5, 0.002, 0.003], None

    wrapped = EvaluateOnlyPolicy(_Inner())
    wrapped.predict(np.zeros(4, dtype=np.float32), deterministic=True)
    assert wrapped.last_open_signal is not None
    assert "open_policy_value" in wrapped.last_open_signal


def test_candidate_names_only_three() -> None:
    assert POLICY_CANDIDATE_NAMES == (P_VALUE, P_ENTROPY, P_ACTION_MARGIN)
    assert len(POLICY_CANDIDATE_NAMES) == 3


def test_predicates_do_not_use_bars_held() -> None:
    for rel in (
        "lumina_core/birth/awakening_open_policy_signal.py",
        "lumina_core/birth/awakening_open_policy_signal_flags.py",
    ):
        assert "bars_held" not in Path(rel).read_text(encoding="utf-8")


def test_predicates_do_not_use_mae_r() -> None:
    for rel in (
        "lumina_core/birth/awakening_open_policy_signal.py",
        "lumina_core/birth/awakening_open_policy_signal_flags.py",
    ):
        assert "mae_r" not in Path(rel).read_text(encoding="utf-8")


def test_predicates_do_not_include_open_split_f_names() -> None:
    src = Path("lumina_core/birth/awakening_open_policy_signal_flags.py").read_text(encoding="utf-8")
    for name in ("F_OCC_FLOOR", "F_SESSION_EARLY", "F_TIGHT_RANGE", "F_AFTER_STOP", "F_IMBAL_FLAT"):
        assert name not in src


def test_pred_inclusive_median() -> None:
    assert pred_value_below_median({"open_policy_value": 0.0}, threshold=0.0) is True
    assert pred_entropy_high({"open_policy_entropy": 1.0}, threshold=1.0) is True
    assert pred_action_margin_low({"open_policy_action_margin": 0.5}, threshold=0.5) is True
