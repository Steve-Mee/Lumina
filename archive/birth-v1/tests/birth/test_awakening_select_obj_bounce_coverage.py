"""Coverage for SELECT_OBJ P_BOUNCE_WEAK inspect, license, report, bounce matrix."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from lumina_core.birth.awakening_path_exit_k3 import INIT_SHA256, T_LOCK
from lumina_core.birth.awakening_path_exit_k3_t025 import T_FP
from lumina_core.birth.awakening_path_shape_k3_dead import EPS_SIT, MFE_LIFE
from lumina_core.birth.awakening_select_obj_bounce import (
    BOUNCE_WEAK,
    FAMILY,
    OVERALL_INCONCLUSIVE,
    OVERALL_MEASURE,
    bounce_r,
    honesty_paragraph,
    isolated_workspace,
    overall_select_obj_bounce_string,
    pred_bounce_weak,
)
from lumina_core.birth.awakening_select_obj_bounce_flags import (
    TAG_OBJ_NONE,
    TAG_OBJ_SPLIT,
    compute_obj_bounce_flags,
    license_obj,
    percentile_nearest_rank,
)
from lumina_core.birth.awakening_select_obj_bounce_path import inspect_select_obj_bounce_protocol


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
    dump = inspect_select_obj_bounce_protocol()
    assert dump["gate0_complete"] is True
    assert dump["missing_sites"] == []
    assert EPS_SIT == 0.05
    assert MFE_LIFE == 0.25
    assert T_FP == -0.25
    assert T_LOCK == -0.04787176712367987
    assert BOUNCE_WEAK == 0.50


def test_coverage_bounce_matrix() -> None:
    assert pred_bounce_weak({"path_k3_unreal_r": -3.20, "path_k3_mae_r": -3.50}) is True
    assert pred_bounce_weak({"path_k3_unreal_r": -3.00, "path_k3_mae_r": -3.50}) is True
    assert pred_bounce_weak({"path_k3_unreal_r": -2.90, "path_k3_mae_r": -3.50}) is False
    assert pred_bounce_weak({"path_k3_unreal_r": -0.05, "path_k3_mae_r": -3.51}) is False
    assert pred_bounce_weak({"path_k3_unreal_r": -3.20}) is False
    assert pred_bounce_weak({"path_k3_mae_r": -3.50}) is False
    assert bounce_r({"path_k3_unreal_r": -3.20, "path_k3_mae_r": -3.50}) == pytest.approx(0.30)
    assert percentile_nearest_rank([0.10, 0.20, 0.30, 0.40, 0.50], 0.10) == 0.10
    assert percentile_nearest_rank([], 0.50) is None


def test_coverage_license_and_honesty() -> None:
    split = {"S_SPLIT": True, "S_HARM": False, "S_MISSING": False}
    none = {"S_SPLIT": False, "S_HARM": False, "S_MISSING": False}
    assert license_obj(split, split)["tag"] == TAG_OBJ_SPLIT
    assert license_obj(split, none)["tag"] == TAG_OBJ_NONE
    assert license_obj(split, split)["law"] == "NONE"
    text = honesty_paragraph(gate1_tag="OBJ_NONE", lift_a=0.0, lift_b=0.0, tag="OBJ_NONE")
    assert "Promoting T_LOCK is forbidden." in text
    assert "T_FP=-0.25 TRANSFER_FAIL" in text
    assert "SHAPE_NONE" in text
    assert "BOUNCE_WEAK=0.50" in text
    assert "No flatten." in text
    assert isolated_workspace(Path("reports") / "birth_cloud_run").as_posix().endswith(
        "awakening_select_obj_bounce/workspace"
    )


def test_coverage_measure_tiny_fixture() -> None:
    holes = [
        _row(
            entry_bar_index=i,
            path_k3_unreal_r=-3.20,
            path_k3_mae_r=-3.50,
            bars_held=8,
        )
        for i in range(50)
    ]
    winners = [
        _row(
            close_reason="target",
            trade_r=1.21,
            pnl=60.0,
            entry_bar_index=100 + i,
            path_k3_unreal_r=-2.90,
            path_k3_mae_r=-3.50,
            bars_held=8,
        )
        for i in range(25)
    ]
    extra = [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0, entry_bar_index=200 + i, bars_held=8) for i in range(30)]
    flags = compute_obj_bounce_flags(holes + winners + extra)
    assert flags["S_SPLIT"] is True
    assert flags["n_H3"] == 50
    assert flags["n_W3"] == 25
    assert flags["BOUNCE_WEAK"] == 0.50
    assert flags["min_bounce_U"] == pytest.approx(0.30)
    assert pred_bounce_weak(holes[0]) is True
    assert pred_bounce_weak(winners[0]) is False


def test_coverage_write_reports_and_tables(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_select_obj_bounce_report import write_select_obj_bounce_reports
    from lumina_core.birth.awakening_select_obj_bounce_tables import table_t0, table_t4, table_tm

    holes = [_row(entry_bar_index=i, path_k3_unreal_r=-3.20, path_k3_mae_r=-3.50) for i in range(50)]
    winners = [
        _row(
            close_reason="target",
            trade_r=1.21,
            pnl=60.0,
            entry_bar_index=100 + i,
            path_k3_unreal_r=-2.90,
            path_k3_mae_r=-3.50,
        )
        for i in range(30)
    ]
    extra = [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0, entry_bar_index=300 + i) for i in range(50)]
    rows = holes + winners + extra
    measure = table_tm(rows)
    proto = inspect_select_obj_bounce_protocol()
    flags = write_select_obj_bounce_reports(
        reports=tmp_path,
        overall=OVERALL_MEASURE,
        zip_sha=INIT_SHA256,
        measure_a=measure,
        measure_b=measure,
        proto=proto,
        sha_a="a" * 64,
        sha_b="b" * 64,
        path_early_present=True,
        hooks_false=True,
        gate0_sha="53daabec73a6a303415c267e38203f77b6805f52",
        n_policy=150,
    )
    audit = (tmp_path / "AWAKENING_SELECT_OBJ_BOUNCE_AUDIT.md").read_text(encoding="utf-8")
    verdict = (tmp_path / "AWAKENING_SELECT_OBJ_BOUNCE_VERDICT.md").read_text(encoding="utf-8")
    flags_text = (tmp_path / "artifacts" / "awakening_select_obj_bounce_flags.json").read_text(encoding="utf-8")
    assert "# AWAKENING_SELECT_OBJ_BOUNCE_AUDIT" in audit
    assert "## Gate 0" in audit and "## Score" in audit and "## Honesty" in audit
    assert "## Gate 2" in audit
    assert FAMILY in flags_text
    assert '"BOUNCE_WEAK": 0.5' in flags_text
    assert '"replay_ran": false' in flags_text
    assert '"learn_called": false' in flags_text
    assert flags["law"] == "NONE"
    assert "Law: NONE" in verdict
    t0 = table_t0(rows, sha_a="a", sha_b="b", optimizer_steps=0, hooks_false=True, n_policy=150)
    assert t0["optimizer_steps"] == 0
    assert t0["hooks_false"] is True
    assert t0["BOUNCE_WEAK"] == 0.50
    assert table_t4(tmp_path)["path_early_A"]["absent"] is True
    missing = table_tm(None, present=False)
    assert missing["S_MISSING"] is True


def test_coverage_run_measure_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_select_obj_bounce_run as run_mod
    from lumina_core.birth.awakening_select_obj_bounce_run import run_select_obj_bounce

    skipped = run_select_obj_bounce(reports=tmp_path, workspace_a=tmp_path)
    assert skipped["replay_ran"] is False
    flags = (tmp_path / "artifacts" / "awakening_select_obj_bounce_flags.json").read_text(encoding="utf-8")
    assert '"replay_ran": false' in flags
    assert '"learn_called": false' in flags
    assert (tmp_path / "AWAKENING_SELECT_OBJ_BOUNCE_VERDICT.md").is_file()
    monkeypatch.setattr(run_mod, "reports_dir", lambda: tmp_path)
    from lumina_core.birth.awakening_select_obj_bounce_run import main

    assert overall_select_obj_bounce_string(gate1_complete=True) == OVERALL_MEASURE
    assert overall_select_obj_bounce_string(optimizer_steps=1, gate1_complete=True) == OVERALL_INCONCLUSIVE
    assert overall_select_obj_bounce_string(hook_true=True) == OVERALL_INCONCLUSIVE
    monkeypatch.setattr(
        run_mod,
        "run_select_obj_bounce",
        lambda **_k: {
            "overall": OVERALL_MEASURE,
            "parent_loaded": False,
            "replay_ran": False,
            "learn_called": False,
            "tag": "OBJ_NONE",
            "gate1_tag": "OBJ_NONE",
            "law": "NONE",
            "licensed_next_family": "H_NONE",
        },
    )
    assert main([]) == 0
