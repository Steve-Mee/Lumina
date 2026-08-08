"""T15: Twin mode SSOT audit tests."""

from __future__ import annotations

from pathlib import Path

from lumina_core.evolution.twin_mode_ssot_audit import build_twin_mode_ssot_audit


def _write_config(workspace: Path, *, mode: str = "shadow", auto_fa: bool = False) -> None:
    workspace.joinpath("config.yaml").write_text(
        f"""
evolution:
  approval_twin:
    mode: {mode}
    mode_promotion:
      auto_promote_when_ready: false
      auto_promote_full_auto_when_ready: {str(auto_fa).lower()}
      forbid_full_auto_in_real_capital: true
      mode_state_path: state/approval_twin_mode.json
      audit_path: state/twin_mode_promotion_audit.jsonl
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_ssot_from_config_shadow(tmp_path: Path) -> None:
    _write_config(tmp_path, mode="shadow")
    report = build_twin_mode_ssot_audit(workspace=tmp_path)
    assert report["ok"] is True
    assert report["ssot_mode"] == "shadow"
    assert report["ssot_source"] == "config_seed"
    assert report["config"]["full_auto_seed_ignored"] is False


def test_yaml_full_auto_seed_ignored(tmp_path: Path) -> None:
    _write_config(tmp_path, mode="full_auto")
    report = build_twin_mode_ssot_audit(workspace=tmp_path)
    assert report["ssot_mode"] == "shadow"
    assert report["ssot_source"] == "config_seed_full_auto_ignored"
    assert report["config"]["full_auto_seed_ignored"] is True
    # Critical not set for yaml alone — warn only
    assert report["ok"] is True
    assert report["has_warnings"] is True
    fa = next(f for f in report["findings"] if f["id"] == "yaml_full_auto_seed")
    assert fa["ok"] is False


def test_state_file_wins_over_config(tmp_path: Path) -> None:
    _write_config(tmp_path, mode="shadow")
    state = tmp_path / "state"
    state.mkdir()
    (state / "approval_twin_mode.json").write_text(
        '{"mode": "assisted", "reason": "gate_promote", "updated_at": "2026-01-01T00:00:00Z"}',
        encoding="utf-8",
    )
    report = build_twin_mode_ssot_audit(workspace=tmp_path)
    assert report["ssot_mode"] == "assisted"
    assert report["ssot_source"] == "state_file"
    assert report["state"]["mode"] == "assisted"
    assert report["ok"] is True


def test_live_mismatch_is_critical(tmp_path: Path) -> None:
    _write_config(tmp_path, mode="shadow")
    state = tmp_path / "state"
    state.mkdir()
    (state / "approval_twin_mode.json").write_text(
        '{"mode": "assisted", "reason": "gate"}',
        encoding="utf-8",
    )
    report = build_twin_mode_ssot_audit(workspace=tmp_path, live_mode="shadow")
    assert report["ok"] is False
    assert report["critical_count"] >= 1
    live = next(f for f in report["findings"] if f["id"] == "live_matches_ssot")
    assert live["ok"] is False


def test_full_auto_under_real_critical(tmp_path: Path) -> None:
    _write_config(tmp_path, mode="shadow")
    state = tmp_path / "state"
    state.mkdir()
    (state / "approval_twin_mode.json").write_text(
        '{"mode": "full_auto", "reason": "gate"}',
        encoding="utf-8",
    )
    report = build_twin_mode_ssot_audit(
        workspace=tmp_path,
        capital_mode_hint="real",
    )
    assert report["ok"] is False
    assert report["real_like_capital"] is True
    fa = next(f for f in report["findings"] if f["id"] == "full_auto_under_real")
    assert fa["ok"] is False
    assert fa["severity"] == "critical"


def test_legacy_active_alias_as_full_auto_seed(tmp_path: Path) -> None:
    _write_config(tmp_path, mode="active")
    report = build_twin_mode_ssot_audit(workspace=tmp_path)
    assert report["config"]["full_auto_seed_ignored"] is True
    assert report["ssot_mode"] == "shadow"
