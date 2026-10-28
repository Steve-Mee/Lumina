"""Birth reset scope: genesis wipe vs post-cert maturation-only wipe."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.maturity.continuum import load_continuum, mark_phase_completed
from lumina_launcher.core.birth_reset import (
    BIRTH_DELETE_TARGETS,
    FOUNDATION_EXIT_DELETE_TARGETS,
    clear_birth_training_state,
    clear_post_birth_maturation_only,
)


def _touch(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    state.mkdir()
    _touch(state / "lumina_birth_progress.json", "{}")
    _touch(state / "lumina_setup_complete.json", "{}")
    _touch(state / "first_boot_user_configured.flag", "1")
    _touch(state / "lumina_daytrading_bible.json", "{}")
    _touch(state / "lumina_maturity_progress.json", "{}")
    _touch(state / "lumina_genesis_charter.json", "{}")
    _touch(state / "lumina_birth_fitness_vector.json", "{}")
    _touch(state / "dna_registry.jsonl", "{}\n")
    _touch(state / "dna_registry.sqlite3", "db")
    _touch(state / "dna_registry.sqlite3-wal", "wal")
    _touch(state / "lumina_evolution_proof.json", "{}")
    _touch(state / "perfect_birth_complete.flag", "1")
    _touch(state / "perfect_birth_complete.json", "{}")
    _touch(state / "champion_freeze_telegram_pending.json", "{}")
    _touch(state / "milestone_notified.json", "{}")
    cache = state / "birth_enrichment_cache"
    cache.mkdir()
    _touch(cache / "sample.meta.json", "{}")
    return tmp_path


def _assert_foundation_exit_gone(workspace: Path) -> None:
    state = workspace / "state"
    assert not (state / "lumina_birth_fitness_vector.json").exists()
    assert not (state / "dna_registry.jsonl").exists()
    assert not (state / "dna_registry.sqlite3").exists()
    assert not (state / "dna_registry.sqlite3-wal").exists()
    assert not (state / "lumina_evolution_proof.json").exists()
    assert not (state / "perfect_birth_complete.flag").exists()
    assert not (state / "perfect_birth_complete.json").exists()
    assert not (state / "champion_freeze_telegram_pending.json").exists()
    assert not (state / "milestone_notified.json").exists()
    continuum = load_continuum(workspace)
    assert "birth" not in (continuum.get("completed_phases") or [])


@pytest.mark.unit
def test_apply_quarantine_on_checkpoint_resume_delegates() -> None:
    from lumina_core.birth.checkpoint import apply_plateau_quarantine_on_checkpoint_resume
    from lumina_core.birth.config import BirthCurriculumConfig

    cfg = BirthCurriculumConfig(plateau_quarantine_rollouts=16, plateau_quarantine_min_trades=250)
    q = apply_plateau_quarantine_on_checkpoint_resume(cfg=cfg, stage_trades=12_000)
    assert q["plateau_quarantine_active"] is True
    assert q["plateau_quarantine_rollouts_remaining"] == 16


@pytest.mark.unit
def test_foundation_exit_targets_are_in_birth_ssot() -> None:
    birth = set(BIRTH_DELETE_TARGETS)
    assert set(FOUNDATION_EXIT_DELETE_TARGETS) <= birth


@pytest.mark.unit
def test_full_wipe_removes_genesis_artifacts(workspace: Path) -> None:
    mark_phase_completed(workspace, "genesis", learned={}, exit_proofs=["setup"])
    mark_phase_completed(workspace, "birth", learned={}, exit_proofs=["foundation"])
    result = clear_birth_training_state(workspace, wipe_genesis=True)
    assert result.success is True
    assert not (workspace / "state" / "lumina_setup_complete.json").exists()
    assert not (workspace / "state" / "first_boot_user_configured.flag").exists()
    assert not (workspace / "state" / "lumina_daytrading_bible.json").exists()
    assert not (workspace / "state" / "lumina_genesis_charter.json").exists()
    assert not (workspace / "state" / "birth_enrichment_cache").exists()
    _assert_foundation_exit_gone(workspace)
    continuum = load_continuum(workspace)
    assert "genesis" not in (continuum.get("completed_phases") or [])


@pytest.mark.unit
def test_wipe_genesis_false_preserves_setup_and_bible(workspace: Path) -> None:
    mark_phase_completed(workspace, "genesis", learned={}, exit_proofs=["setup"])
    mark_phase_completed(workspace, "birth", learned={}, exit_proofs=["foundation"])
    result = clear_birth_training_state(workspace, wipe_genesis=False)
    assert result.success is True
    assert not (workspace / "state" / "lumina_birth_progress.json").exists()
    assert (workspace / "state" / "lumina_setup_complete.json").exists()
    assert (workspace / "state" / "lumina_daytrading_bible.json").exists()
    assert (workspace / "state" / "lumina_genesis_charter.json").exists()
    _assert_foundation_exit_gone(workspace)
    continuum = load_continuum(workspace)
    assert continuum.get("completed_phases") == ["genesis"]


@pytest.mark.unit
def test_post_cert_maturation_wipe_keeps_genesis_and_birth(workspace: Path) -> None:
    _touch(workspace / "state" / "lumina_birth_completed.flag", "1")
    ppo = workspace / "lumina_agents" / "ppo"
    _touch(ppo / "birth_best_stage4_viable_plant.zip", "zip")
    _touch(ppo / "birth_best_stage5_probe_handoff.zip", "zip")
    result = clear_post_birth_maturation_only(workspace)
    assert result.success is True
    assert not (workspace / "state" / "lumina_maturity_progress.json").exists()
    assert not (workspace / "state" / "lumina_evolution_proof.json").exists()
    assert not (workspace / "state" / "perfect_birth_complete.flag").exists()
    assert (workspace / "state" / "lumina_daytrading_bible.json").exists()
    assert (workspace / "state" / "lumina_birth_progress.json").exists()
    assert (workspace / "state" / "lumina_birth_fitness_vector.json").exists()
    assert (workspace / "state" / "dna_registry.jsonl").exists()
    assert (ppo / "birth_best_stage4_viable_plant.zip").exists()
    assert (ppo / "birth_best_stage5_probe_handoff.zip").exists()


@pytest.mark.unit
def test_post_cert_maturation_wipe_blocked_without_certificate(workspace: Path) -> None:
    result = clear_post_birth_maturation_only(workspace)
    assert result.success is False
