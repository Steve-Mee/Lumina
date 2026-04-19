from __future__ import annotations

import json
from pathlib import Path

from lumina_core.engine import sim_stability_checker as ssc


def test_iter_summary_paths_avoids_resolve_and_dedupes(tmp_path: Path, monkeypatch) -> None:
    state_dir = tmp_path / "state"
    test_runs_dir = state_dir / "test_runs"
    state_dir.mkdir(parents=True, exist_ok=True)
    test_runs_dir.mkdir(parents=True, exist_ok=True)

    # Real files are used so glob behavior stays realistic while we still control keys.
    for file_name in ("last_run_summary.json", "dup.json"):
        (state_dir / file_name).write_text(json.dumps({"mode": "sim"}), encoding="utf-8")
    for file_name in ("dup.json", "run1.json"):
        (test_runs_dir / file_name).write_text(json.dumps({"mode": "sim"}), encoding="utf-8")

    monkeypatch.setattr(ssc, "_STATE_DIR", state_dir)
    monkeypatch.setattr(ssc, "_TEST_RUNS_DIR", test_runs_dir)

    # Force a duplicate key for both dup.json files while keeping others unique.
    monkeypatch.setattr(
        ssc,
        "_dedupe_key",
        lambda p: "same-key" if p.name == "dup.json" else str(p).lower().replace("\\", "/"),
    )

    paths = ssc._iter_summary_paths()

    assert [p.name for p in paths] == ["dup.json", "last_run_summary.json", "run1.json"]
