"""Coverage for OPEN_SPLIT run/report/tables/telem. Measure-only. No learn()."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.birth.awakening_open_split import (
    INIT_SHA256,
    INIT_ZIP_NAME,
    OPEN_A_NAME,
    OpenSplitProtocolError,
)


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


def test_coverage_run_open_split_skip_replay_writes_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_open_split_run as run_mod
    from lumina_core.birth.awakening_open_split_run import run_open_split, write_jsonl_sha256

    assert write_jsonl_sha256(tmp_path / "empty.jsonl").is_file()
    parent = tmp_path / INIT_ZIP_NAME
    parent.write_bytes(b"PK\x03\x04parent")
    monkeypatch.setattr(run_mod, "inspect_open_split_protocol", lambda: {"gate0_complete": True, "missing_sites": []})
    monkeypatch.setattr(run_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(run_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)
    skipped = run_open_split(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path, skip_replay=True)
    assert skipped["parent_loaded"] is True
    assert (tmp_path / "AWAKENING_OPEN_SPLIT_VERDICT.md").is_file()
    assert (tmp_path / "artifacts" / "awakening_open_split_flags.json").is_file()


def test_coverage_run_evaluate_only_call_site_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_open_split_run as run_mod
    from lumina_core.birth.awakening_open_split_run import run_open_split

    parent = tmp_path / INIT_ZIP_NAME
    parent.write_bytes(b"PK\x03\x04parent")
    monkeypatch.setattr(run_mod, "inspect_open_split_protocol", lambda: {"gate0_complete": True, "missing_sites": []})
    monkeypatch.setattr(run_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(run_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)
    monkeypatch.setattr(
        run_mod, "load_frozen_policy", lambda *_a, **_k: SimpleNamespace(predict=lambda *a, **k: ([0.0], None))
    )

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
        name = "open_split_A_close_ledger.jsonl" if seed == 20260902 else "open_split_B_close_ledger.jsonl"
        path = reports / "artifacts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        holes = [
            _row(
                close_reason="stop",
                open_occ_flat=0.40,
                open_session_phase=1.0,
                open_range_stop_frac=0.8,
                bars_since_prev_policy_stop=20,
                open_imbalance=1.5,
            )
            for _ in range(76)
        ]
        winners = [
            _row(
                close_reason="target",
                trade_r=1.21,
                pnl=60.0,
                open_occ_flat=0.40,
                open_session_phase=1.0,
                open_range_stop_frac=0.8,
                bars_since_prev_policy_stop=20,
                open_imbalance=1.5,
            )
            for _ in range(45)
        ]
        extra = [
            _row(
                close_reason="time_stop",
                trade_r=-0.1,
                pnl=-5.0,
                open_occ_flat=0.40,
                open_session_phase=1.0,
            )
            for _ in range(29)
        ]
        import json as _json

        path.write_text("".join(_json.dumps(r) + "\n" for r in holes + winners + extra), encoding="utf-8")
        return SimpleNamespace(optimizer_steps=0, trajectories=[], rollout_steps=0)

    monkeypatch.setattr(run_mod, "_load_or_build_fixture", _fixture)
    monkeypatch.setattr(run_mod, "run_open_split_eval_leg", _eval_leg)
    live = run_open_split(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)
    assert live["parent_loaded"] is True
    assert live["A"]["t0"]["n_policy"] == 150
    monkeypatch.setattr(run_mod, "run_open_split_eval_leg", lambda **_k: SimpleNamespace(optimizer_steps=1))
    with pytest.raises(OpenSplitProtocolError, match="optimizer_steps"):
        run_open_split(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)


def test_coverage_write_reports_tmp_audit_verdict_flags(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_open_split_report import leg_payload, write_open_split_reports

    rows = [_row(open_occ_flat=0.40) for _ in range(50)]
    rows += [_row(close_reason="target", trade_r=1.21, pnl=60.0, open_occ_flat=0.40) for _ in range(30)]
    rows += [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0, open_occ_flat=0.40) for _ in range(20)]
    payload = leg_payload(
        rows=rows,
        zip_sha=INIT_SHA256,
        ticks_sha16="7e86c2bb1c71d514",
        price_sha16_value="deadbeef",
        optimizer_steps=0,
    )
    write_open_split_reports(
        reports=tmp_path,
        overall="GRIND_REGRESS_AWAKENING_OPEN OPEN_SPLIT_AUTOPSY OPEN_MEASURE_ONLY",
        zip_sha=INIT_SHA256,
        payload_a=payload,
        payload_b=payload,
        t4={"grind_A": {"absent": True}},
        proto={"gate0_complete": True, "missing_sites": [], "gather_open_features": "x:1"},
        parent_loaded=True,
        gate0_sha="25061876cd5d249d18fd8e12e5890d965f10f8c7",
    )
    verdict = (tmp_path / "AWAKENING_OPEN_SPLIT_VERDICT.md").read_text(encoding="utf-8")
    assert "Gate 1 law:** `NONE`" in verdict or "Gate 1 law:** `NONE`" in verdict.replace(" ", "") or "NONE" in verdict
    audit = (tmp_path / "AWAKENING_OPEN_SPLIT_AUDIT.md").read_text(encoding="utf-8")
    assert "## Mission" in audit
    assert "## Capital / autonomy / experiment" in audit


def test_coverage_tables_t0_t4(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_open_split_tables import table_t0, table_t1, table_t2, table_t3, table_t4

    policy = [_row() for _ in range(8)]
    policy += [_row(close_reason="target", trade_r=1.21, pnl=60.0) for _ in range(8)]
    t0 = table_t0(policy, zip_sha256="ab", ticks_sha16="cd", price_sha16_value="ef", optimizer_steps=0)
    assert t0["n_policy"] == 16
    t1 = table_t1(policy)
    assert t1["n_H"] == 8
    assert t1["n_W"] == 8
    grid = table_t2(policy)
    assert "F_OCC_FLOOR" in grid
    assert "missing" in grid["F_OCC_FLOOR"]
    paper = table_t3(policy)
    assert "drop_H" in paper["F_OCC_FLOOR"]
    present = tmp_path / "grind_A_close_ledger.jsonl"
    present.write_text(
        '{"pnl":-117.0,"trade_r":-1.04,"close_reason":"stop","regime":"NEUTRAL","plant":false}\n',
        encoding="utf-8",
    )
    autopsy = tmp_path / "entry_autopsy_A_close_ledger.jsonl"
    autopsy.write_text(
        '{"pnl":-117.0,"trade_r":-1.04,"close_reason":"stop","regime":"NEUTRAL","plant":false,"entry_regime":"NEUTRAL"}\n',
        encoding="utf-8",
    )
    t4 = table_t4(tmp_path)
    assert t4["grind_A"]["absent"] is False
    assert t4["entry_autopsy_A"]["absent"] is False
    assert t4["grind_B"]["absent"] is True


def test_coverage_telem_with_and_without_optional_keys() -> None:
    from lumina_core.birth.sim_runner_entry_telem import (
        OPEN_SPLIT_SOURCE,
        close_open_telem,
        start_open_telem,
        update_open_telem,
    )

    four = start_open_telem(entry_regime="NEUTRAL", entry_bar_index=2, entry_price=20000.0, side=-1)
    assert "open_occ_flat" not in four
    full = start_open_telem(
        entry_regime="NEUTRAL",
        entry_bar_index=8,
        entry_price=20000.0,
        side=1,
        open_occ_flat=0.27,
        open_cum_flat=0.28,
        open_in_band_seen=True,
        open_session_phase=0.0,
        open_confluence=0.5,
        open_news_proximity=0.1,
        open_imbalance=0.99,
        open_range_stop_frac=0.4,
        open_participation_mode="PASSTHROUGH",
    )
    closed = close_open_telem(
        full, 12, "NEUTRAL", {"intended_risk_usd": 50.0}, last_policy_stop_bar=2, source=OPEN_SPLIT_SOURCE
    )
    assert closed["source"] == OPEN_SPLIT_SOURCE
    assert closed["open_side"] == 1
    assert closed["bars_since_prev_policy_stop"] == 6
    assert closed["open_occ_flat"] == pytest.approx(0.27)
    none_closed = close_open_telem(None, 1, "NEUTRAL", {}, source=OPEN_SPLIT_SOURCE)
    assert none_closed["source"] == OPEN_SPLIT_SOURCE

    class _Env:
        _entry_side = 1
        _entry_price = 20000.0
        _idx = 2
        occupancy_control_flat = 0.27
        occupancy_in_band_seen = True
        range_flat_bars = 50
        range_total_signals = 200

    ticks = [
        {
            "regime": "NEUTRAL",
            "high": 20010.0,
            "low": 19990.0,
            "bible_session_phase": 0.0,
            "bible_confluence": 0.5,
            "bible_news_proximity": 0.2,
        }
    ]
    opened = update_open_telem(None, _Env(), {}, 0, 1, ticks[0], ticks)
    assert opened is not None
    assert opened.get("open_occ_flat") == pytest.approx(0.27)
    assert "open_imbalance" not in opened


def test_coverage_gather_open_features_missing_attrs() -> None:
    from lumina_core.birth.sim_runner_entry_telem import gather_open_features, stamp_open_host

    empty = gather_open_features(SimpleNamespace(), {}, {}, 0.0)
    assert "open_occ_flat" not in empty
    assert "open_imbalance" not in empty
    assert "open_range_stop_frac" not in empty
    host = SimpleNamespace()
    geo = SimpleNamespace(stop_pct=0.0075)
    stamp_open_host(host, 0.27, True, 50, 200, 10, 40, geo)
    tick = {"high": 20100.0, "low": 19900.0, "imbalance": 1.0, "bible_session_phase": 0.0}
    got = gather_open_features(host, tick, {"occupancy_in_band_seen": True}, 20000.0)
    assert got["open_occ_flat"] == pytest.approx(0.27)
    assert got["open_imbalance"] == pytest.approx(1.0)
    assert "open_range_stop_frac" in got
    no_imb = gather_open_features(host, {"high": 20100.0, "low": 19900.0}, {}, 20000.0)
    assert "open_imbalance" not in no_imb


def test_coverage_forbidden_write_and_wrong_zip(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_open_split import (
        assert_eval_seed,
        assert_isolated_write,
        assert_parent_sha,
        assert_wire_vs_autopsy_a,
        honesty_paragraph,
        open_split_ledger_path,
        overall_open_split_string,
    )

    assert assert_eval_seed(20260902) == 20260902
    with pytest.raises(OpenSplitProtocolError, match="A/B only"):
        assert_eval_seed(7)
    ws = tmp_path / "birth_cloud_run" / "workspace"
    ws.mkdir(parents=True)
    assert open_split_ledger_path(ws, leg="A").name == OPEN_A_NAME
    missing = tmp_path / INIT_ZIP_NAME
    with pytest.raises(OpenSplitProtocolError, match="parent zip missing"):
        assert_parent_sha(missing)
    assert_wire_vs_autopsy_a(wr_policy=0.373, n_policy=150)
    with pytest.raises(OpenSplitProtocolError, match="wire change"):
        assert_wire_vs_autopsy_a(wr_policy=0.50, n_policy=10)
    assert "not separable" in honesty_paragraph("S_NONE", "none")
    assert "splits on" in honesty_paragraph("S_SPLIT", "F_OCC_FLOOR", 0.4)
    assert overall_open_split_string(parent_loaded=True).startswith("GRIND_REGRESS")
    with pytest.raises(OpenSplitProtocolError, match="forbidden write"):
        assert_isolated_write(tmp_path / "s5_close_ledger.jsonl")


def test_coverage_ledger_append_tmp(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_open_split_report import write_open_split_reports

    payload = {
        "t0": {
            "n_all": 0,
            "n_policy": 0,
            "n_plant": 0,
            "wr_policy": 0.0,
            "mean_r_policy": 0.0,
            "zip_sha256": INIT_SHA256,
            "ticks_sha16": "",
            "price_sha16": "",
            "optimizer_steps": 0,
        },
        "t1": {"U": {}, "H": {}, "W": {}, "n_U": 0, "n_H": 0, "n_W": 0, "share_H": 0.0, "share_W": 0.0},
        "t2": {},
        "t3": {},
        "flags": {
            "n_U": 0,
            "n_H": 0,
            "n_W": 0,
            "S_MISSING_U": True,
            "S_THIN": True,
            "winning_F": "none",
            "tag": "S_MISSING",
            "candidates": {},
            "gate1": "NONE",
        },
        "rows_n": 0,
        "stash_produced": {},
    }
    (tmp_path / "artifacts").mkdir(parents=True)
    (tmp_path / "LUMINA_BIRTH_EXPERIMENT_LOG.md").write_text("# log\n", encoding="utf-8")
    (tmp_path / "artifacts" / "LUMINA_BIRTH_EXPERIMENT_LOG.md").write_text("# log\n", encoding="utf-8")
    write_open_split_reports(
        reports=tmp_path,
        overall="GRIND_INCONCLUSIVE_AWAKENING_OPEN OPEN_SPLIT_AUTOPSY S_MISSING",
        zip_sha=INIT_SHA256,
        payload_a=payload,
        payload_b=payload,
        t4={},
        proto={"gate0_complete": True, "missing_sites": []},
        parent_loaded=False,
        gate0_sha="25061876cd5d249d18fd8e12e5890d965f10f8c7",
    )
    text = (tmp_path / "LUMINA_BIRTH_EXPERIMENT_LOG.md").read_text(encoding="utf-8")
    assert "OPEN_SPLIT autopsy" in text
    flags = (tmp_path / "artifacts" / "awakening_open_split_flags.json").read_text(encoding="utf-8")
    assert "OPEN_DECISION" in flags or "S_MISSING" in flags


def test_coverage_run_main_gate0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_open_split_run as run_mod
    from lumina_core.birth.awakening_open_split_run import main, run_open_split

    monkeypatch.setattr(
        run_mod, "inspect_open_split_protocol", lambda: {"gate0_complete": False, "missing_sites": ["x"]}
    )
    with pytest.raises(OpenSplitProtocolError, match="Gate 0"):
        run_open_split(reports=tmp_path)
    monkeypatch.setattr(run_mod, "run_open_split", lambda: {"overall": "X", "parent_loaded": True})
    assert main() == 0
    monkeypatch.setattr(run_mod, "TRAIN", True)
    with pytest.raises(RuntimeError, match="TRAIN"):
        run_open_split(reports=tmp_path)
