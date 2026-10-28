"""Coverage for OPEN_POLICY_SIGNAL run/report/tables/extract/telem. Measure-only."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from lumina_core.birth.awakening_open_policy_signal import (
    INIT_SHA256,
    INIT_ZIP_NAME,
    OVERALL_INCONCLUSIVE,
    OpenPolicySignalProtocolError,
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


def test_coverage_run_skip_replay_writes_inconclusive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_open_policy_signal_run as run_mod
    from lumina_core.birth.awakening_open_policy_signal_run import run_open_policy_signal, write_jsonl_sha256

    assert write_jsonl_sha256(tmp_path / "empty.jsonl").is_file()
    parent = tmp_path / INIT_ZIP_NAME
    parent.write_bytes(b"PK\x03\x04parent")
    monkeypatch.setattr(run_mod, "inspect_open_policy_signal_protocol", lambda: {"gate0_complete": True, "missing_sites": []})
    monkeypatch.setattr(run_mod, "resolve_parent_path", lambda *_a, **_k: parent)
    monkeypatch.setattr(run_mod, "assert_parent_sha", lambda *_a, **_k: INIT_SHA256)
    skipped = run_open_policy_signal(reports=tmp_path, workspace_a=tmp_path, workspace_b=tmp_path, skip_replay=True)
    assert skipped["overall"] == OVERALL_INCONCLUSIVE
    assert skipped["skip_replay"] is True
    flags = (tmp_path / "artifacts" / "awakening_open_policy_signal_flags.json").read_text(encoding="utf-8")
    assert '"skip_replay": true' in flags
    assert (tmp_path / "AWAKENING_OPEN_POLICY_SIGNAL_VERDICT.md").is_file()


def test_coverage_write_reports_and_tables(tmp_path: Path) -> None:
    from lumina_core.birth.awakening_open_policy_signal_report import (
        leg_payload,
        write_open_policy_signal_reports,
    )
    from lumina_core.birth.awakening_open_policy_signal_tables import (
        table_t0,
        table_t1,
        table_t1b,
        table_t2,
        table_t3,
        table_t4,
        table_t5,
    )

    rows = [
        _row(open_policy_value=-1.0, open_policy_entropy=1.0, open_policy_action_margin=0.2)
        for _ in range(50)
    ]
    rows += [
        _row(
            close_reason="target",
            trade_r=1.21,
            pnl=60.0,
            open_policy_value=1.0,
            open_policy_entropy=1.0,
            open_policy_action_margin=0.8,
        )
        for _ in range(30)
    ]
    payload = leg_payload(
        rows=rows,
        zip_sha=INIT_SHA256,
        ticks_sha16="7e86c2bb1c71d514",
        price_sha16_value="deadbeef",
        optimizer_steps=0,
    )
    assert "t1b" in payload and "t5" in payload
    write_open_policy_signal_reports(
        reports=tmp_path,
        overall=OVERALL_INCONCLUSIVE,
        zip_sha=INIT_SHA256,
        payload_a=payload,
        payload_b=payload,
        t4={"grind_A": {"absent": True}},
        proto={"gate0_complete": True, "missing_sites": []},
        parent_loaded=True,
        gate0_sha="a9c5e32b10ed517c78091806b9f58c8e65a3f621",
        skip_replay=True,
    )
    verdict = (tmp_path / "AWAKENING_OPEN_POLICY_SIGNAL_VERDICT.md").read_text(encoding="utf-8")
    assert "Law shipped: NONE" in verdict
    assert "H_NONE" in verdict
    t0 = table_t0(rows, zip_sha256="ab", ticks_sha16="cd", price_sha16_value="ef", optimizer_steps=0)
    assert t0["n_policy"] == 80
    assert table_t1(rows)["n_H"] == 50
    assert "open_policy_value" in table_t1b(rows)
    assert "P_VALUE" in table_t2(rows)
    assert "drop_H" in table_t3(rows)["P_VALUE"]
    assert table_t5(rows)["P_VALUE"]["READ_ONLY_FLIP"] is True
    t4 = table_t4(tmp_path)
    assert t4["grind_A"]["absent"] is True


def test_coverage_extract_success_and_empty() -> None:
    from lumina_core.birth.policy_signal_extract import extract_policy_signals

    empty = extract_policy_signals(None, np.zeros(4, dtype=np.float32))
    assert empty["open_policy_value"] is None
    class _Dist:
        def entropy(self) -> Any:
            return np.array([0.5], dtype=np.float64)

        @property
        def distribution(self) -> Any:
            return SimpleNamespace(probs=np.array([0.6, 0.4], dtype=np.float64))

    class _Policy:
        training = False

        def eval(self) -> None:
            return None

        def train(self) -> None:
            return None

        def predict_values(self, obs: Any) -> Any:
            _ = obs
            return np.array([[0.1]], dtype=np.float64)

        def get_distribution(self, obs: Any) -> Any:
            _ = obs
            return _Dist()

    model = SimpleNamespace(policy=_Policy())
    got = extract_policy_signals(model, np.zeros(4, dtype=np.float32), action=0)
    assert got["open_policy_value"] == pytest.approx(0.1)
    assert got["open_policy_p_chosen"] == pytest.approx(0.6)


def test_coverage_telem_policy_kwargs() -> None:
    from lumina_core.birth.sim_runner_entry_telem import start_open_telem

    stash = start_open_telem(
        entry_regime="NEUTRAL",
        entry_bar_index=1,
        entry_price=20000.0,
        side=1,
        open_policy_value=-0.2,
        open_policy_entropy=0.8,
        open_policy_action_margin=0.15,
        open_policy_p_chosen=0.55,
        open_policy_margin_is_top2=False,
    )
    assert stash["open_policy_p_chosen"] == pytest.approx(0.55)
    bare = start_open_telem(entry_regime="NEUTRAL", entry_bar_index=0, entry_price=1.0, side=1)
    assert "open_policy_value" not in bare


def test_coverage_inspect_complete() -> None:
    from lumina_core.birth.awakening_open_policy_signal_path import inspect_open_policy_signal_protocol

    dump = inspect_open_policy_signal_protocol()
    assert dump["gate0_complete"] is True


def test_coverage_gate0_incomplete_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import lumina_core.birth.awakening_open_policy_signal_run as run_mod
    from lumina_core.birth.awakening_open_policy_signal_run import run_open_policy_signal

    monkeypatch.setattr(
        run_mod,
        "inspect_open_policy_signal_protocol",
        lambda: {"gate0_complete": False, "missing_sites": ["last_open_signal"]},
    )
    with pytest.raises(OpenPolicySignalProtocolError, match="Gate 0"):
        run_open_policy_signal(reports=tmp_path, skip_replay=True)
