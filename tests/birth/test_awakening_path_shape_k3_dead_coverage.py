"""Coverage for PATH_SHAPE K3 DEAD inspect, license, report writers, should_* matrix."""

from __future__ import annotations

from pathlib import Path
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
    kwargs = dict(enabled=True, is_policy=True, entry_regime="NEUTRAL", bars_from_entry=3, unreal_r=-0.30, mae_r=-0.30, mfe_r=0.00)
    assert should_path_shape_k3_dead(**kwargs) is True
    assert should_path_shape_k3_dead(**{**kwargs, "mfe_r": 0.26}) is False
    assert should_path_shape_k3_dead(**{**kwargs, "unreal_r": -0.05, "mae_r": -0.80}) is False
    assert should_path_shape_k3_dead(**{**kwargs, "enabled": False}) is False
    assert should_path_shape_k3_dead(**{**kwargs, "is_policy": False}) is False
    assert should_path_shape_k3_dead(**{**kwargs, "entry_regime": None}) is False
    assert should_path_shape_k3_dead(**{**kwargs, "entry_regime": "UNKNOWN"}) is False
    assert should_path_shape_k3_dead(**{**kwargs, "bars_from_entry": 2}) is False


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


def test_coverage_write_reports_and_tables(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_path_shape_k3_dead_report import leg_payload, write_path_shape_k3_dead_reports
    from lumina_core.birth.awakening_path_shape_k3_dead_tables import table_t0, table_t1, table_t2, table_t3, table_t4, table_tm

    base = {"n_H": 78, "mean_r_H": -1.04, "n_W": 39, "mean_r_W": 1.2, "n_policy": 150, "wr_policy": 0.307, "mean_r_policy": -0.40, "n_still_open_at_3": 117, "present": True}
    holes = [_row(entry_bar_index=i) for i in range(50)]
    winners = [_row(close_reason="target", trade_r=1.21, pnl=60.0, entry_bar_index=100 + i) for i in range(30)]
    exits = [_row(close_reason="force_exit", trade_r=-0.20, pnl=-12.0, path_exit_k3=True, path_exit_k3_shape="DEAD", path_exit_k3_mae_r=-0.30, path_exit_k3_mfe_r=0.0, path_exit_k3_family=FAMILY, entry_bar_index=200 + i) for i in range(20)]
    extra = [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0, entry_bar_index=300 + i) for i in range(50)]
    rows = holes + winners + exits + extra
    payload = leg_payload(rows=rows, zip_sha=INIT_SHA256, ticks_sha16="7e86c2bb1c71d514", price_sha16_value="deadbeef", optimizer_steps=0, hook_enabled=True, shape_enabled=True, t_family_enabled=False, baseline=base, skip_replay=False, replay_ran=True, artifacts=tmp_path / "artifacts", leg="A")
    assert payload["mean_stamped_shape"] == "DEAD"
    measure = table_tm(rows)
    write_path_shape_k3_dead_reports(reports=tmp_path, overall=OVERALL_MEASURE, zip_sha=INIT_SHA256, payload_a=payload, payload_b=payload, measure_a=measure, measure_b=measure, t4={"grind_A": {"absent": True}, "path_early_A": {"absent": True}}, proto={"gate0_complete": True, "missing_sites": []}, parent_loaded=True, skip_replay=False, replay_ran=True, gate0_sha="eb3184db8a7931991752e0e3eef3f1149269d20f")
    audit = (tmp_path / "AWAKENING_PATH_SHAPE_K3_DEAD_AUDIT.md").read_text(encoding="utf-8")
    verdict = (tmp_path / "AWAKENING_PATH_SHAPE_K3_DEAD_VERDICT.md").read_text(encoding="utf-8")
    flags_text = (tmp_path / "artifacts" / "awakening_path_shape_k3_dead_flags.json").read_text(encoding="utf-8")
    assert "# AWAKENING_PATH_SHAPE_K3_DEAD_AUDIT" in audit
    assert "## Gate 0" in audit and "## Hook" in audit and "## Honesty" in audit
    assert FAMILY in flags_text
    assert '"EPS_SIT": 0.05' in flags_text
    assert "Law: SHADOW default off | NONE." in verdict
    t0 = table_t0(rows, zip_sha256="ab", ticks_sha16="cd", price_sha16_value="ef", optimizer_steps=0, hook_enabled=True, shape_enabled=True, t_family_enabled=False)
    assert t0["mean_stamped_shape"] == "DEAD"
    assert t0["n_exit"] == 20
    assert table_t1(rows)["n_H"] == 50
    assert table_t2(rows, baseline=base)["delta_n_H"] == 50 - 78
    assert table_t3(n_exit=20, artifacts=tmp_path, leg="A")["n_exit_shape"] == 20
    assert table_t4(tmp_path)["grind_A"]["absent"] is True
    assert SOURCE in t0["source"]


def test_coverage_run_measure_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_shape_k3_dead_run as run_mod
    from lumina_core.birth.awakening_path_shape_k3_dead_eval import write_jsonl_sha256
    from lumina_core.birth.awakening_path_shape_k3_dead_run import run_path_shape_k3_dead

    assert write_jsonl_sha256(tmp_path / "empty.jsonl").is_file()
    parent = tmp_path / INIT_ZIP_NAME
    parent.write_bytes(b"PK\x03\x04parent")
    monkeypatch.setattr(run_mod, "inspect_path_shape_k3_dead_protocol", lambda: {"gate0_complete": True, "missing_sites": []})
    monkeypatch.setattr(run_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(run_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)
    skipped = run_path_shape_k3_dead(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path, skip_replay=True)
    assert skipped["replay_ran"] is False
    flags = (tmp_path / "artifacts" / "awakening_path_shape_k3_dead_flags.json").read_text(encoding="utf-8")
    assert '"replay_ran": false' in flags
    assert (tmp_path / "AWAKENING_PATH_SHAPE_K3_DEAD_VERDICT.md").is_file()


def test_coverage_overall_and_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_shape_k3_dead_run as run_mod
    from lumina_core.birth.awakening_path_shape_k3_dead_run import main

    assert overall_path_shape_k3_dead_string(gate1_complete=True) == OVERALL_MEASURE
    assert overall_path_shape_k3_dead_string(skip_replay=True, gate2_attempted=True) == OVERALL_INCONCLUSIVE
    assert overall_path_shape_k3_dead_string(replay_ran=True, optimizer_steps=1, gate2_attempted=True) == OVERALL_INCONCLUSIVE
    assert overall_path_shape_k3_dead_string(replay_ran=True, s_missing_hook=True, gate2_attempted=True) == OVERALL_INCONCLUSIVE
    assert overall_path_shape_k3_dead_string(replay_ran=True, tfamily_clone=True, gate2_attempted=True) == OVERALL_INCONCLUSIVE
    assert overall_path_shape_k3_dead_string(both_shadows=True) == OVERALL_INCONCLUSIVE
    monkeypatch.setattr(run_mod, "reports_dir", lambda: tmp_path)
    monkeypatch.setattr(run_mod, "run_path_shape_k3_dead", lambda **_k: {"overall": OVERALL_MEASURE, "parent_loaded": False, "replay_ran": False, "tag": "SHAPE_NONE", "gate1_tag": "SHAPE_NONE", "HOLE_MOVED_A": False, "HOLE_MOVED_B": False})
    assert main(["--skip-replay"]) == 0


def test_coverage_assert_n_exit_clone() -> None:
    with pytest.raises(PathShapeK3DeadProtocolError, match=">= 80"):
        assert_n_exit_not_tfamily_clone(n_exit_a=80, exits_a=[], mean_stamped_threshold_a=None)
    with pytest.raises(PathShapeK3DeadProtocolError, match="DEAD"):
        assert_n_exit_not_tfamily_clone(n_exit_a=20, exits_a=[{"path_exit_k3": True}], mean_stamped_threshold_a=None)
    ok = [{"path_exit_k3": True, "path_exit_k3_shape": "DEAD", "path_exit_k3_mae_r": -0.3, "path_exit_k3_mfe_r": 0.0}]
    assert_n_exit_not_tfamily_clone(n_exit_a=1, exits_a=ok, mean_stamped_threshold_a=None)
    with pytest.raises(PathShapeK3DeadProtocolError, match="T_LOCK"):
        assert_n_exit_not_tfamily_clone(n_exit_a=1, exits_a=ok, mean_stamped_threshold_a=T_LOCK)
