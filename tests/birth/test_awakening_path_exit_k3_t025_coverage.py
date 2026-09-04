"""Coverage for PATH_EXIT K3 T025 inspect, license, report writers, should_* matrix."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.birth.awakening_path_exit_k3 import INIT_SHA256, T_LOCK, should_path_exit_k3
from lumina_core.birth.awakening_path_exit_k3_t025 import (
    FAMILY,
    INIT_ZIP_NAME,
    OVERALL_INCONCLUSIVE,
    OVERALL_MEASURE,
    SOURCE,
    T_FP,
    PathExitK3T025ProtocolError,
    honesty_paragraph,
    isolated_workspace,
    overall_path_exit_k3_t025_string,
)
from lumina_core.birth.awakening_path_exit_k3_t025_flags import (
    TAG_TRANSFER_FAIL,
    TAG_TRANSFER_OK,
    license_transfer,
)
from lumina_core.birth.awakening_path_exit_k3_t025_path import inspect_path_exit_k3_t025_protocol


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
    dump = inspect_path_exit_k3_t025_protocol()
    assert dump["gate0_complete"] is True
    assert dump["missing_sites"] == []
    core = Path("lumina_core/birth/awakening_path_exit_k3.py").read_text(encoding="utf-8")
    assert "T_LOCK = -0.04787176712367987" in core
    assert "thr = path_exit_k3_threshold()" in core
    assert T_FP == -0.25


def test_coverage_should_matrix() -> None:
    base = dict(
        enabled=True,
        is_policy=True,
        entry_regime="NEUTRAL",
        bars_from_entry=3,
        unreal_r=T_FP,
        threshold=T_FP,
    )
    assert should_path_exit_k3(**base) is True
    assert should_path_exit_k3(**{**base, "unreal_r": -0.24}) is False
    assert should_path_exit_k3(**{**base, "threshold": None, "unreal_r": -0.24}) is True
    assert should_path_exit_k3(**{**base, "enabled": False}) is False
    assert should_path_exit_k3(**{**base, "is_policy": False}) is False
    assert should_path_exit_k3(**{**base, "bars_from_entry": 2}) is False
    assert should_path_exit_k3(**{**base, "unreal_r": None}) is False
    assert should_path_exit_k3(**{**base, "entry_regime": None}) is False
    assert should_path_exit_k3(**{**base, "entry_regime": "UNKNOWN"}) is False
    assert float(T_LOCK) == -0.04787176712367987


def test_coverage_license_and_honesty() -> None:
    ok = {"HOLE_MOVED": True, "S_HARM": False, "S_MISSING_HOOK": False}
    fail = {"HOLE_MOVED": False, "S_HARM": False, "S_MISSING_HOOK": False}
    assert license_transfer(ok, ok)["tag"] == TAG_TRANSFER_OK
    assert license_transfer(ok, fail)["tag"] == TAG_TRANSFER_FAIL
    text = honesty_paragraph(
        skip_replay=False,
        n_exit_a=10,
        n_exit_b=8,
        n_h_base_a=78,
        n_h_t025_a=60,
        n_h_base_b=83,
        n_h_t025_b=70,
        mean_r_base_a=-0.3,
        mean_r_t025_a=-0.2,
        mean_r_base_b=-0.18,
        mean_r_t025_b=-0.22,
        hole_moved_a=True,
        hole_moved_b=False,
        tag=TAG_TRANSFER_FAIL,
    )
    assert "Promoting T_LOCK is forbidden." in text
    assert "T_FP=-0.25" in text
    assert "HOLE_MOVED A/B=true/false." in text
    assert "Tag: TRANSFER_FAIL." in text
    assert isolated_workspace(Path("reports") / "birth_cloud_run").as_posix().endswith(
        "awakening_path_exit_k3_t025/workspace"
    )


def test_coverage_write_reports_and_tables(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_path_exit_k3_t025_report import (
        leg_payload,
        write_path_exit_k3_t025_reports,
    )
    from lumina_core.birth.awakening_path_exit_k3_t025_tables import (
        table_t0,
        table_t1,
        table_t2,
        table_t3,
        table_t4,
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
        _row(
            close_reason="force_exit",
            trade_r=-0.25,
            pnl=-12.0,
            path_exit_k3=True,
            path_exit_k3_threshold=T_FP,
            entry_bar_index=200 + i,
        )
        for i in range(20)
    ]
    extra = [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0, entry_bar_index=300 + i) for i in range(50)]
    rows = holes + winners + exits + extra
    payload = leg_payload(
        rows=rows,
        zip_sha=INIT_SHA256,
        ticks_sha16="7e86c2bb1c71d514",
        price_sha16_value="deadbeef",
        optimizer_steps=0,
        hook_enabled=True,
        baseline=base,
        skip_replay=False,
        replay_ran=True,
        artifacts=tmp_path / "artifacts",
        leg="A",
    )
    assert payload["mean_stamped_threshold"] == T_FP
    write_path_exit_k3_t025_reports(
        reports=tmp_path,
        overall=OVERALL_MEASURE,
        zip_sha=INIT_SHA256,
        payload_a=payload,
        payload_b=payload,
        t4={"grind_A": {"absent": True}, "path_early_A": {"absent": True}, "path_exit_k3_A": {"absent": True}},
        proto={"gate0_complete": True, "missing_sites": []},
        parent_loaded=True,
        skip_replay=False,
        replay_ran=True,
        gate0_sha="a694f3f55f4bc7f3bb5abf8fecc6d09481ec200e",
    )
    verdict = (tmp_path / "AWAKENING_PATH_EXIT_K3_T025_VERDICT.md").read_text(encoding="utf-8")
    audit = (tmp_path / "AWAKENING_PATH_EXIT_K3_T025_AUDIT.md").read_text(encoding="utf-8")
    flags_text = (tmp_path / "artifacts" / "awakening_path_exit_k3_t025_flags.json").read_text(
        encoding="utf-8"
    )
    assert "# AWAKENING_PATH_EXIT_K3_T025_AUDIT" in audit
    assert "## Gate 0" in audit
    assert "## Hook" in audit
    assert "## Source" in audit
    assert "## Replay" in audit
    assert "## Flags" in audit
    assert "## n_exit vs T_LOCK clone" in audit
    assert "## Honesty" in audit
    assert "Law: SHADOW default off." in verdict
    assert FAMILY in flags_text
    assert '"T_FP": -0.25' in flags_text
    t0 = table_t0(
        rows,
        zip_sha256="ab",
        ticks_sha16="cd",
        price_sha16_value="ef",
        optimizer_steps=0,
        hook_enabled=True,
    )
    assert t0["T_FP"] == -0.25
    assert t0["mean_stamped_threshold"] == T_FP
    assert t0["n_exit"] == 20
    assert table_t1(rows)["n_H"] == 50
    assert table_t2(rows, baseline=base)["delta_n_H"] == 50 - 78
    assert table_t3(n_exit=20, n_exit_k27=50)["n_exit_k27"] == 50
    t4 = table_t4(tmp_path)
    assert t4["grind_A"]["absent"] is True
    assert t4["path_exit_k3_A"]["absent"] is True
    assert SOURCE in t0["source"]


def test_coverage_run_skip_replay_writes_inconclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_exit_k3_t025_run as run_mod
    from lumina_core.birth.awakening_path_exit_k3_t025_eval import write_jsonl_sha256
    from lumina_core.birth.awakening_path_exit_k3_t025_run import run_path_exit_k3_t025

    assert write_jsonl_sha256(tmp_path / "empty.jsonl").is_file()
    parent = tmp_path / INIT_ZIP_NAME
    parent.write_bytes(b"PK\x03\x04parent")
    monkeypatch.setattr(
        run_mod,
        "inspect_path_exit_k3_t025_protocol",
        lambda: {"gate0_complete": True, "missing_sites": []},
    )
    monkeypatch.setattr(run_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(run_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)
    skipped = run_path_exit_k3_t025(
        reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path, skip_replay=True
    )
    assert skipped["overall"] == OVERALL_INCONCLUSIVE
    assert skipped["skip_replay"] is True
    flags = (tmp_path / "artifacts" / "awakening_path_exit_k3_t025_flags.json").read_text(encoding="utf-8")
    assert '"skip_replay": true' in flags
    assert (tmp_path / "AWAKENING_PATH_EXIT_K3_T025_VERDICT.md").is_file()


def test_coverage_run_evaluate_only_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_exit_k3_t025_run as run_mod
    from lumina_core.birth.awakening_path_exit_k3_t025_run import run_path_exit_k3_t025

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
        run_mod,
        "inspect_path_exit_k3_t025_protocol",
        lambda: {"gate0_complete": True, "missing_sites": []},
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
        name = (
            "path_exit_k3_t025_A_close_ledger.jsonl"
            if seed == 20260902
            else "path_exit_k3_t025_B_close_ledger.jsonl"
        )
        path = reports / "artifacts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        holes = [_row() for _ in range(50)]
        winners = [_row(close_reason="target", trade_r=1.21, pnl=60.0) for _ in range(30)]
        exits = [
            _row(
                close_reason="force_exit",
                trade_r=-0.25,
                pnl=-12.0,
                path_exit_k3=True,
                path_exit_k3_threshold=T_FP,
            )
            for _ in range(20)
        ]
        extra = [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0) for _ in range(50)]
        import json as _json

        path.write_text("".join(_json.dumps(r) + "\n" for r in holes + winners + exits + extra), encoding="utf-8")
        return SimpleNamespace(optimizer_steps=0, trajectories=[], rollout_steps=0)

    import lumina_core.birth.awakening_path_exit_k3_t025_eval as eval_mod

    monkeypatch.setattr(eval_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(eval_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)
    monkeypatch.setattr(eval_mod, "_load_or_build_fixture", _fixture)
    monkeypatch.setattr(eval_mod, "run_path_exit_k3_t025_eval_leg", _eval_leg)
    live = run_path_exit_k3_t025(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)
    assert live["parent_loaded"] is True
    assert live["replay_ran"] is True
    assert live["A"]["t0"]["n_policy"] == 150
    assert live["A"]["t0"]["optimizer_steps"] == 0
    assert live["A"]["mean_stamped_threshold"] == T_FP
    src = Path("lumina_core/birth/awakening_path_exit_k3_t025_eval.py").read_text(encoding="utf-8")
    assert "PATH_EXIT_K3_THRESHOLD.set" in src
    assert SOURCE in src
    monkeypatch.setattr(eval_mod, "run_path_exit_k3_t025_eval_leg", lambda **_k: SimpleNamespace(optimizer_steps=1))
    with pytest.raises(PathExitK3T025ProtocolError, match="optimizer_steps"):
        run_path_exit_k3_t025(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)


def test_coverage_gate0_incomplete_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_exit_k3_t025_run as run_mod
    from lumina_core.birth.awakening_path_exit_k3_t025_run import run_path_exit_k3_t025

    monkeypatch.setattr(
        run_mod,
        "inspect_path_exit_k3_t025_protocol",
        lambda: {"gate0_complete": False, "missing_sites": ["t_fp"]},
    )
    with pytest.raises(PathExitK3T025ProtocolError, match="Gate 0"):
        run_path_exit_k3_t025(reports=tmp_path, skip_replay=True)


def test_coverage_overall_and_main(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_exit_k3_t025_run as run_mod
    from lumina_core.birth.awakening_path_exit_k3_t025_run import main

    assert (
        overall_path_exit_k3_t025_string(
            parent_loaded=True, skip_replay=False, replay_ran=True, optimizer_steps=0
        )
        == OVERALL_MEASURE
    )
    assert overall_path_exit_k3_t025_string(skip_replay=True) == OVERALL_INCONCLUSIVE
    assert overall_path_exit_k3_t025_string(replay_ran=True, optimizer_steps=1) == OVERALL_INCONCLUSIVE
    assert overall_path_exit_k3_t025_string(replay_ran=True, s_missing_hook=True) == OVERALL_INCONCLUSIVE
    assert overall_path_exit_k3_t025_string(replay_ran=True, tlock_clone=True) == OVERALL_INCONCLUSIVE
    monkeypatch.setattr(run_mod, "reports_dir", lambda: tmp_path)
    monkeypatch.setattr(
        run_mod,
        "run_path_exit_k3_t025",
        lambda **_k: {
            "overall": OVERALL_INCONCLUSIVE,
            "parent_loaded": False,
            "replay_ran": False,
            "tag": "S_MISSING",
            "HOLE_MOVED_A": False,
            "HOLE_MOVED_B": False,
        },
    )
    assert main(["--skip-replay"]) == 0
