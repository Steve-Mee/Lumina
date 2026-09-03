"""Coverage for PATH_EXIT K3 report writers + should_* + inspect. No learn()."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.birth.awakening_path_exit_k3 import (
    FAMILY,
    INIT_SHA256,
    INIT_ZIP_NAME,
    OVERALL_INCONCLUSIVE,
    OVERALL_MEASURE,
    SOURCE,
    T_LOCK,
    PathExitK3ProtocolError,
    honesty_paragraph,
    isolated_workspace,
    overall_path_exit_k3_string,
    should_path_exit_k3,
)
from lumina_core.birth.awakening_path_exit_k3_flags import (
    TAG_HOLE_MOVED,
    compute_path_exit_k3_flags,
    empty_baseline,
    license_from_a,
)
from lumina_core.birth.awakening_path_exit_k3_path import inspect_path_exit_k3_protocol


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
    dump = inspect_path_exit_k3_protocol()
    assert dump["gate0_complete"] is True
    assert dump["missing_sites"] == []
    assert "T_LOCK = -0.04787176712367987" in Path(
        "lumina_core/birth/awakening_path_exit_k3.py"
    ).read_text(encoding="utf-8")
    assert should_path_exit_k3(
        enabled=True, is_policy=True, entry_regime="NEUTRAL", bars_from_entry=3, unreal_r=T_LOCK
    )


def test_coverage_write_reports_and_tables(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_path_exit_k3_report import (
        leg_payload,
        write_path_exit_k3_reports,
    )
    from lumina_core.birth.awakening_path_exit_k3_tables import (
        table_t0,
        table_t1,
        table_t2,
        table_t3,
        table_t4,
        table_t5,
    )

    base = {
        "n_H": 78,
        "mean_r_H": -1.04,
        "n_W": 39,
        "mean_r_W": 1.2,
        "n_policy": 150,
        "wr_policy": 0.307,
        "mean_r_policy": -0.40,
        "n_still_open_at_3": 117,
        "present": True,
    }
    holes = [_row(entry_bar_index=i) for i in range(50)]
    winners = [_row(close_reason="target", trade_r=1.21, pnl=60.0, entry_bar_index=100 + i) for i in range(30)]
    exits = [
        _row(close_reason="force_exit", trade_r=-0.05, pnl=-5.0, path_exit_k3=True, entry_bar_index=200 + i)
        for i in range(40)
    ]
    extra = [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0, entry_bar_index=300 + i) for i in range(30)]
    rows = holes + winners + exits + extra
    baseline_rows = [
        _row(entry_bar_index=200 + i, close_reason="stop") for i in range(25)
    ] + [_row(entry_bar_index=225 + i, close_reason="target", trade_r=1.21, pnl=60.0) for i in range(15)]
    payload = leg_payload(
        rows=rows,
        zip_sha=INIT_SHA256,
        ticks_sha16="7e86c2bb1c71d514",
        price_sha16_value="deadbeef",
        optimizer_steps=0,
        hook_enabled=True,
        baseline=base,
        baseline_rows=baseline_rows,
        skip_replay=False,
        replay_ran=True,
    )
    assert payload["flags"]["tag"] == TAG_HOLE_MOVED
    write_path_exit_k3_reports(
        reports=tmp_path,
        overall=OVERALL_MEASURE,
        zip_sha=INIT_SHA256,
        payload_a=payload,
        payload_b=payload,
        t4={"grind_A": {"absent": True}, "path_early_A": {"absent": True}},
        proto={"gate0_complete": True, "missing_sites": []},
        parent_loaded=True,
        skip_replay=False,
        replay_ran=True,
        gate0_sha="334e367ffeec8fecf01b70f86b1dd84952064ebf",
    )
    verdict = (tmp_path / "AWAKENING_PATH_EXIT_K3_VERDICT.md").read_text(encoding="utf-8")
    audit = (tmp_path / "AWAKENING_PATH_EXIT_K3_AUDIT.md").read_text(encoding="utf-8")
    flags_text = (tmp_path / "artifacts" / "awakening_path_exit_k3_flags.json").read_text(encoding="utf-8")
    assert "Law shipped: SHADOW" in verdict
    assert "PATH_EXIT:P_K3_UNREAL_RED" in verdict
    assert "# AWAKENING_PATH_EXIT_K3_AUDIT" in audit
    assert FAMILY in flags_text
    t0 = table_t0(
        rows,
        zip_sha256="ab",
        ticks_sha16="cd",
        price_sha16_value="ef",
        optimizer_steps=0,
        hook_enabled=True,
    )
    assert t0["n_exit"] == 40
    assert t0["hook_enabled"] is True
    assert table_t1(rows)["n_H"] == 50
    assert table_t2(rows, baseline=base)["delta_n_H"] == 50 - 78
    assert table_t3(n_exit=40)["scale_fail"] is False
    assert table_t5(rows, baseline_rows)["join_absent"] is False
    assert table_t5(rows, None)["join_absent"] is True
    t4 = table_t4(tmp_path)
    assert t4["grind_A"]["absent"] is True
    assert isolated_workspace(tmp_path).as_posix().endswith("awakening_path_exit_k3/workspace")
    assert "flatten-at-3" in honesty_paragraph()
    licensed = license_from_a(payload["flags"], payload["flags"])
    assert licensed["tag"] == TAG_HOLE_MOVED
    assert licensed["law"] == "SHADOW"


def test_coverage_run_skip_replay_writes_inconclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_exit_k3_run as run_mod
    from lumina_core.birth.awakening_path_exit_k3_eval import write_jsonl_sha256
    from lumina_core.birth.awakening_path_exit_k3_run import run_path_exit_k3

    assert write_jsonl_sha256(tmp_path / "empty.jsonl").is_file()
    parent = tmp_path / INIT_ZIP_NAME
    parent.write_bytes(b"PK\x03\x04parent")
    monkeypatch.setattr(
        run_mod, "inspect_path_exit_k3_protocol", lambda: {"gate0_complete": True, "missing_sites": []}
    )
    monkeypatch.setattr(run_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(run_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)
    skipped = run_path_exit_k3(
        reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path, skip_replay=True
    )
    assert skipped["overall"] == OVERALL_INCONCLUSIVE
    assert skipped["skip_replay"] is True
    flags = (tmp_path / "artifacts" / "awakening_path_exit_k3_flags.json").read_text(encoding="utf-8")
    assert '"skip_replay": true' in flags
    assert (tmp_path / "AWAKENING_PATH_EXIT_K3_VERDICT.md").is_file()


def test_coverage_run_evaluate_only_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_exit_k3_run as run_mod
    from lumina_core.birth.awakening_path_exit_k3_run import run_path_exit_k3

    parent = tmp_path / INIT_ZIP_NAME
    parent.write_bytes(b"PK\x03\x04parent")
    (tmp_path / "artifacts").mkdir(parents=True)
    early_a = tmp_path / "artifacts" / "path_early_A_close_ledger.jsonl"
    early_b = tmp_path / "artifacts" / "path_early_B_close_ledger.jsonl"
    early_rows = [_row() for _ in range(78)] + [
        _row(close_reason="target", trade_r=1.21, pnl=60.0) for _ in range(39)
    ] + [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0, bars_held=8) for _ in range(33)]
    early_a.write_text("".join(__import__("json").dumps(r) + "\n" for r in early_rows), encoding="utf-8")
    early_b.write_text(early_a.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(
        run_mod, "inspect_path_exit_k3_protocol", lambda: {"gate0_complete": True, "missing_sites": []}
    )
    monkeypatch.setattr(run_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(run_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)

    def _fixture(workspace: Path, *, seed: int) -> dict[str, Any]:
        _ = workspace, seed
        return {
            "holdout": [{"close": 1.0, "regime": "NEUTRAL"}],
            "ticks_sha16": "7e86c2bb1c71d514",
            "bars_sha16": "x",
            "price_sha16": "aff3cb1e3a6f5014",
        }

    def _eval_leg(**kwargs: Any) -> SimpleNamespace:
        seed = int(kwargs["seed"])
        reports = Path(kwargs["reports"])
        name = "path_exit_k3_A_close_ledger.jsonl" if seed == 20260902 else "path_exit_k3_B_close_ledger.jsonl"
        path = reports / "artifacts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        holes = [_row() for _ in range(50)]
        winners = [_row(close_reason="target", trade_r=1.21, pnl=60.0) for _ in range(30)]
        exits = [
            _row(close_reason="force_exit", trade_r=-0.05, pnl=-5.0, path_exit_k3=True) for _ in range(40)
        ]
        extra = [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0) for _ in range(30)]
        import json as _json

        path.write_text("".join(_json.dumps(r) + "\n" for r in holes + winners + exits + extra), encoding="utf-8")
        return SimpleNamespace(optimizer_steps=0, trajectories=[], rollout_steps=0)

    import lumina_core.birth.awakening_path_exit_k3_eval as eval_mod

    monkeypatch.setattr(eval_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(eval_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)
    monkeypatch.setattr(eval_mod, "_load_or_build_fixture", _fixture)
    monkeypatch.setattr(eval_mod, "run_path_exit_k3_eval_leg", _eval_leg)
    live = run_path_exit_k3(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)
    assert live["parent_loaded"] is True
    assert live["replay_ran"] is True
    assert live["A"]["t0"]["n_policy"] == 150
    assert live["A"]["t0"]["optimizer_steps"] == 0
    src = Path("lumina_core/birth/awakening_path_exit_k3_eval.py").read_text(encoding="utf-8")
    assert "path_exit_k3_shadow=True" in src
    assert SOURCE in src
    monkeypatch.setattr(eval_mod, "run_path_exit_k3_eval_leg", lambda **_k: SimpleNamespace(optimizer_steps=1))
    with pytest.raises(PathExitK3ProtocolError, match="optimizer_steps"):
        run_path_exit_k3(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)


def test_coverage_gate0_incomplete_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_exit_k3_run as run_mod
    from lumina_core.birth.awakening_path_exit_k3_run import run_path_exit_k3

    monkeypatch.setattr(
        run_mod,
        "inspect_path_exit_k3_protocol",
        lambda: {"gate0_complete": False, "missing_sites": ["t_lock"]},
    )
    with pytest.raises(PathExitK3ProtocolError, match="Gate 0"):
        run_path_exit_k3(reports=tmp_path, skip_replay=True)


def test_coverage_overall_and_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_exit_k3_run as run_mod
    from lumina_core.birth.awakening_path_exit_k3_run import main

    assert (
        overall_path_exit_k3_string(parent_loaded=True, skip_replay=False, replay_ran=True, optimizer_steps=0)
        == OVERALL_MEASURE
    )
    assert overall_path_exit_k3_string(skip_replay=True) == OVERALL_INCONCLUSIVE
    assert overall_path_exit_k3_string(replay_ran=True, optimizer_steps=1) == OVERALL_INCONCLUSIVE
    assert overall_path_exit_k3_string(replay_ran=True, s_missing_hook=True) == OVERALL_INCONCLUSIVE
    monkeypatch.setattr(run_mod, "reports_dir", lambda: tmp_path)
    monkeypatch.setattr(
        run_mod,
        "run_path_exit_k3",
        lambda **_k: {
            "overall": OVERALL_INCONCLUSIVE,
            "parent_loaded": False,
            "replay_ran": False,
            "tag": "S_MISSING",
        },
    )
    assert main(["--skip-replay"]) == 0
    flags = compute_path_exit_k3_flags([], baseline=empty_baseline())
    assert flags["S_MISSING_HOOK"] is True
