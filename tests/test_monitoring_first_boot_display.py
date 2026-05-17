"""First-boot metric uses progress stage (not only the flag file)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    ("stage", "flag", "policy", "expected_label"),
    [
        ("detected", True, False, "In progress"),
        ("loading_data", True, False, "In progress"),
        ("training_running", True, False, "In progress"),
        ("completed", True, True, "Yes"),
        ("failed", True, False, "Failed"),
        ("deferred_calendar", False, False, "Deferred"),
        ("", False, False, "No"),
        ("", True, True, "Yes"),
        ("", True, False, "No"),
    ],
)
def test_first_boot_completion_display(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    flag: bool,
    policy: bool,
    expected_label: str,
) -> None:
    from lumina_os.frontend import monitoring_dashboard as md

    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    flag_path = state_dir / "first_boot_completed.flag"
    policy_path = tmp_path / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    paths = md._MonitoringPaths.resolve(tmp_path)

    if flag:
        flag_path.write_text("2026-01-01T00:00:00", encoding="utf-8")
    if policy:
        policy_path.parent.mkdir(parents=True, exist_ok=True)
        policy_path.write_bytes(b"x")

    progress = {"stage": stage, "timestamp": "2026-01-02T00:00:00"}
    label, _ts = md._first_boot_completion_display(paths, progress)
    assert label == expected_label


def test_first_boot_progress_fraction_prefers_progress_pct() -> None:
    from lumina_os.frontend import monitoring_dashboard as md

    assert md._first_boot_progress_fraction({"stage": "training_running", "progress_pct": 52}) == 0.52
    assert md._first_boot_progress_fraction({"stage": "training_running"}) == 0.70


def test_first_boot_historical_days_prefers_actual() -> None:
    from lumina_os.frontend import monitoring_dashboard as md

    assert (
        md._first_boot_historical_days_display({"actual_real_days_loaded": 18, "estimated_real_days": 120}) == 18
    )
    assert md._first_boot_historical_days_display({"estimated_real_days": 120}) == 120
