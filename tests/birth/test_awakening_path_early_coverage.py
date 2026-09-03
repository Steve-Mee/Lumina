"""Coverage for PATH_EARLY run/report/tables/telem. Measure-only. No learn()."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from lumina_core.birth.awakening_path_early import (
    INIT_SHA256,
    INIT_ZIP_NAME,
    OVERALL_INCONCLUSIVE,
    SOURCE,
    PathEarlyProtocolError,
)


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


def test_coverage_run_skip_replay_writes_inconclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_early_run as run_mod
    from lumina_core.birth.awakening_path_early_run import run_path_early, write_jsonl_sha256

    assert write_jsonl_sha256(tmp_path / "empty.jsonl").is_file()
    parent = tmp_path / INIT_ZIP_NAME
    parent.write_bytes(b"PK\x03\x04parent")
    monkeypatch.setattr(run_mod, "inspect_path_early_protocol", lambda: {"gate0_complete": True, "missing_sites": []})
    monkeypatch.setattr(run_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(run_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)
    skipped = run_path_early(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path, skip_replay=True)
    assert skipped["overall"] == OVERALL_INCONCLUSIVE
    assert skipped["skip_replay"] is True
    flags = (tmp_path / "artifacts" / "awakening_path_early_flags.json").read_text(encoding="utf-8")
    assert '"skip_replay": true' in flags
    assert (tmp_path / "AWAKENING_PATH_EARLY_VERDICT.md").is_file()
    assert "H_NONE" in (tmp_path / "AWAKENING_PATH_EARLY_VERDICT.md").read_text(encoding="utf-8")


def test_coverage_run_evaluate_only_mocked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_early_run as run_mod
    from lumina_core.birth.awakening_path_early_run import run_path_early

    parent = tmp_path / INIT_ZIP_NAME
    parent.write_bytes(b"PK\x03\x04parent")
    monkeypatch.setattr(run_mod, "inspect_path_early_protocol", lambda: {"gate0_complete": True, "missing_sites": []})
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
        name = "path_early_A_close_ledger.jsonl" if seed == 20260902 else "path_early_B_close_ledger.jsonl"
        path = reports / "artifacts" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        holes = [_row(path_k3_mae_r=-1.0, path_k3_unreal_r=-0.4) for _ in range(80)]
        winners = [
            _row(close_reason="target", trade_r=1.21, pnl=60.0, path_k3_mae_r=-0.2, path_k3_unreal_r=0.1)
            for _ in range(39)
        ]
        extra = [_row(close_reason="time_stop", trade_r=-0.1, pnl=-5.0, path_k3_mae_r=-0.5) for _ in range(31)]
        import json as _json

        path.write_text("".join(_json.dumps(r) + "\n" for r in holes + winners + extra), encoding="utf-8")
        return SimpleNamespace(optimizer_steps=0, trajectories=[], rollout_steps=0)

    monkeypatch.setattr(run_mod, "_load_or_build_fixture", _fixture)
    monkeypatch.setattr(run_mod, "run_path_early_eval_leg", _eval_leg)
    live = run_path_early(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)
    assert live["parent_loaded"] is True
    assert live["A"]["t0"]["n_policy"] == 150
    assert live["A"]["t0"]["optimizer_steps"] == 0
    src = Path("lumina_core/birth/awakening_path_early_run.py").read_text(encoding="utf-8")
    assert "ledger_source=SOURCE" in src or SOURCE in src
    monkeypatch.setattr(run_mod, "run_path_early_eval_leg", lambda **_k: SimpleNamespace(optimizer_steps=1))
    with pytest.raises(PathEarlyProtocolError, match="optimizer_steps"):
        run_path_early(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path)


def test_coverage_write_reports_and_tables(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_path_early_report import (
        leg_payload,
        write_path_early_reports,
    )
    from lumina_core.birth.awakening_path_early_tables import (
        table_t0,
        table_t1,
        table_t1b,
        table_t2,
        table_t3,
        table_t4,
        table_t5,
    )

    rows = [_row(path_k3_mae_r=-1.0, path_k3_mfe_r=0.2, path_k3_unreal_r=-0.4) for _ in range(50)]
    rows += [
        _row(
            close_reason="target",
            trade_r=1.21,
            pnl=60.0,
            path_k3_mae_r=0.0,
            path_k3_mfe_r=0.8,
            path_k3_unreal_r=0.3,
        )
        for _ in range(30)
    ]
    payload = leg_payload(
        rows=rows,
        zip_sha=INIT_SHA256,
        ticks_sha16="7e86c2bb1c71d514",
        price_sha16_value="deadbeef",
        optimizer_steps=0,
        skip_replay=True,
    )
    assert "t1b" in payload and "t5" in payload
    write_path_early_reports(
        reports=tmp_path,
        overall=OVERALL_INCONCLUSIVE,
        zip_sha=INIT_SHA256,
        payload_a=payload,
        payload_b=payload,
        t4={"grind_A": {"absent": True}, "policy_signal_A": {"absent": True}},
        proto={"gate0_complete": True, "missing_sites": []},
        parent_loaded=True,
        gate0_sha="9a98853f08909c39205da647aa749a485c66c0a1",
        skip_replay=True,
    )
    verdict = (tmp_path / "AWAKENING_PATH_EARLY_VERDICT.md").read_text(encoding="utf-8")
    assert "Law shipped: NONE" in verdict
    assert "H_NONE" in verdict
    t0 = table_t0(rows, zip_sha256="ab", ticks_sha16="cd", price_sha16_value="ef", optimizer_steps=0, skip_replay=True)
    assert t0["n_policy"] == 80
    assert t0["skip_replay"] is True
    assert table_t1(rows)["n_H"] == 50
    assert "path_k3_mae_r" in table_t1b(rows)
    assert "P_K3_MAE_DEEP" in table_t2(rows)
    assert "drop_H" in table_t3(rows)["P_K3_MAE_DEEP"]
    assert table_t5(rows)["P_K3_MAE_DEEP"]["READ_ONLY_FLIP"] is True
    t4 = table_t4(tmp_path)
    assert t4["grind_A"]["absent"] is True
    assert t4["policy_signal_A"]["absent"] is True


def test_coverage_telem_snapshots() -> None:
    from lumina_core.birth.sim_runner_entry_telem import snapshot_path_at_k, start_open_telem

    stash = start_open_telem(entry_regime="NEUTRAL", entry_bar_index=1, entry_price=20000.0, side=1)
    stash["mae_usd"] = -25.0
    stash["mfe_usd"] = 10.0
    snapshot_path_at_k(stash, {"close": 19998.0}, 3)
    assert stash["path_k3_mae_usd"] == pytest.approx(-25.0)
    assert stash["path_k3_unreal_usd"] == pytest.approx(-10.0)
    snapshot_path_at_k(stash, {"last": 20001.0}, 5)
    assert stash["path_k5_unreal_usd"] == pytest.approx(5.0)
    snapshot_path_at_k(stash, {"high": 1.0, "low": 0.0}, 4)
    assert "path_k4_mae_usd" not in stash


def test_coverage_inspect_complete() -> None:
    from lumina_core.birth.awakening_path_early_path import inspect_path_early_protocol

    dump = inspect_path_early_protocol()
    assert dump["gate0_complete"] is True


def test_coverage_gate0_incomplete_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_path_early_run as run_mod
    from lumina_core.birth.awakening_path_early_run import run_path_early

    monkeypatch.setattr(
        run_mod,
        "inspect_path_early_protocol",
        lambda: {"gate0_complete": False, "missing_sites": ["snapshot_site"]},
    )
    with pytest.raises(PathEarlyProtocolError, match="Gate 0"):
        run_path_early(reports=tmp_path, skip_replay=True)
