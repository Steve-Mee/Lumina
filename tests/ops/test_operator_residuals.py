"""OR1–OR6 operator residual board tests."""

from __future__ import annotations

from pathlib import Path

from lumina_core.ops.operator_residuals import build_operator_residuals_report


def test_board_schema_and_six_items(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    report = build_operator_residuals_report(workspace=tmp_path, run_fabric_mock=False)
    assert report["schema"] == "operator_residuals_or1_or6_v1"
    ids = [i["id"] for i in report["items"]]
    assert ids == ["OR1", "OR2", "OR3", "OR4", "OR5", "OR6"]
    assert "sp3_sp4_readiness" in report
    assert report["sp1_sp2_status"]["SP1"].startswith("implemented")
    assert report["sp1_sp2_status"]["SP2"].startswith("implemented")


def test_freeze_blocks_sp3(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir()
    (state / "lumina_birth_progress.json").write_text(
        '{"swarm_rejected_no_lift": true, "swarm_champion_accepted": false, '
        '"needs_attention": true}',
        encoding="utf-8",
    )
    report = build_operator_residuals_report(workspace=tmp_path, run_fabric_mock=False)
    or5 = next(i for i in report["items"] if i["id"] == "OR5")
    assert or5["status"] == "blocked"
    assert or5["blocks_sp3"] is True
    assert "OR5" in report["sp3_sp4_readiness"]["blockers"]
    assert report["sp3_sp4_readiness"]["ready"] is False


def test_no_freeze_or5_green(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    report = build_operator_residuals_report(workspace=tmp_path, run_fabric_mock=False)
    or5 = next(i for i in report["items"] if i["id"] == "OR5")
    assert or5["status"] == "green"
    assert or5["blocks_sp3"] is False


def test_aperture_soft_without_samples(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir()
    report = build_operator_residuals_report(workspace=tmp_path, run_fabric_mock=False)
    or2 = next(i for i in report["items"] if i["id"] == "OR2")
    assert or2["status"] in {"yellow", "green"}
    assert or2["automated_ok"] is True
