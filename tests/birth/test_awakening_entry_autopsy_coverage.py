"""Coverage for ENTRY autopsy run/report/tables/telem. Measure-only. No learn()."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.birth.awakening_entry_autopsy import (
    ENTRY_A_NAME,
    INIT_SHA256,
    EntryAutopsyProtocolError,
)


def _hole(
    *,
    entry: str | None,
    bars_held: int | None = 10,
    mae_r: float | None = -1.0,
    close_reason: str = "stop",
    regime: str = "NEUTRAL",
    plant: bool = False,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "pnl": -117.0,
        "trade_r": -1.04,
        "close_reason": close_reason,
        "regime": regime,
        "plant": plant,
        "force_open": plant,
    }
    if entry is not None:
        row["entry_regime"] = entry
    if bars_held is not None:
        row["bars_held"] = bars_held
    if mae_r is not None:
        row["mae_r"] = mae_r
    return row


def test_tables_t0_t4(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_entry_autopsy_tables import (
        cell_entry_stats,
        entry_label,
        optional_float,
        percentile,
        table_t0,
        table_t1,
        table_t2,
        table_t3,
        table_t4,
    )

    assert percentile([], 0.5) is None
    assert percentile([4.0], 0.25) == pytest.approx(4.0)
    assert optional_float({"mae_r": "x"}, "mae_r") is None
    assert entry_label({"entry_regime": ""}) == "UNKNOWN"
    policy = [_hole(entry="NEUTRAL", bars_held=2) for _ in range(8)]
    policy += [_hole(entry="TREND_UP", close_reason="target", regime="TREND_UP", bars_held=9) for _ in range(8)]
    t0 = table_t0(policy, zip_sha256="ab", ticks_sha16="cd", price_sha16_value="ef", optimizer_steps=0)
    assert t0["n_policy"] == 16
    assert table_t1(policy)["hole"]["n"] == 8
    assert cell_entry_stats(policy[:8])["n_entry_neutral"] == 8
    assert "NEUTRAL|stop" in table_t2(policy, min_n=8)["trigger"]
    assert table_t3(policy)["n_first_touch"] == 8
    assert table_t3([])["n_hole"] == 0
    present = tmp_path / "grind_A_close_ledger.jsonl"
    present.write_text(
        '{"pnl":-117.0,"trade_r":-1.04,"close_reason":"stop","regime":"NEUTRAL","plant":false}\n',
        encoding="utf-8",
    )
    t4 = table_t4(tmp_path)
    assert t4["grind_A"]["absent"] is False
    assert t4["grind_B"]["absent"] is True


def test_paths_wire_honesty(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_entry_autopsy import (
        FAMILY_H_NONE,
        FAMILY_OPEN_DECISION,
        FAMILY_REGIME_FLIP_EXIT,
        INIT_ZIP_NAME,
        OVERALL_INCONCLUSIVE,
        OVERALL_MEASURE,
        assert_eval_seed,
        assert_parent_sha,
        assert_wire_vs_grind_a,
        entry_ledger_path,
        honesty_paragraph,
        overall_entry_string,
    )

    assert assert_eval_seed(20260902) == 20260902
    with pytest.raises(EntryAutopsyProtocolError, match="A/B only"):
        assert_eval_seed(7)
    ws = tmp_path / "birth_cloud_run" / "workspace"
    ws.mkdir(parents=True)
    assert entry_ledger_path(ws, leg="A").name == ENTRY_A_NAME
    missing = tmp_path / INIT_ZIP_NAME
    with pytest.raises(EntryAutopsyProtocolError, match="parent zip missing"):
        assert_parent_sha(missing)
    assert_wire_vs_grind_a(wr_policy=0.34, n_policy=150)
    with pytest.raises(EntryAutopsyProtocolError, match="wire change"):
        assert_wire_vs_grind_a(wr_policy=0.50, n_policy=10)
    assert "NEUTRAL" in honesty_paragraph(FAMILY_OPEN_DECISION)
    assert "flip-exit" in honesty_paragraph(FAMILY_REGIME_FLIP_EXIT)
    assert "No train law" in honesty_paragraph(FAMILY_H_NONE)
    assert overall_entry_string(parent_loaded=True) == OVERALL_MEASURE
    assert overall_entry_string(parent_loaded=False) == OVERALL_INCONCLUSIVE


def test_report_writers(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_entry_autopsy_report import leg_payload, write_entry_autopsy_reports

    rows = [_hole(entry="NEUTRAL") for _ in range(40)]
    payload = leg_payload(
        rows=rows,
        zip_sha=INIT_SHA256,
        ticks_sha16="7e86c2bb1c71d514",
        price_sha16_value="deadbeef",
        optimizer_steps=0,
    )
    assert payload["flags"]["H_ENTRY_NEUTRAL"] is True
    write_entry_autopsy_reports(
        reports=tmp_path,
        overall="GRIND_REGRESS_AWAKENING_OPEN ENTRY_HOLE_AUTOPSY ENTRY_MEASURE_ONLY",
        family="OPEN_DECISION",
        zip_sha=INIT_SHA256,
        payload_a=payload,
        payload_b=payload,
        t4={"grind_A": {"absent": True}},
        proto={"gate0_complete": True, "missing_sites": []},
        parent_loaded=True,
    )
    assert (tmp_path / "artifacts" / "awakening_entry_autopsy_flags.json").is_file()
    text = (tmp_path / "AWAKENING_ENTRY_AUTOPSY_VERDICT.md").read_text(encoding="utf-8")
    assert "OPEN_DECISION" in text


def test_open_telem() -> None:
    from lumina_core.birth.sim_runner_entry_telem import (
        apply_open_excursion,
        close_open_telem,
        start_open_telem,
        tick_hl,
        update_open_telem,
    )

    assert tick_hl({"close": 1.0}) is None
    stash = start_open_telem(entry_regime="NEUTRAL", entry_bar_index=2, entry_price=20000.0, side=1)
    apply_open_excursion(stash, {"high": 20002.0, "low": 19998.0})
    apply_open_excursion(stash, {"high": 20010.0, "low": 19990.0})
    assert stash["mae_usd"] <= -50.0
    closed = close_open_telem(stash, 6, "NEUTRAL", {"intended_risk_usd": 50.0})
    assert closed["bars_held"] == 4
    assert "mae_r" in closed
    assert close_open_telem(None, 1, "NEUTRAL", {})["source"] == "awakening_entry_autopsy"

    class _Env:
        _entry_side = 1
        _entry_price = 20000.0
        _idx = 2

    ticks = [{"regime": "NEUTRAL", "high": 20001.0, "low": 19999.0}]
    opened = update_open_telem(None, _Env(), {}, 0, 1, ticks[0], ticks)
    assert opened is not None
    assert update_open_telem(None, _Env(), {}, 1, 1, ticks[0], ticks) is None


def test_run_skip_and_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_entry_autopsy_run as run_mod
    from lumina_core.birth.awakening_entry_autopsy import INIT_ZIP_NAME
    from lumina_core.birth.awakening_entry_autopsy_run import run_entry_autopsy, write_jsonl_sha256

    assert write_jsonl_sha256(tmp_path / "empty.jsonl").is_file()
    parent = tmp_path / INIT_ZIP_NAME
    parent.write_bytes(b"PK\x03\x04parent")
    monkeypatch.setattr(run_mod, "inspect_entry_autopsy_protocol", lambda: {"gate0_complete": True, "missing_sites": []})
    monkeypatch.setattr(run_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(
        run_mod,
        "assert_parent_sha",
        lambda *_a, **_k: (_ for _ in ()).throw(EntryAutopsyProtocolError("parent zip missing")),
    )
    out = run_entry_autopsy(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)
    assert out["parent_loaded"] is False
    monkeypatch.setattr(run_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)
    skipped = run_entry_autopsy(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path, skip_replay=True)
    assert skipped["parent_loaded"] is True

    def _fixture(workspace: Path, *, seed: int) -> dict[str, Any]:
        _ = workspace, seed
        return {
            "holdout": [{"close": 1.0}],
            "reused_manifest": False,
            "ticks_sha16": "7e86c2bb1c71d514",
            "bars_sha16": "x",
            "price_sha16": "y",
        }

    def _eval_leg(**kwargs: Any) -> SimpleNamespace:
        seed = int(kwargs["seed"])
        reports = Path(kwargs["reports"])
        name = "entry_autopsy_A_close_ledger.jsonl" if seed == 20260902 else "entry_autopsy_B_close_ledger.jsonl"
        path = reports / "artifacts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        winners = [
            {
                "pnl": 60.0,
                "trade_r": 1.21,
                "close_reason": "target",
                "regime": "NEUTRAL",
                "plant": False,
                "force_open": False,
                "entry_regime": "NEUTRAL",
                "bars_held": 8,
                "mae_r": -0.2,
            }
            for _ in range(51)
        ]
        losers = [
            {
                "pnl": -52.0,
                "trade_r": -1.04,
                "close_reason": "stop",
                "regime": "NEUTRAL",
                "plant": False,
                "force_open": False,
                "entry_regime": "NEUTRAL",
                "bars_held": 6,
                "mae_r": -1.0,
            }
            for _ in range(99)
        ]
        import json as _json

        path.write_text("".join(_json.dumps(r) + "\n" for r in winners + losers), encoding="utf-8")
        return SimpleNamespace(optimizer_steps=0, trajectories=[], rollout_steps=0)

    monkeypatch.setattr(run_mod, "_load_or_build_fixture", _fixture)
    monkeypatch.setattr(run_mod, "run_entry_eval_leg", _eval_leg)
    live = run_entry_autopsy(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)
    assert live["family"] == "OPEN_DECISION"
    monkeypatch.setattr(run_mod, "run_entry_eval_leg", lambda **_k: SimpleNamespace(optimizer_steps=1))
    with pytest.raises(EntryAutopsyProtocolError, match="optimizer_steps"):
        run_entry_autopsy(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)
    monkeypatch.setattr(run_mod, "TRAIN", True)
    with pytest.raises(RuntimeError, match="TRAIN"):
        run_entry_autopsy(reports=tmp_path)


def test_run_main_gate0(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_entry_autopsy_run as run_mod
    from lumina_core.birth.awakening_entry_autopsy_run import main, run_entry_autopsy

    monkeypatch.setattr(
        run_mod, "inspect_entry_autopsy_protocol", lambda: {"gate0_complete": False, "missing_sites": ["x"]}
    )
    with pytest.raises(EntryAutopsyProtocolError, match="Gate 0"):
        run_entry_autopsy(reports=tmp_path)
    monkeypatch.setattr(run_mod, "run_entry_autopsy", lambda: {"overall": "X", "family": "OPEN_DECISION"})
    assert main() == 0
