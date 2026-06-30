"""Tests for birth stage forensics budget reporting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from scripts.birth_stage_forensics import build_report


@pytest.mark.unit
def test_build_report_detects_genesis_engine_budget_mismatch(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True)
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        json.dumps(
            {
                "cumulative_trades": 11_074,
                "target_trades": 10_000,
                "phase": "stage_stalled",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "birth_v2": {
                    "trade_budget_cap": 10_000,
                    "curriculum": {},
                },
                "first_boot": {"training_trades": 25_000},
            }
        ),
        encoding="utf-8",
    )

    report = build_report(tmp_path)
    budget = report["budget_forensics"]
    assert budget["budget_mismatch"] is True
    assert "first_boot.training_trades=25000" in str(budget["budget_mismatch_detail"])
    assert budget["cumulative_trades"] == 11_074


@pytest.mark.unit
def test_build_report_no_mismatch_when_aligned(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True)
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        json.dumps({"cumulative_trades": 500, "target_trades": 25_000, "phase": "running"}),
        encoding="utf-8",
    )
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump(
            {
                "birth_v2": {"trade_budget_cap": 25_000, "curriculum": {}},
                "first_boot": {"training_trades": 25_000},
            }
        ),
        encoding="utf-8",
    )

    report = build_report(tmp_path)
    assert report["budget_forensics"]["budget_mismatch"] is False


@pytest.mark.unit
def test_build_report_stage_pass_audit_included(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True)
    (tmp_path / "config.yaml").write_text(
        yaml.safe_dump({"birth_v2": {"trade_budget_cap": 10_000, "curriculum": {}}}),
        encoding="utf-8",
    )
    (tmp_path / "state" / "lumina_birth_progress.json").write_text(
        json.dumps({"curriculum_stage": "stage1_trend", "stages_passed": []}),
        encoding="utf-8",
    )

    report = build_report(tmp_path)
    assert "stage_pass_audit" in report
    assert report["stage_pass_audit"]["integrity_ok"] is True
