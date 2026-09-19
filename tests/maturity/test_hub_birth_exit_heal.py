"""Hub must checkpoint Birth from Foundation exit SSOT — never certificate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lumina_core.birth.fitness_vector import (
    BirthFitnessVector,
    receipt_checksum,
    write_fitness_vector,
)
from lumina_core.birth.progress import write_birth_progress
from lumina_core.maturity.birth_exit import is_birth_exit_sufficient
from lumina_core.maturity.continuum import load_continuum, next_phase_id
from lumina_core.maturity.continuum_honesty import continuum_honesty_snapshot
from lumina_core.maturity.maturity_service import MaturityService
from lumina_core.maturity.phase_specs import evaluate_exit_proofs, hub_payload
from tests.birth.test_foundation_loopholes import _v2_receipt


def _empty_continuum(tmp_path: Path) -> None:
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "lumina_phase_continuum.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "active_phase": None,
                "completed_phases": [],
                "phase_records": {},
                "advance_mode": "manual",
                "pending_advance": None,
            }
        ),
        encoding="utf-8",
    )


def _seed_foundation_exit(tmp_path: Path) -> None:
    receipts = [
        _v2_receipt("stage1_trend", occupancy=None),
        _v2_receipt("stage2_range"),
        _v2_receipt("stage3_mixed"),
        _v2_receipt("stage4_viable_plant"),
        _v2_receipt("stage5_probe_handoff", oos_sharpe=-1.25),
    ]
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    write_birth_progress(
        tmp_path,
        stage="completed",
        phase="completed",
        message="Birth Foundation complete",
        progress_pct=100.0,
        stage_pass_receipts=[r.to_dict() for r in receipts],
    )
    s5 = receipts[-1]
    write_fitness_vector(
        tmp_path,
        BirthFitnessVector(
            schema="foundation_v2",
            mean_r=float(s5.mean_r or 0.0),
            edge=float(s5.edge or 0.0),
            occupancy=float(s5.occupancy or 0.0),
            oos_wr=float(s5.winrate),
            oos_sharpe=float(s5.oos_sharpe or 0.0),
            median_loss_r=float(s5.median_loss_r or 0.0),
            s5_receipt_checksum=receipt_checksum(s5.to_dict()),
            trades=int(s5.trades),
        ),
    )
    (tmp_path / "state" / "lumina_birth_completed.flag").write_text("ok", encoding="utf-8")
    (tmp_path / "state" / "lumina_setup_complete.json").write_text(
        '{"completed": true}',
        encoding="utf-8",
    )
    _empty_continuum(tmp_path)


@pytest.mark.unit
def test_maturity_service_constructor_accepts_workspace(tmp_path: Path) -> None:
    _seed_foundation_exit(tmp_path)
    assert is_birth_exit_sufficient(tmp_path) is True
    svc = MaturityService(tmp_path)
    result = svc.mark_birth_complete_from_artifacts()
    assert result.get("ok") is True
    data = load_continuum(tmp_path)
    assert "genesis" in data["completed_phases"]
    assert "birth" in data["completed_phases"]
    assert next_phase_id(data["completed_phases"]) == "awakening"


@pytest.mark.unit
def test_empty_continuum_genesis_is_not_unknown_phase(tmp_path: Path) -> None:
    _seed_foundation_exit(tmp_path)
    ok, missing, _ = evaluate_exit_proofs(tmp_path, "genesis")
    assert ok is True
    assert "unknown_phase" not in missing
    hub = hub_payload(tmp_path)
    assert hub["last_completed"] is None
    assert hub["next_phase"] == "genesis"
    assert "unknown_phase" not in ((hub.get("exit_eval") or {}).get("missing") or [])
    snap = continuum_honesty_snapshot(tmp_path)
    codes = [d.get("code") for d in snap.get("continuum_vs_milestones_drift") or []]
    assert "birth_exit_without_continuum" in codes
    assert any(
        d.get("code") == "birth_exit_without_continuum" and d.get("severity") == "warning"
        for d in snap.get("continuum_vs_milestones_drift") or []
    )
    assert snap["honesty_ok"] is False


@pytest.mark.unit
def test_get_hub_heals_birth_complete_without_certificate(tmp_path: Path) -> None:
    _seed_foundation_exit(tmp_path)
    hub = MaturityService(tmp_path).get_hub()
    assert "birth" in (hub.get("completed_phases") or [])
    assert hub.get("next_phase") == "awakening"
    assert hub.get("last_completed") == "birth"
    assert hub.get("birth_exit_exited") is True
    assert hub.get("ready_for_real") is False
    assert hub.get("real_eligible") is False
    missing = (hub.get("exit_eval") or {}).get("missing") or []
    assert "unknown_phase" not in missing
    snap = continuum_honesty_snapshot(tmp_path)
    codes = [d.get("code") for d in snap.get("continuum_vs_milestones_drift") or []]
    assert "birth_exit_without_continuum" not in codes
    assert any("READY_FOR_REAL" in w for w in (hub.get("conflation_warnings") or []))
