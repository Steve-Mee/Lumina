"""Organism phase continuum: checkpoints, advance modes, wipe, strict proofs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lumina_core.maturity.advance_policy import confirm_telegram_advance, on_phase_complete
from lumina_core.maturity.continuum import (
    load_continuum,
    mark_phase_completed,
    mark_phase_failed,
    next_phase_id,
    save_continuum,
    set_advance_mode,
    set_pending_advance,
)
from lumina_core.maturity.phase_runners import run_apprenticeship, run_awakening, run_playground, run_proving_ground
from lumina_core.maturity.wipe import wipe_all_maturation, wipe_phase


@pytest.mark.unit
def test_failed_phase_does_not_keep_loading_message(tmp_path: Path) -> None:
    from lumina_core.maturity.continuum import mark_phase_running
    from lumina_core.maturity.phase_runners.common import write_phase_progress

    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=["setup"])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=["foundation"])
    mark_phase_running(tmp_path, "awakening", learned={"status": "starting"})
    write_phase_progress(
        tmp_path, "awakening", progress_pct=18.0, message="Loading frozen π* + Birth split"
    )
    mark_phase_failed(
        tmp_path,
        "awakening",
        error="[WinError 5] Toegang geweigerd: continuum.json.tmp -> continuum.json",
    )
    rec = load_continuum(tmp_path)["phase_records"]["awakening"]
    assert rec["status"] == "failed"
    assert str(rec.get("message") or "").startswith("Failed:")
    assert "WinError 5" in str(rec.get("message"))
    assert "Loading frozen" not in str(rec.get("message"))


@pytest.mark.unit
def test_save_continuum_retries_winerror_5(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    dest = tmp_path / "state" / "lumina_phase_continuum.json"
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=["setup"])
    calls = {"n": 0}
    real_replace = os.replace

    def _flaky(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        calls["n"] += 1
        if Path(dst) == dest and calls["n"] < 3:
            err = PermissionError(13, "Access is denied")
            setattr(err, "winerror", 5)
            raise err
        real_replace(src, dst)

    monkeypatch.setattr("lumina_core.io.atomic_fs.os.replace", _flaky)
    save_continuum(tmp_path, load_continuum(tmp_path))
    assert dest.is_file()
    assert calls["n"] >= 3

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

    result = wipe_all_maturation(tmp_path, confirm=True)
    assert result["ok"] is True
    data = load_continuum(tmp_path)
    assert data["completed_phases"] == ["genesis"]
    assert (tmp_path / "state" / "lumina_setup_complete.json").is_file()


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
    from tests.maturity.test_awakening_law import _write_pass_workspace

    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    _write_pass_workspace(tmp_path)

    with patch(
        "lumina_core.maturity.maturation_progress.sync_maturation_from_birth_state",
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

    result = run_playground(
        tmp_path, should_stop=lambda: True, poll_sec=0.0, sleep_fn=lambda _s: None
    )
    assert result["ok"] is False
    assert "sim_envelope_sealed" in (result.get("missing") or [])


@pytest.mark.unit
def test_apprenticeship_incomplete_without_green_streak(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "playground", learned={}, exit_proofs=[])

    result = run_apprenticeship(tmp_path, should_stop=lambda: True)
    assert result["ok"] is False
    assert result.get("status") == "incomplete"
    data = load_continuum(tmp_path)
    assert "apprenticeship" not in data["completed_phases"]


@pytest.mark.unit
def test_apprenticeship_ready_report_cannot_complete(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "playground", learned={}, exit_proofs=[])
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    (tmp_path / "state" / "sim_stability_report.json").write_text(
        '{"READY_FOR_REAL": true, "consecutive_green_days": 5}',
        encoding="utf-8",
    )

    result = run_apprenticeship(tmp_path, should_stop=lambda: True)
    assert result["ok"] is False
    data = load_continuum(tmp_path)
    assert "apprenticeship" not in data["completed_phases"]


@pytest.mark.unit
def test_proving_without_law_cannot_complete(tmp_path: Path) -> None:
    mark_phase_completed(tmp_path, "genesis", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "birth", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "awakening", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "playground", learned={}, exit_proofs=[])
    mark_phase_completed(tmp_path, "apprenticeship", learned={}, exit_proofs=[])
    (tmp_path / "state").mkdir(parents=True, exist_ok=True)
    result = run_proving_ground(tmp_path, should_stop=lambda: True)
    assert result["ok"] is False
    assert result.get("status") == "incomplete"
    data = load_continuum(tmp_path)
    assert "proving_ground" not in data["completed_phases"]
    rec = (data.get("phase_records") or {}).get("proving_ground") or {}
    assert rec.get("status") != "failed"


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
