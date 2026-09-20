"""Named hub wipes: awakening-only, birth-keep-history, full-keep-setup."""

from __future__ import annotations

from pathlib import Path

import pytest

from lumina_core.maturity.continuum import load_continuum, mark_phase_completed
from lumina_core.maturity.wipe import wipe_all_maturation, wipe_phase


def _touch(path: Path, content: str = "x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_workspace(root: Path) -> dict[str, Path]:
    state = root / "state"
    state.mkdir(parents=True, exist_ok=True)
    art = root / "reports" / "birth_cloud_run" / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    cache = state / "birth_enrichment_cache"
    cache.mkdir(parents=True, exist_ok=True)

    files = {
        "setup": state / "lumina_setup_complete.json",
        "charter": state / "lumina_genesis_charter.json",
        "bible": state / "lumina_daytrading_bible.json",
        "configured": state / "first_boot_user_configured.flag",
        "config": root / "config.yaml",
        "progress": state / "lumina_birth_progress.json",
        "fitness": state / "lumina_birth_fitness_vector.json",
        "completed": state / "lumina_birth_completed.flag",
        "receipts": state / "lumina_birth_foundation_receipts.json",
        "ticks": state / "lumina_birth_ticks_cache.jsonl",
        "split": state / "lumina_birth_split_cache.json",
        "manifest": state / "lumina_birth_cache_manifest.json",
        "enrich": cache / "sample.meta.json",
        "pi_star": art / "birth_exit_pi_star.zip",
        "pi_star_meta": art / "birth_exit_pi_star.json",
        "live_zip": art / "awakening_live_pi_star.zip",
        "live_meta": art / "awakening_live_pi_star.json",
        "live_ledger": art / "awakening_live_holdout.jsonl",
        "incumbent": art / "awakening_incumbent_pi_star.zip",
        "evo": state / "lumina_evolution_proof.json",
        "aw_progress": state / "lumina_awakening_progress.json",
        "aw_watch": state / "awakening_twin_watch.jsonl",
        "perfect": state / "perfect_birth_complete.flag",
        "exam_ext": state / "lumina_awakening_exam_ext.jsonl",
        "exam_man": state / "lumina_awakening_exam_manifest.json",
    }
    _touch(files["setup"], "{}")
    _touch(files["charter"], "{}")
    _touch(files["bible"], "{}")
    _touch(files["configured"], "1")
    _touch(files["config"], "mode: sim\n")
    _touch(files["progress"], '{"phase":"completed"}')
    _touch(files["fitness"], "{}")
    _touch(files["completed"], "1")
    _touch(files["receipts"], "[]")
    _touch(files["ticks"], "{}\n")
    _touch(files["split"], "{}")
    _touch(files["manifest"], "{}")
    _touch(files["enrich"], "{}")
    files["pi_star"].write_bytes(b"frozen-pi-star")
    _touch(files["pi_star_meta"], "{}")
    files["incumbent"].write_bytes(b"awakening-incumbent")
    files["live_zip"].write_bytes(b"awakening-child")
    _touch(files["live_meta"], "{}")
    _touch(files["live_ledger"], "{}\n")
    _touch(files["evo"], "{}")
    _touch(files["aw_progress"], '{"n_b":133}')
    _touch(files["aw_watch"], "{}\n")
    _touch(files["perfect"], "1")
    _touch(files["exam_ext"], "{}\n")
    _touch(files["exam_man"], "{}")

    mark_phase_completed(root, "genesis", learned={}, exit_proofs=["setup_complete"])
    mark_phase_completed(root, "birth", learned={"trades": 1145}, exit_proofs=["foundation"])
    mark_phase_completed(root, "awakening", learned={}, exit_proofs=["evolution_proof_passed"])
    mark_phase_completed(root, "playground", learned={}, exit_proofs=["deck_unlocked"])
    return files


@pytest.mark.unit
def test_wipe_awakening_keeps_birth_and_history(tmp_path: Path) -> None:
    files = _seed_workspace(tmp_path)
    result = wipe_phase(tmp_path, "awakening", confirm=True)
    assert result["ok"] is True
    data = load_continuum(tmp_path)
    assert "awakening" not in (data.get("completed_phases") or [])
    assert "playground" not in (data.get("completed_phases") or [])
    assert "birth" in (data.get("completed_phases") or [])
    assert "genesis" in (data.get("completed_phases") or [])
    assert not files["live_zip"].exists()
    assert not files["live_meta"].exists()
    assert not files["live_ledger"].exists()
    assert not files["evo"].exists()
    assert not files["aw_progress"].exists()
    assert not files["aw_watch"].exists()
    assert not files["perfect"].exists()
    assert not files["incumbent"].exists()
    assert not files["exam_ext"].exists()
    assert not files["exam_man"].exists()
    assert files["pi_star"].is_file()
    assert files["pi_star"].read_bytes() == b"frozen-pi-star"
    assert files["pi_star_meta"].read_text(encoding="utf-8") == "{}"
    assert files["fitness"].is_file()
    assert files["completed"].is_file()
    assert files["progress"].is_file()
    assert files["receipts"].is_file()
    assert files["ticks"].is_file()
    assert files["split"].is_file()
    assert files["setup"].is_file()
    assert files["config"].is_file()


@pytest.mark.unit
def test_wipe_birth_keeps_setup_and_tick_cache(tmp_path: Path) -> None:
    files = _seed_workspace(tmp_path)
    result = wipe_phase(tmp_path, "birth", confirm=True)
    assert result["ok"] is True
    data = load_continuum(tmp_path)
    assert data.get("completed_phases") == ["genesis"]
    assert not files["progress"].exists()
    assert not files["fitness"].exists()
    assert not files["completed"].exists()
    assert not files["live_zip"].exists()
    assert not files["evo"].exists()
    assert files["ticks"].is_file()
    assert files["split"].is_file()
    assert files["enrich"].is_file()
    assert files["setup"].is_file()
    assert files["charter"].is_file()
    assert files["bible"].is_file()
    assert files["config"].read_text(encoding="utf-8") == "mode: sim\n"
    assert not files["pi_star"].exists()
    assert not files["pi_star_meta"].exists()


@pytest.mark.unit
def test_full_wipe_keeps_setup_drops_history(tmp_path: Path) -> None:
    files = _seed_workspace(tmp_path)
    result = wipe_all_maturation(tmp_path, confirm=True)
    assert result["ok"] is True
    data = load_continuum(tmp_path)
    assert data.get("completed_phases") == ["genesis"]
    assert not files["progress"].exists()
    assert not files["fitness"].exists()
    assert not files["ticks"].exists()
    assert not files["split"].exists()
    assert not files["live_zip"].exists()
    assert files["setup"].is_file()
    assert files["charter"].is_file()
    assert files["bible"].is_file()
    assert files["configured"].is_file()
    assert files["config"].is_file()


@pytest.mark.unit
def test_maturity_service_clears_last_result_on_wipe(tmp_path: Path) -> None:
    from lumina_core.maturity.maturity_service import MaturityService

    _seed_workspace(tmp_path)
    svc = MaturityService(tmp_path)
    svc._last_result = {"ok": False, "error": "stale"}  # type: ignore[attr-defined]
    svc._error = "stale"  # type: ignore[attr-defined]
    result = svc.wipe_phase("awakening", confirm=True)
    assert result["ok"] is True
    assert svc._last_result is None  # type: ignore[attr-defined]
    assert svc._error is None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_named_wipes_require_confirm(tmp_path: Path) -> None:
    _seed_workspace(tmp_path)
    assert wipe_phase(tmp_path, "awakening", confirm=False)["ok"] is False
    assert wipe_phase(tmp_path, "birth", confirm=False)["ok"] is False
    assert wipe_all_maturation(tmp_path, confirm=False)["ok"] is False
    assert (tmp_path / "state" / "lumina_birth_completed.flag").is_file()
    assert (tmp_path / "reports" / "birth_cloud_run" / "artifacts" / "awakening_live_pi_star.zip").is_file()
