from __future__ import annotations

from pathlib import Path

import yaml

from lumina_os.api.monitoring import enrich_observability_snapshot_for_react_dashboard


def test_enrichment_includes_training_target_and_completed(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"first_boot": {"training_trades": 12000}}),
        encoding="utf-8",
    )
    (state_dir / "first_boot_progress.json").write_text(
        '{"stage":"training_running","cumulative_trades":5498}',
        encoding="utf-8",
    )
    payload = enrich_observability_snapshot_for_react_dashboard({}, state_dir=state_dir)
    ui = payload["_lumina_ui"]
    assert ui["training_completed_trades"] == 5498
    assert ui["training_target_trades"] == 0
    assert ui["training_target_applicable"] is False
    assert ui["trades_completed"] == 5498
    assert ui["first_boot_stage"] == "training_running"


def test_enrichment_shows_training_target_only_when_user_configured(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"first_boot": {"training_trades": 12000}}),
        encoding="utf-8",
    )
    (state_dir / "first_boot_progress.json").write_text(
        '{"stage":"training_running","cumulative_trades":1000,"target_trades":12000}',
        encoding="utf-8",
    )
    (state_dir / "first_boot_user_configured.flag").write_text("ok", encoding="utf-8")
    payload = enrich_observability_snapshot_for_react_dashboard({}, state_dir=state_dir)
    ui = payload["_lumina_ui"]
    assert ui["training_target_trades"] == 12000
    assert ui["training_target_applicable"] is True


def test_enrichment_exposes_ppo_progress_fields(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({"first_boot": {"training_trades": 12000}}), encoding="utf-8")
    (state_dir / "first_boot_progress.json").write_text(
        '{"stage":"training_running","phase":"ppo_training","ppo_steps":120000,"ppo_timesteps_total":300000,"ppo_progress_pct":40.0}',
        encoding="utf-8",
    )
    payload = enrich_observability_snapshot_for_react_dashboard({}, state_dir=state_dir)
    ui = payload["_lumina_ui"]
    assert ui["ppo_steps"] == 120000
    assert ui["ppo_timesteps_total"] == 300000
    assert float(ui["ppo_progress_pct"]) == 40.0


def test_enrichment_marks_activity_stale_when_ppo_timestamp_stalls(tmp_path: Path, monkeypatch) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({"first_boot": {"training_trades": 12000}}), encoding="utf-8")
    (state_dir / "first_boot_progress.json").write_text(
        '{"stage":"training_running","phase":"ppo_training","timestamp":"2026-01-01T00:00:00+00:00","ppo_steps":5000}',
        encoding="utf-8",
    )
    (state_dir / "launcher_bot_process.json").write_text('{"pid": 1234}', encoding="utf-8")
    monkeypatch.setattr("lumina_os.api.monitoring._pid_alive", lambda pid: True)
    payload = enrich_observability_snapshot_for_react_dashboard({}, state_dir=state_dir)
    ui = payload["_lumina_ui"]
    assert ui["activity_stale"] is True
