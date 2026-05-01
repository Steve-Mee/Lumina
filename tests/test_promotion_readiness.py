from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.evolution.promotion_readiness import (
    check_promotion_readiness,
    extract_dna_hash_for_gate,
    is_protected_promotion_mode,
)


def test_sim_mode_skips_bundle() -> None:
    r = check_promotion_readiness(mode="sim", challenger={"name": "x"}, proposal=None)
    assert r.ok


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("real", True),
        ("paper", True),
        ("sim_real_guard", True),
        ("sim", False),
    ],
)
def test_protected_mode_detection(mode: str, expected: bool) -> None:
    assert is_protected_promotion_mode(mode) is expected


def test_reconciler_pending_blocks(tmp_path: Path) -> None:
    status = tmp_path / "st.json"
    status.write_text(
        json.dumps({"pending_count": 2, "last_error": None, "status": "ready"}),
        encoding="utf-8",
    )
    r = check_promotion_readiness(
        mode="real",
        challenger={"name": "c"},
        proposal=None,
        reconciler_status_path=status,
        reality_gap_history_path=tmp_path / "missing.jsonl",
    )
    assert not r.ok
    assert any("reconciler_pending" in x for x in r.reasons)


def test_reconciler_last_error_blocks(tmp_path: Path) -> None:
    status = tmp_path / "st.json"
    status.write_text(
        json.dumps({"pending_count": 0, "last_error": "ws down", "status": "ready"}),
        encoding="utf-8",
    )
    r = check_promotion_readiness(
        mode="paper",
        challenger={"name": "c"},
        proposal=None,
        reconciler_status_path=status,
        reality_gap_history_path=tmp_path / "missing.jsonl",
    )
    assert not r.ok


def test_reality_gap_red_blocks(tmp_path: Path) -> None:
    hist = tmp_path / "rg.jsonl"
    # Force many high-gap observations so mean gap lands in RED band (> 0.70)
    lines = []
    for i in range(25):
        lines.append(
            json.dumps(
                {
                    "ts": f"2026-01-{i+1:02d}T00:00:00Z",
                    "sim_sharpe": 3.0,
                    "real_sharpe": 0.5,
                    "gap": 2.5,
                    "penalty": 0.1,
                }
            )
        )
    hist.write_text("\n".join(lines), encoding="utf-8")
    r = check_promotion_readiness(
        mode="real",
        challenger={"name": "c"},
        proposal=None,
        reconciler_status_path=tmp_path / "no_reconciler.json",
        reality_gap_history_path=hist,
    )
    assert not r.ok
    assert any("reality_gap_band_red" in x for x in r.reasons)


def test_shadow_required_when_dna_hash_present(tmp_path: Path) -> None:
    shadow = tmp_path / "shadow.json"
    shadow.write_text(json.dumps({"abc": {"status": "failed"}}), encoding="utf-8")
    r = check_promotion_readiness(
        mode="real",
        challenger={"name": "c", "dna_hash": "abc"},
        proposal=None,
        reconciler_status_path=tmp_path / "nr.json",
        reality_gap_history_path=tmp_path / "nrg.jsonl",
        shadow_runs_path=shadow,
    )
    assert not r.ok


def test_shadow_passed_ok(tmp_path: Path) -> None:
    shadow = tmp_path / "shadow.json"
    shadow.write_text(json.dumps({"abc": {"status": "passed"}}), encoding="utf-8")
    r = check_promotion_readiness(
        mode="real",
        challenger={"name": "c", "dna_hash": "abc"},
        proposal=None,
        reconciler_status_path=tmp_path / "nr.json",
        reality_gap_history_path=tmp_path / "nrg.jsonl",
        shadow_runs_path=shadow,
    )
    assert r.ok


def test_extract_dna_hash_order() -> None:
    assert extract_dna_hash_for_gate({"dna_hash": "x"}, {"dna_hash": "y"}) == "x"
    assert extract_dna_hash_for_gate({}, {"promotion_dna_hash": "z"}) == "z"
