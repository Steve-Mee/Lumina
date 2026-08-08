"""Organism phase continuum: checkpoints, advance modes, wipe, strict proofs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lumina_core.maturity.advance_policy import confirm_telegram_advance, on_phase_complete
from lumina_core.maturity.continuum import (
    load_continuum,
    mark_phase_completed,
    next_phase_id,
    set_advance_mode,
    set_pending_advance,
)
from lumina_core.maturity.phase_runners import run_apprenticeship, run_awakening, run_playground, run_proving_ground
from lumina_core.maturity.wipe import wipe_all_maturation, wipe_phase


@pytest.mark.unit
def test_next_phase_after_birth(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=["setup"])
    mark_phase_completed(tmp_path, "birth", learned={"trades": 1}, exit_proofs=["birth_complete"])
    data = load_continuum(tmp_path)
    assert next_phase_id(data["completed_phases"]) == "awakening"
    assert "birth" in data["completed_phases"]


@pytest.mark.unit
def test_advance_manual_stays_on_hub(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    set_advance_mode(tmp_path, "manual")
    result = on_phase_complete(tmp_path, "birth")
    assert result["action"] == "hub"
    assert result["next"] == "awakening"


@pytest.mark.unit
def test_advance_auto_evolve_starts_next_not_real(tmp_path: Path) -> None:
    for phase in ("genesis", "birth", "awakening", "playground", "apprenticeship", "proving_ground"):
        mark_phase_completed(tmp_path, phase, learned={}, exit_proofs=[])
    set_advance_mode(tmp_path, "auto_evolve")
    result = on_phase_complete(tmp_path, "proving_ground")
    assert result["next"] == "real"
    assert result["action"] == "hub_real_confirm"


@pytest.mark.unit
def test_advance_auto_evolve_chains_awakening(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    set_advance_mode(tmp_path, "auto_evolve")
    result = on_phase_complete(tmp_path, "birth")
    assert result["action"] == "auto_start"
    assert result["start_phase"] == "awakening"


@pytest.mark.unit
def test_telegram_confirm_token(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    set_advance_mode(tmp_path, "telegram")
    data = set_pending_advance(tmp_path, from_phase="birth", to_phase="awakening")
    token = (data.get("pending_advance") or {}).get("telegram_token")
    assert token
    bad = confirm_telegram_advance(tmp_path, token="wrong")
    assert bad["ok"] is False
    ok = confirm_telegram_advance(tmp_path, token=str(token))
    assert ok["ok"] is True
    assert ok["start_phase"] == "awakening"


@pytest.mark.unit
def test_wipe_phase_removes_from_completed(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])

    with patch(
        "lumina_launcher.services.birth_service.BirthService.wipe_all_birth_data",
        return_value={"status": "ok"},
    ), patch(
        "lumina_launcher.services.birth_service.BirthService.configure_workspace",
    ):
        result = wipe_phase(tmp_path, "awakening", confirm=True)
    assert result["ok"] is True
    data = load_continuum(tmp_path)
    assert "awakening" not in data["completed_phases"]
    assert "birth" in data["completed_phases"]


@pytest.mark.unit
def test_wipe_all_resets_to_genesis(tmp_path: Path) -> None:
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "lumina_setup_complete.json").write_text("{}", encoding="utf-8")
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])

    with patch(
        "lumina_launcher.services.birth_service.BirthService.wipe_all_birth_data",
        return_value={"status": "ok"},
    ), patch(
        "lumina_launcher.services.birth_service.BirthService.configure_workspace",
    ):
        result = wipe_all_maturation(tmp_path, confirm=True)
    assert result["ok"] is True
    data = load_continuum(tmp_path)
    assert data["completed_phases"] == ["genesis"]


@pytest.mark.unit
def test_wipe_requires_confirm(tmp_path: Path) -> None:
    result = wipe_phase(tmp_path, "awakening", confirm=False)
    assert result["ok"] is False


@pytest.mark.unit
def test_awakening_fails_without_evolution_or_twin(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)

    with patch(
        "lumina_core.maturity.maturation_progress.sync_maturation_from_birth_state",
    ), patch(
        "lumina_core.birth.evolution_proof_gate.evolution_proof_passed",
        return_value=False,
    ), patch(
        "lumina_core.maturity.phase_runners.common.load_maturity_config",
        return_value=MagicMock(
            strict_exit_proofs=True,
            experimental_soft_complete=False,
            awakening_min_twin_samples=10,
            playground_require_first_order=True,
            apprenticeship_min_green_days=5,
            proving_require_promotion_or_shadow=True,
            apprenticeship_sim_days_probe=0,
        ),
    ), patch(
        "lumina_core.maturity.phase_specs.load_maturity_config",
        return_value=MagicMock(
            strict_exit_proofs=True,
            experimental_soft_complete=False,
            awakening_min_twin_samples=10,
            playground_require_first_order=True,
            apprenticeship_min_green_days=5,
            proving_require_promotion_or_shadow=True,
            apprenticeship_sim_days_probe=0,
        ),
    ):
        result = run_awakening(tmp_path)
    assert result["ok"] is False
    data = load_continuum(tmp_path)
    assert "awakening" not in data["completed_phases"]


@pytest.mark.unit
def test_awakening_completes_with_evolution_and_twin(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    state = tmp_path / "state"
    state.mkdir(parents=True, exist_ok=True)
    (state / "twin_mode_metrics_summary.json").write_text(
        '{"samples": 25}', encoding="utf-8"
    )

    with patch(
        "lumina_core.maturity.maturation_progress.sync_maturation_from_birth_state",
    ), patch(
        "lumina_core.birth.evolution_proof_gate.evolution_proof_passed",
        return_value=True,
    ), patch(
        "lumina_core.birth.evolution_proof_gate.load_evolution_proof_record",
        return_value={"oos_winrate": 0.5},
    ), patch(
        "lumina_core.maturity.phase_runners.common.load_maturity_config",
        return_value=MagicMock(
            strict_exit_proofs=True,
            experimental_soft_complete=False,
            awakening_min_twin_samples=10,
            playground_require_first_order=True,
            apprenticeship_min_green_days=5,
            proving_require_promotion_or_shadow=True,
            apprenticeship_sim_days_probe=0,
        ),
    ), patch(
        "lumina_core.maturity.phase_specs.load_maturity_config",
        return_value=MagicMock(
            strict_exit_proofs=True,
            experimental_soft_complete=False,
            awakening_min_twin_samples=10,
            playground_require_first_order=True,
            apprenticeship_min_green_days=5,
            proving_require_promotion_or_shadow=True,
            apprenticeship_sim_days_probe=0,
        ),
    ):
        result = run_awakening(tmp_path)
    assert result["ok"] is True
    data = load_continuum(tmp_path)
    assert "awakening" in data["completed_phases"]


@pytest.mark.unit
def test_playground_fails_without_envelope(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])

    with patch(
        "lumina_core.maturity.maturation_progress.sync_maturation_from_birth_state",
    ), patch(
        "lumina_core.maturity.phase_specs._sim_envelope_sealed",
        return_value=False,
    ), patch(
        "lumina_core.maturity.phase_runners.playground._sim_envelope_sealed",
        return_value=False,
    ), patch(
        "lumina_core.maturity.phase_specs.load_maturity_config",
        return_value=MagicMock(
            strict_exit_proofs=True,
            experimental_soft_complete=False,
            awakening_min_twin_samples=10,
            playground_require_first_order=True,
            apprenticeship_min_green_days=5,
            proving_require_promotion_or_shadow=True,
            apprenticeship_sim_days_probe=0,
        ),
    ), patch(
        "lumina_core.maturity.phase_runners.common.load_maturity_config",
        return_value=MagicMock(
            strict_exit_proofs=True,
            experimental_soft_complete=False,
            playground_require_first_order=True,
        ),
    ):
        result = run_playground(tmp_path)
    assert result["ok"] is False
    assert "sim_envelope_sealed" in (result.get("missing") or [])


@pytest.mark.unit
def test_apprenticeship_incomplete_without_green_streak(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "playground", learned={}, exit_proofs=[])

    cfg = MagicMock(
        strict_exit_proofs=True,
        experimental_soft_complete=False,
        apprenticeship_min_green_days=5,
        apprenticeship_sim_days=0,
        apprenticeship_sim_days_probe=0,
        playground_require_first_order=True,
        proving_require_promotion_or_shadow=True,
        awakening_min_twin_samples=10,
    )
    with patch(
        "lumina_core.maturity.maturation_progress.sync_stability_milestone",
    ), patch(
        "lumina_core.engine.sim_stability_checker.generate_stability_report",
        return_value={"READY_FOR_REAL": False, "consecutive_green_days": 1},
    ), patch(
        "lumina_core.maturity.phase_runners.common.load_maturity_config",
        return_value=cfg,
    ), patch(
        "lumina_core.maturity.phase_runners.apprenticeship.cfg",
        return_value=cfg,
    ), patch(
        "lumina_core.maturity.phase_specs.load_maturity_config",
        return_value=cfg,
    ):
        result = run_apprenticeship(tmp_path)
    assert result["ok"] is False
    assert result.get("status") == "incomplete"
    data = load_continuum(tmp_path)
    assert "apprenticeship" not in data["completed_phases"]


@pytest.mark.unit
def test_apprenticeship_completes_when_ready_for_real(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "playground", learned={}, exit_proofs=[])

    cfg = MagicMock(
        strict_exit_proofs=True,
        experimental_soft_complete=False,
        apprenticeship_min_green_days=5,
        apprenticeship_sim_days=0,
        apprenticeship_sim_days_probe=0,
        playground_require_first_order=True,
        proving_require_promotion_or_shadow=True,
        awakening_min_twin_samples=10,
    )
    with patch(
        "lumina_core.maturity.maturation_progress.sync_stability_milestone",
    ), patch(
        "lumina_core.engine.sim_stability_checker.generate_stability_report",
        return_value={"READY_FOR_REAL": True, "consecutive_green_days": 5},
    ), patch(
        "lumina_core.maturity.phase_runners.common.load_maturity_config",
        return_value=cfg,
    ), patch(
        "lumina_core.maturity.phase_runners.apprenticeship.cfg",
        return_value=cfg,
    ), patch(
        "lumina_core.maturity.phase_specs.load_maturity_config",
        return_value=cfg,
    ):
        result = run_apprenticeship(tmp_path)
    assert result["ok"] is True
    data = load_continuum(tmp_path)
    assert "apprenticeship" in data["completed_phases"]


@pytest.mark.unit
def test_proving_requires_audit_pass(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "playground", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "apprenticeship", learned={}, exit_proofs=[])
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)

    cfg = MagicMock(
        strict_exit_proofs=True,
        experimental_soft_complete=False,
        proving_require_promotion_or_shadow=True,
        apprenticeship_min_green_days=5,
        playground_require_first_order=True,
        awakening_min_twin_samples=10,
        apprenticeship_sim_days_probe=0,
    )
    with patch(
        "lumina_core.maturity.phase_specs.load_maturity_config",
        return_value=cfg,
    ), patch(
        "lumina_core.maturity.phase_runners.common.load_maturity_config",
        return_value=cfg,
    ):
        result = run_proving_ground(tmp_path)
    assert result["ok"] is False
    data = load_continuum(tmp_path)
    assert "proving_ground" not in data["completed_phases"]
    audit = tmp_path / "state" / "promotion_gate_audit.jsonl"
    assert audit.is_file()
    assert "insufficient_shadow_evidence" in audit.read_text(encoding="utf-8")


@pytest.mark.unit
def test_try_handle_telegram_text_yes_token(tmp_path: Path) -> None:
    from lumina_core.maturity.advance_policy import try_handle_telegram_text

    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    data = set_pending_advance(tmp_path, from_phase="birth", to_phase="awakening")
    token = (data.get("pending_advance") or {}).get("telegram_token")
    assert token

    with patch(
        "lumina_core.maturity.maturity_service.maturity_service.start_phase",
        return_value={"ok": True, "phase": "awakening", "status": "started"},
    ) as start, patch(
        "lumina_core.maturity.maturity_service.maturity_service.configure_workspace",
    ):
        # Wire try_handle to use our tmp_path
        result = try_handle_telegram_text(tmp_path, f"YES {token}")
    assert result is not None
    assert result.get("ok") is True
    start.assert_called()
