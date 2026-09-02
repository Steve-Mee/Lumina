"""Headless cloud Birth runner: certified path, no practice-floor cheat."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from lumina_core.birth.birth_certificate import BirthCertificateThresholds
from lumina_core.maturity.birth_exit import is_birth_exit_sufficient
from scripts import run_birth_cloud_shadow as runner


@pytest.mark.unit
def test_workspace_overlay_does_not_lower_cert_or_stage_floors(tmp_path: Path) -> None:
    src = Path("config.yaml")
    dest = tmp_path / "config.yaml"
    dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    runner._overlay_workspace_config(dest)
    raw = yaml.safe_load(dest.read_text(encoding="utf-8"))
    assert raw["mode"] == "sim"
    assert raw["trading"]["instrument"] == "NQ SEP26"
    assert raw["birth_v2"]["prefer_real_data_only"] is True
    assert raw["first_boot"]["allow_minimal_synthetic_fallback"] is False
    thresholds = raw["birth_v2"]["certificate_thresholds"]
    assert float(thresholds["min_oos_winrate"]) == pytest.approx(0.48)
    assert float(thresholds["min_oos_sharpe"]) == pytest.approx(0.35)
    cur = raw["birth_v2"]["curriculum"]
    assert float(cur["birth_survival_wr_floor"]) == pytest.approx(0.20)
    # Interval may drop; pass law must not.
    assert int(cur["stage1_trend_trades"]) == 2000
    assert int(cur["stage2_range_trades"]) == 3000


@pytest.mark.unit
def test_empty_workspace_is_not_birth_exit(tmp_path: Path) -> None:
    assert is_birth_exit_sufficient(tmp_path) is False


@pytest.mark.unit
def test_exit_mapping_timeout_and_infra(tmp_path: Path) -> None:
    assert runner._map_exit({"status": "paused"}, timed_out=True, workspace=tmp_path) == 124
    assert runner._map_exit({"status": "history_unavailable"}, timed_out=False, workspace=tmp_path) == 3
    assert runner._map_exit({"status": "stage_stalled"}, timed_out=False, workspace=tmp_path) == 2


@pytest.mark.unit
def test_certificate_thresholds_object_unchanged_by_runner() -> None:
    t = BirthCertificateThresholds()
    assert t.min_oos_winrate == pytest.approx(0.48)
    assert t.min_regimes == 3
