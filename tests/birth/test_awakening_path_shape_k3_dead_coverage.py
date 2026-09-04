"""Coverage for PATH_SHAPE K3 DEAD inspect, license, report writers, should_* matrix."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.birth.awakening_path_exit_k3 import INIT_SHA256, T_LOCK
from lumina_core.birth.awakening_path_exit_k3_t025 import T_FP
from lumina_core.birth.awakening_path_shape_k3_dead import (
    EPS_SIT,
    FAMILY,
    INIT_ZIP_NAME,
    MFE_LIFE,
    OVERALL_INCONCLUSIVE,
    OVERALL_MEASURE,
    SOURCE,
    PathShapeK3DeadProtocolError,
    honesty_paragraph,
    isolated_workspace,
    overall_path_shape_k3_dead_string,
    should_path_shape_k3_dead,
)
from lumina_core.birth.awakening_path_shape_k3_dead_flags import (
    TAG_SHAPE_NONE,
    TAG_SHAPE_SPLIT,
    TAG_TRANSFER_FAIL,
    TAG_TRANSFER_OK,
    assert_n_exit_not_tfamily_clone,
    compute_shape_measure_flags,
    license_shape,
    license_transfer,
    pred_dead_row,
)
from lumina_core.birth.awakening_path_shape_k3_dead_path import inspect_path_shape_k3_dead_protocol


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
        "entry_bar_index": extra.pop("entry_bar_index", 10),
        "open_side": extra.pop("open_side", 1),
    }
    if entry is not None:
        row["entry_regime"] = entry
    row.update(extra)
    return row


def test_coverage_inspect_complete() -> None:
    dump = inspect_path_shape_k3_dead_protocol()
    assert dump["gate0_complete"] is True
    assert dump["missing_sites"] == []
    core = Path("lumina_core/birth/awakening_path_exit_k3.py").read_text(encoding="utf-8")
    assert "T_LOCK = -0.04787176712367987" in core
    assert EPS_SIT == 0.05
    assert MFE_LIFE == 0.25
    assert T_FP == -0.25
    assert T_LOCK == -0.04787176712367987


def test_coverage_should_matrix() -> None:
    assert should_path_shape_k3_dead(enabled=True, is_policy=True, entry_regime="NEUTRAL", bars_from_entry=3, unreal_r=-0.30, mae_r=-0.30, mfe_r=0.00) is True
    assert should_path_shape_k3_dead(enabled=True, is_policy=True, entry_regime="NEUTRAL", bars_from_entry=3, unreal_r=-0.30, mae_r=-0.30, mfe_r=0.26) is False
    assert should_path_shape_k3_dead(enabled=True, is_policy=True, entry_regime="NEUTRAL", bars_from_entry=3, unreal_r=-0.05, mae_r=-0.80, mfe_r=0.00) is False
    assert should_path_shape_k3_dead(enabled=False, is_policy=True, entry_regime="NEUTRAL", bars_from_entry=3, unreal_r=-0.30, mae_r=-0.30, mfe_r=0.00) is False
    assert should_path_shape_k3_dead(enabled=True, is_policy=False, entry_regime="NEUTRAL", bars_from_entry=3, unreal_r=-0.30, mae_r=-0.30, mfe_r=0.00) is False
    assert should_path_shape_k3_dead(enabled=True, is_policy=True, entry_regime=None, bars_from_entry=3, unreal_r=-0.30, mae_r=-0.30, mfe_r=0.00) is False
    assert should_path_shape_k3_dead(enabled=True, is_policy=True, entry_regime="UNKNOWN", bars_from_entry=3, unreal_r=-0.30, mae_r=-0.30, mfe_r=0.00) is False
    assert should_path_shape_k3_dead(enabled=True, is_policy=True, entry_regime="NEUTRAL", bars_from_entry=2, unreal_r=-0.30, mae_r=-0.30, mfe_r=0.00) is False


def test_coverage_license_and_honesty() -> None:
    split = {"S_SPLIT": True, "S_HARM": False, "S_MISSING": False}
    none = {"S_SPLIT": False, "S_HARM": False, "S_MISSING": False}
    assert license_shape(split, split)["tag"] == TAG_SHAPE_SPLIT
    assert license_shape(split, none)["tag"] == TAG_SHAPE_NONE
    ok = {"HOLE_MOVED": True, "S_HARM": False, "S_MISSING_HOOK": False}
    fail = {"HOLE_MOVED": False, "S_HARM": False, "S_MISSING_HOOK": False}
    assert license_transfer(ok, ok)["tag"] == TAG_TRANSFER_OK
    assert license_transfer(ok, fail)["tag"] == TAG_TRANSFER_FAIL
    text = honesty_paragraph(gate1_tag="SHAPE_NONE", lift_a=0.0, lift_b=0.0, tag="SHAPE_NONE")
    assert "Promoting T_LOCK is forbidden." in text
    assert "T_FP=-0.25 TRANSFER_FAIL" in text
    assert "EPS_SIT=0.05" in text
    assert isolated_workspace(Path("reports") / "birth_cloud_run").as_posix().endswith("awakening_path_shape_k3_dead/workspace")


def test_coverage_measure_tiny_fixture() -> None:
    holes = [_row(entry_bar_index=i, path_k3_unreal_r=-0.30, path_k3_mae_r=-0.30, path_k3_mfe_r=0.00, bars_held=8) for i in range(50)]
    winners = [_row(close_reason="target", trade_r=1.21, pnl=60.0, entry_bar_index=100 + i, path_k3_unreal_r=-0.05, path_k3_mae_r=-0.80, path_k3_mfe_r=0.40, bars_held=8) for i in range(25)]
    extra = [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0, entry_bar_index=200 + i, bars_held=8) for i in range(30)]
    flags = compute_shape_measure_flags(holes + winners + extra)
    assert flags["S_SPLIT"] is True
    assert flags["n_H3"] == 50
    assert flags["n_W3"] == 25
    assert pred_dead_row(holes[0]) is True
    assert pred_dead_row(winners[0]) is False
