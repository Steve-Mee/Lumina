"""Awakening OPEN_POLICY_SIGNAL: protocol, flags, extraction, eval wrap."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.awakening_grind import TRAIN
from lumina_core.birth.awakening_open_policy_signal import (
    FORBIDDEN_WRITE_NAMES,
    SIGNAL_A_NAME,
    SIGNAL_B_NAME,
    TRAIN_SEED,
    OpenPolicySignalProtocolError,
    assert_eval_seed,
    assert_isolated_write,
    assert_not_evaluated_policy,
    isolated_workspace,
)
from lumina_core.birth.awakening_open_policy_signal_flags import (
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


def _universe_with_signals(
    *,
    n_h: int,
    n_w: int,
    n_other: int = 20,
    h_value: float = -0.5,
    w_value: float = 0.5,
    h_entropy: float = 1.5,
    w_entropy: float = 0.3,
    h_margin: float = 0.1,
    w_margin: float = 0.7,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _ in range(n_h):
        rows.append(_row(
            close_reason="stop", regime="NEUTRAL", trade_r=-1.04, pnl=-117.0,
            open_policy_value=h_value,
            open_policy_entropy=h_entropy,
            open_policy_action_margin=h_margin,
        ))
    for _ in range(n_w):
        rows.append(_row(
            close_reason="target", regime="NEUTRAL", trade_r=1.21, pnl=60.0,
            open_policy_value=w_value,
            open_policy_entropy=w_entropy,
            open_policy_action_margin=w_margin,
        ))
    for _ in range(n_other):
        rows.append(_row(
            close_reason="time_stop", regime="NEUTRAL", trade_r=-0.1, pnl=-5.0,
            open_policy_value=0.0,
            open_policy_entropy=0.9,
            open_policy_action_margin=0.4,
        ))
    return rows


def test_inspect_open_policy_signal_protocol_complete() -> None:
    dump = inspect_open_policy_signal_protocol()
    assert dump["gate0_complete"] is True, f"missing: {dump['missing_sites']}"
    assert dump["missing_sites"] == []


def test_candidate_names_only_three() -> None:
    assert POLICY_CANDIDATE_NAMES == (P_VALUE, P_ENTROPY, P_ACTION_MARGIN)
    assert len(POLICY_CANDIDATE_NAMES) == 3


def test_runner_refuses_train_seed() -> None:
    with pytest.raises(OpenPolicySignalProtocolError, match="train seed"):
        assert_eval_seed(TRAIN_SEED)


def test_forbidden_write_parent_zip(tmp_path: Path) -> None:
    with pytest.raises(OpenPolicySignalProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "birth_exit_pi_star.zip")
    assert SIGNAL_A_NAME not in FORBIDDEN_WRITE_NAMES
    assert SIGNAL_B_NAME not in FORBIDDEN_WRITE_NAMES
    assert isolated_workspace(tmp_path).as_posix().endswith("awakening_open_policy_signal/workspace")
    assert TRAIN is False


def test_forbidden_write_open_split_jsonl(tmp_path: Path) -> None:
    with pytest.raises(OpenPolicySignalProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "open_split_A_close_ledger.jsonl")
    with pytest.raises(OpenPolicySignalProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "open_split_B_close_ledger.jsonl")


def test_assert_not_evaluated_policy_refuses_control(tmp_path: Path) -> None:
    control = tmp_path / "awakening_select_pi_star.zip"
    control.write_bytes(b"PK\x03\x04select-child")
    with pytest.raises(OpenPolicySignalProtocolError, match="evaluated policy"):
        assert_not_evaluated_policy(control)


def test_adaptive_thresholds_median() -> None:
    rows = [
        {"open_policy_value": 1.0, "open_policy_entropy": 2.0, "open_policy_action_margin": 0.8},
        {"open_policy_value": 3.0, "open_policy_entropy": 4.0, "open_policy_action_margin": 0.2},
        {"open_policy_value": 5.0, "open_policy_entropy": 6.0, "open_policy_action_margin": 0.5},
    ]
    thr = compute_adaptive_thresholds(rows)
    assert thr["value_median"] == pytest.approx(3.0)
    assert thr["entropy_median"] == pytest.approx(4.0)
    assert thr["action_margin_median"] == pytest.approx(0.5)


def test_pred_value_below_median() -> None:
    assert pred_value_below_median({"open_policy_value": -1.0}, threshold=0.0) is True
    assert pred_value_below_median({"open_policy_value": 1.0}, threshold=0.0) is False
    assert pred_value_below_median({}, threshold=0.0) is False


def test_pred_entropy_high() -> None:
    assert pred_entropy_high({"open_policy_entropy": 2.0}, threshold=1.0) is True
    assert pred_entropy_high({"open_policy_entropy": 0.5}, threshold=1.0) is False
    assert pred_entropy_high({}, threshold=1.0) is False


def test_pred_action_margin_low() -> None:
    assert pred_action_margin_low({"open_policy_action_margin": 0.1}, threshold=0.5) is True
    assert pred_action_margin_low({"open_policy_action_margin": 0.9}, threshold=0.5) is False
    assert pred_action_margin_low({}, threshold=0.5) is False


def test_s_none_when_no_separation() -> None:
    rows = _universe_with_signals(
        n_h=50, n_w=30, n_other=20,
        h_value=0.0, w_value=0.0,
        h_entropy=1.0, w_entropy=1.0,
        h_margin=0.5, w_margin=0.5,
    )
    flags = compute_open_policy_signal_flags(rows)
    assert flags["tag"] == "S_NONE"
    assert flags["winning_P"] == "none"


def test_s_split_value_separates() -> None:
    rows = _universe_with_signals(
        n_h=50, n_w=30, n_other=20,
        h_value=-2.0, w_value=2.0,
        h_entropy=1.0, w_entropy=1.0,
        h_margin=0.5, w_margin=0.5,
    )
    flags = compute_open_policy_signal_flags(rows)
    if flags["candidates"][P_VALUE]["S_SPLIT"]:
        assert flags["tag"] == "S_SPLIT"
        assert flags["winning_P"] == P_VALUE


def test_s_thin_small_hole() -> None:
    rows = _universe_with_signals(n_h=30, n_w=30, n_other=20)
    flags = compute_open_policy_signal_flags(rows)
    assert flags["S_THIN"] is True
    assert flags["tag"] == "S_THIN"


def test_s_missing_u() -> None:
    rows = _universe_with_signals(n_h=50, n_w=30, n_other=0)
    for _ in range(20):
        rows.append(_row(entry=None, close_reason="flatten", regime="NEUTRAL", trade_r=0.0, pnl=0.0))
    flags = compute_open_policy_signal_flags(rows)
    assert flags["S_MISSING_U"] is True
    assert flags["tag"] == "S_MISSING"


def test_license_s_none() -> None:
    flags = {"tag": "S_NONE", "winning_P": "none", "S_MISSING_U": False, "S_THIN": False}
    licensed = license_from_ab(flags, flags)
    assert licensed["tag"] == "S_NONE"
    assert licensed["licensed_next_family"] == "H_NONE"


def test_license_s_split_agree() -> None:
    flags = {"tag": "S_SPLIT", "winning_P": "P_VALUE", "S_MISSING_U": False, "S_THIN": False}
    licensed = license_from_ab(flags, flags)
    assert licensed["tag"] == "S_SPLIT"
    assert licensed["licensed_next_family"] == "OPEN_FILTER:POLICY_P_VALUE"


def test_license_s_ab_disagree() -> None:
    flags_a = {"tag": "S_SPLIT", "winning_P": "P_VALUE", "S_MISSING_U": False, "S_THIN": False}
    flags_b = {"tag": "S_SPLIT", "winning_P": "P_ENTROPY", "S_MISSING_U": False, "S_THIN": False}
    licensed = license_from_ab(flags_a, flags_b)
    assert licensed["tag"] == "S_AB_DISAGREE"


def test_extract_policy_signals_none_model() -> None:
    import numpy as np
    result = extract_policy_signals(None, np.zeros(10, dtype=np.float32))
    assert result["open_policy_value"] is None
    assert result["open_policy_entropy"] is None
    assert result["open_policy_action_margin"] is None


def test_close_ledger_row_copies_policy_signal_keys() -> None:
    filled = close_ledger_row({
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
        "open_policy_value": -0.3,
        "open_policy_entropy": 1.2,
        "open_policy_action_margin": 0.15,
    })
    assert filled["open_policy_value"] == pytest.approx(-0.3)
    assert filled["open_policy_entropy"] == pytest.approx(1.2)
    assert filled["open_policy_action_margin"] == pytest.approx(0.15)


def test_close_ledger_row_omits_missing_policy_signals() -> None:
    row = close_ledger_row({
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
    })
    assert "open_policy_value" not in row
    assert "open_policy_entropy" not in row
    assert "open_policy_action_margin" not in row


def test_source_does_not_implement_open_filter() -> None:
    for rel in (
        "lumina_core/birth/awakening_open_policy_signal.py",
        "lumina_core/birth/awakening_open_policy_signal_flags.py",
        "lumina_core/birth/awakening_open_policy_signal_run.py",
        "lumina_core/birth/awakening_open_policy_signal_tables.py",
        "lumina_core/birth/awakening_open_policy_signal_report.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        assert "def apply_open_filter" not in src
        assert "def refuse_neutral_open" not in src
        assert "decide_stage2_participation(" not in src


def test_source_does_not_call_learn() -> None:
    for rel in (
        "lumina_core/birth/awakening_open_policy_signal_run.py",
        "lumina_core/birth/policy_signal_extract.py",
    ):
        src = Path(rel).read_text(encoding="utf-8")
        assert "model.learn(" not in src
        assert ".learn(" not in src or "learn() forbidden" in src


def test_start_open_telem_accepts_policy_signals() -> None:
    from lumina_core.birth.sim_runner_entry_telem import start_open_telem

    stash = start_open_telem(
        entry_regime="NEUTRAL",
        entry_bar_index=2,
        entry_price=20000.0,
        side=1,
        open_policy_value=-0.5,
        open_policy_entropy=1.3,
        open_policy_action_margin=0.2,
    )
    assert stash["open_policy_value"] == pytest.approx(-0.5)
    assert stash["open_policy_entropy"] == pytest.approx(1.3)
    assert stash["open_policy_action_margin"] == pytest.approx(0.2)


def test_start_open_telem_omits_none_policy_signals() -> None:
    from lumina_core.birth.sim_runner_entry_telem import start_open_telem

    stash = start_open_telem(
        entry_regime="NEUTRAL",
        entry_bar_index=2,
        entry_price=20000.0,
        side=1,
    )
    assert "open_policy_value" not in stash
    assert "open_policy_entropy" not in stash
    assert "open_policy_action_margin" not in stash
