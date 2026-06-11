"""Tests for Protocol Adherence Rate measurement."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from lumina_core.audit.protocol_adherence import (
    assess_evolution_log_text,
    is_classified_meta_entry,
    measure_protocol_adherence,
)


@pytest.mark.unit
def test_assess_adherent_entry():
    text = """
# Meta change
**Hypothesis**: X improves Y.
**Prediction (30d)**: measurable uplift.
**Rollback**: revert file Z.
"""
    adherent, missing = assess_evolution_log_text(text)
    assert adherent is True
    assert missing == ()


@pytest.mark.unit
def test_assess_missing_rollback():
    text = "**Hypothesis**: only hypothesis and falsifiable prediction here."
    adherent, missing = assess_evolution_log_text(text)
    assert adherent is False
    assert "rollback" in missing


@pytest.mark.unit
def test_classified_only_skips_unmarked_logs(tmp_path: Path):
    log_dir = tmp_path / "evolution" / "log"
    log_dir.mkdir(parents=True)
    (log_dir / "2026-06-11-bare.md").write_text("executed only\n", encoding="utf-8")
    (log_dir / "2026-06-11-meta.md").write_text(
        "**Classification**: Small\n**Hypothesis**: x\n**Prediction**: y\n**Rollback**: z\n",
        encoding="utf-8",
    )
    result = measure_protocol_adherence(log_dir=log_dir, since=date(2026, 6, 1), classified_only=True)
    assert result["total_entries"] == 1
    assert result["skipped_unclassified"] == 1


@pytest.mark.unit
def test_is_classified_meta_entry():
    assert is_classified_meta_entry("**Classification**: Small\n") is True
    assert is_classified_meta_entry("no marker") is False


@pytest.mark.unit
def test_measure_filters_by_since(tmp_path: Path):
    log_dir = tmp_path / "evolution" / "log"
    log_dir.mkdir(parents=True)
    (log_dir / "2026-05-01-old.md").write_text("no protocol markers", encoding="utf-8")
    (log_dir / "2026-06-11-good.md").write_text(
        "**Classification**: Small\n**Hypothesis**: ok\n**Prediction**: 30d\n**Rollback**: revert\n",
        encoding="utf-8",
    )
    result = measure_protocol_adherence(log_dir=log_dir, since=date(2026, 6, 1))
    assert result["total_entries"] == 1
    assert result["adherent_entries"] == 1
    assert result["pass"] is True
    print("MANUAL_SMOKE_PROTOCOL_ADHERENCE_OK")
