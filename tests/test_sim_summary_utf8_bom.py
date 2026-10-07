"""Stability summaries written by PowerShell must still parse."""

from __future__ import annotations

from pathlib import Path

from lumina_core.engine.sim_stability_history import _load_summary


def test_load_summary_accepts_utf8_bom(tmp_path: Path) -> None:
    path = tmp_path / "summary_sim_x.json"
    path.write_bytes(b"\xef\xbb\xbf" + b'{"mode": "sim", "sharpe": 1}')
    loaded = _load_summary(path)
    assert loaded is not None
    assert loaded["mode"] == "sim"
