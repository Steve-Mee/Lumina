"""Coverage for PATH_UNREAL_K3 run/report/tables/inspect/flags/license. No learn()."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.birth.awakening_path_unreal_k3 import (
    INIT_SHA256,
    INIT_ZIP_NAME,
    OVERALL_INCONCLUSIVE,
    OVERALL_MEASURE,
    SOURCE,
    PathUnrealK3ProtocolError,
    honesty_paragraph,
    isolated_workspace,
    overall_path_unreal_k3_string,
)
from lumina_core.birth.awakening_path_unreal_k3_flags import (
    CANDIDATE_NAMES,
    FAMILY_H_NONE,
    FAMILY_PATH_EXIT_P_K3_UNREAL_RED,
    P_K3_UNREAL_RED,
    compute_path_unreal_k3_flags,
    license_from_ab_k3,
)
from lumina_core.birth.awakening_path_unreal_k3_path import inspect_path_unreal_k3_protocol


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


def _rows_split() -> list[dict[str, Any]]:
    rows = [_row(path_k3_unreal_r=-1.0, path_k3_mae_r=-2.0, path_k3_mfe_r=0.2) for _ in range(50)]
    rows += [
        _row(
            close_reason="target",
            trade_r=1.21,
            pnl=60.0,
            path_k3_unreal_r=0.3,
            path_k3_mae_r=0.0,
            path_k3_mfe_r=0.8,
        )
        for _ in range(30)
    ]
    return rows


def test_coverage_inspect_complete() -> None:
    dump = inspect_path_unreal_k3_protocol()
    assert dump["gate0_complete"] is True
    assert dump["missing_sites"] == []
    assert "PATH_EXIT:P_K3_UNREAL_RED" in Path(
        "lumina_core/birth/awakening_path_unreal_k3_flags.py"
    ).read_text(encoding="utf-8")
    assert "K_LOCKED = 3" in Path("lumina_core/birth/awakening_path_unreal_k3_flags.py").read_text(
        encoding="utf-8"
    )


def test_coverage_flags_and_license() -> None:
    rows = _rows_split()
    flags = compute_path_unreal_k3_flags(rows)
    assert list(flags["candidates"]) == [P_K3_UNREAL_RED]
    assert flags["gate1"] == "NONE"
    assert CANDIDATE_NAMES == (P_K3_UNREAL_RED,)
    licensed_split = license_from_ab_k3(
        {"tag": "S_SPLIT", "S_MISSING_U": False, "S_MISSING_PATH": False, "S_THIN": False},
        {"tag": "S_SPLIT", "S_MISSING_U": False, "S_MISSING_PATH": False, "S_THIN": False},
    )
    assert licensed_split["licensed_next_family"] == FAMILY_PATH_EXIT_P_K3_UNREAL_RED
    licensed_none = license_from_ab_k3(
        {"tag": "S_NONE", "S_MISSING_U": False, "S_MISSING_PATH": False, "S_THIN": False},
        {"tag": "S_NONE", "S_MISSING_U": False, "S_MISSING_PATH": False, "S_THIN": False},
    )
    assert licensed_none["licensed_next_family"] == FAMILY_H_NONE


def test_coverage_write_reports_and_tables(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_path_unreal_k3_report import (
        leg_payload,
        write_path_unreal_k3_reports,
    )
    from lumina_core.birth.awakening_path_unreal_k3_tables import (
        table_t0,
        table_t1,
        table_t1b,
        table_t2,
        table_t3,
        table_t4,
        table_t5,
    )

    rows = _rows_split()
    payload = leg_payload(
        rows=rows,
        zip_sha=INIT_SHA256,
        ticks_sha16="7e86c2bb1c71d514",
        price_sha16_value="deadbeef",
        optimizer_steps=0,
        skip_replay=False,
        replay_ran=False,
        source="path_early_jsonl",
        source_a_sha256="aa",
        source_b_sha256="bb",
    )
    assert "t1b" in payload and "t5" in payload
    write_path_unreal_k3_reports(
        reports=tmp_path,
        overall=OVERALL_MEASURE,
        zip_sha=INIT_SHA256,
        payload_a=payload,
        payload_b=payload,
        t4={"grind_A": {"absent": True}, "path_early_A": {"absent": True}},
        proto={"gate0_complete": True, "missing_sites": []},
        parent_loaded=True,
        source="path_early_jsonl",
        source_a_sha256="aa",
        source_b_sha256="bb",
        missing_share_a=0.0,
        path_chosen="rescore",
        skip_replay=False,
        replay_ran=False,
        gate0_sha="5079d66af8dfd74933989bac459e97d3fbb0daca",
    )
    verdict = (tmp_path / "AWAKENING_PATH_UNREAL_K3_VERDICT.md").read_text(encoding="utf-8")
    audit = (tmp_path / "AWAKENING_PATH_UNREAL_K3_AUDIT.md").read_text(encoding="utf-8")
    flags_text = (tmp_path / "artifacts" / "path_unreal_k3_flags.json").read_text(encoding="utf-8")
    assert "Law shipped: NONE" in verdict
    assert "Flatten-at-3 shipped: no" in verdict
    assert "P_K3_UNREAL_RED" in verdict
    assert "# AWAKENING_PATH_UNREAL_K3_AUDIT" in audit
    assert "PATH_UNREAL_K3" in flags_text or "P_K3_UNREAL_RED" in flags_text
    t0 = table_t0(
        rows,
        zip_sha256="ab",
        ticks_sha16="cd",
        price_sha16_value="ef",
        optimizer_steps=0,
        skip_replay=False,
        replay_ran=False,
        source="path_early_jsonl",
    )
    assert t0["n_policy"] == 80
    assert t0["optimizer_steps"] == 0
    assert table_t1(rows)["n_H"] == 50
    t1b = table_t1b(rows)
    assert t1b["path_k3_unreal_r"]["contrast_only"] is False
    assert t1b["path_k3_mae_r"]["contrast_only"] is True
    assert t1b["path_k5_unreal_r"]["U_k"]["mean"] is None
    assert "P_K3_UNREAL_RED" in table_t2(rows)
    assert "drop_H" in table_t3(rows)["P_K3_UNREAL_RED"]
    assert table_t5(rows)[P_K3_UNREAL_RED]["READ_ONLY_FLIP"] is True
    t4 = table_t4(tmp_path)
    assert t4["grind_A"]["absent"] is True
    assert t4["path_early_A"]["absent"] is True
    assert isolated_workspace(tmp_path).as_posix().endswith("awakening_path_unreal_k3/workspace")
    assert "k=5 is not a candidate" in honesty_paragraph(source="path_early_jsonl")


def test_coverage_run_skip_replay_writes_inconclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_unreal_k3_run as run_mod
    from lumina_core.birth.awakening_path_unreal_k3_run import run_path_unreal_k3, write_jsonl_sha256

    assert write_jsonl_sha256(tmp_path / "empty.jsonl").is_file()
    parent = tmp_path / INIT_ZIP_NAME
    parent.write_bytes(b"PK\x03\x04parent")
    monkeypatch.setattr(
        run_mod, "inspect_path_unreal_k3_protocol", lambda: {"gate0_complete": True, "missing_sites": []}
    )
    monkeypatch.setattr(run_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(run_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)
    skipped = run_path_unreal_k3(
        reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path, skip_replay=True
    )
    assert skipped["overall"] == OVERALL_INCONCLUSIVE
    assert skipped["skip_replay"] is True
    flags = (tmp_path / "artifacts" / "path_unreal_k3_flags.json").read_text(encoding="utf-8")
    assert '"skip_replay": true' in flags
    assert (tmp_path / "AWAKENING_PATH_UNREAL_K3_VERDICT.md").is_file()
    assert "H_NONE" in (tmp_path / "AWAKENING_PATH_UNREAL_K3_VERDICT.md").read_text(encoding="utf-8")


def test_coverage_run_evaluate_only_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_unreal_k3_run as run_mod
    from lumina_core.birth.awakening_path_unreal_k3_run import run_path_unreal_k3

    parent = tmp_path / INIT_ZIP_NAME
    parent.write_bytes(b"PK\x03\x04parent")
    monkeypatch.setattr(
        run_mod, "inspect_path_unreal_k3_protocol", lambda: {"gate0_complete": True, "missing_sites": []}
    )
    monkeypatch.setattr(run_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(run_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)
    monkeypatch.setattr(
        run_mod, "load_frozen_policy", lambda *_a, **_k: SimpleNamespace(predict=lambda *a, **k: ([0.0], None))
    )
    monkeypatch.setattr(run_mod, "probe_path_early_source", lambda *_a, **_k: {"ok": False, "reason": "missing_jsonl", "source_A_sha256": "", "source_B_sha256": "", "missing_share": 1.0, "rows_a": [], "rows_b": []})

    def _fixture(workspace: Path, *, seed: int) -> dict[str, Any]:
        _ = workspace, seed
        return {
            "holdout": [{"close": 1.0, "regime": "NEUTRAL"}],
            "reused_manifest": False,
            "ticks_sha16": "7e86c2bb1c71d514",
            "bars_sha16": "x",
            "price_sha16": "aff3cb1e3a6f5014",
        }

    def _eval_leg(**kwargs: Any) -> SimpleNamespace:
        seed = int(kwargs["seed"])
        reports = Path(kwargs["reports"])
        name = "path_unreal_k3_A_close_ledger.jsonl" if seed == 20260902 else "path_unreal_k3_B_close_ledger.jsonl"
        path = reports / "artifacts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        holes = [_row(path_k3_unreal_r=-0.4, path_k3_mae_r=-1.0) for _ in range(80)]
        winners = [
            _row(close_reason="target", trade_r=1.21, pnl=60.0, path_k3_unreal_r=0.1, path_k3_mae_r=-0.2)
            for _ in range(39)
        ]
        extra = [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0, path_k3_unreal_r=-0.5) for _ in range(31)]
        import json as _json

        path.write_text("".join(_json.dumps(r) + "\n" for r in holes + winners + extra), encoding="utf-8")
        return SimpleNamespace(optimizer_steps=0, trajectories=[], rollout_steps=0)

    monkeypatch.setattr(run_mod, "_load_or_build_fixture", _fixture)
    monkeypatch.setattr(run_mod, "run_path_unreal_k3_eval_leg", _eval_leg)
    live = run_path_unreal_k3(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)
    assert live["parent_loaded"] is True
    assert live["replay_ran"] is True
    assert live["A"]["t0"]["n_policy"] == 150
    assert live["A"]["t0"]["optimizer_steps"] == 0
    src = Path("lumina_core/birth/awakening_path_unreal_k3_run.py").read_text(encoding="utf-8")
    assert "ledger_source=SOURCE" in src or SOURCE in src
    monkeypatch.setattr(run_mod, "run_path_unreal_k3_eval_leg", lambda **_k: SimpleNamespace(optimizer_steps=1))
    with pytest.raises(PathUnrealK3ProtocolError, match="optimizer_steps"):
        run_path_unreal_k3(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)


def test_coverage_gate0_incomplete_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_unreal_k3_run as run_mod
    from lumina_core.birth.awakening_path_unreal_k3_run import run_path_unreal_k3

    monkeypatch.setattr(
        run_mod,
        "inspect_path_unreal_k3_protocol",
        lambda: {"gate0_complete": False, "missing_sites": ["k_locked"]},
    )
    with pytest.raises(PathUnrealK3ProtocolError, match="Gate 0"):
        run_path_unreal_k3(reports=tmp_path, skip_replay=True)


def test_coverage_overall_measure_and_inconclusive_branches() -> None:
    assert (
        overall_path_unreal_k3_string(
            parent_loaded=True,
            skip_replay=False,
            n_u_a=126,
            s_missing_path=False,
            optimizer_steps=0,
            source_jsonl_present=True,
            replay_ran=False,
        )
        == OVERALL_MEASURE
    )
    assert (
        overall_path_unreal_k3_string(
            parent_loaded=False,
            skip_replay=False,
            n_u_a=126,
            source_jsonl_present=False,
            replay_ran=False,
        )
        == OVERALL_INCONCLUSIVE
    )
    assert (
        overall_path_unreal_k3_string(
            parent_loaded=True,
            skip_replay=False,
            n_u_a=126,
            s_missing_path=True,
            source_jsonl_present=True,
        )
        == OVERALL_INCONCLUSIVE
    )
    assert (
        overall_path_unreal_k3_string(
            parent_loaded=True,
            skip_replay=False,
            n_u_a=126,
            optimizer_steps=1,
            source_jsonl_present=True,
        )
        == OVERALL_INCONCLUSIVE
    )


def test_coverage_main_skip_replay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_unreal_k3_run as run_mod
    from lumina_core.birth.awakening_path_unreal_k3_run import main

    monkeypatch.setattr(run_mod, "reports_dir", lambda: tmp_path)
    monkeypatch.setattr(
        run_mod,
        "run_path_unreal_k3",
        lambda **_k: {
            "overall": OVERALL_INCONCLUSIVE,
            "parent_loaded": False,
            "source": "path_early_jsonl",
            "replay_ran": False,
        },
    )
    assert main(["--skip-replay"]) == 0
