"""Wipe single maturation phase or all post-genesis progress (fail-closed)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger
from lumina_core.maturity.continuum import (
    load_continuum,
    save_continuum,
    wipe_all_continuum,
    wipe_phase_record,
)
from lumina_core.maturity.maturation_progress import (
    MaturationPhase,
    load_maturation_progress,
    resolve_current_phase,
    save_maturation_progress,
)

logger = get_logger("lumina.maturity.wipe")

# Milestones owned primarily by each phase (best-effort scrub).
_PHASE_MILESTONES: dict[str, tuple[str, ...]] = {
    MaturationPhase.BIRTH.value: (
        "birth_started",
        "birth_certificate_issued",
        "curriculum_stage1_trend_passed",
        "curriculum_stage2_range_passed",
        "curriculum_stage3_mixed_passed",
        "curriculum_stage4_viable_passed",
        "curriculum_stage5_probe_passed",
        "curriculum_stage4_polish_passed",
    ),
    MaturationPhase.AWAKENING.value: (
        "evolution_proof_passed",
        "perfect_birth_autonomy_proven",
    ),
    MaturationPhase.PLAYGROUND.value: (
        "deck_unlocked",
        "first_sim_order_placed",
        "sim_mirror_api_ok",
    ),
    MaturationPhase.APPRENTICESHIP.value: ("sim_real_guard_stable",),
    MaturationPhase.PROVING_GROUND.value: (
        "shadow_validation_passed",
        "promotion_gate_passed",
    ),
    MaturationPhase.REAL.value: ("human_real_approval", "real_trading_live"),
}

_LATER_THAN_AWAKENING: tuple[str, ...] = (
    MaturationPhase.PLAYGROUND.value,
    MaturationPhase.APPRENTICESHIP.value,
    MaturationPhase.PROVING_GROUND.value,
    MaturationPhase.REAL.value,
)
_LATER_THAN_BIRTH: tuple[str, ...] = (MaturationPhase.AWAKENING.value, *_LATER_THAN_AWAKENING)
_LATER_THAN_PLAYGROUND: tuple[str, ...] = (
    MaturationPhase.APPRENTICESHIP.value,
    MaturationPhase.PROVING_GROUND.value,
    MaturationPhase.REAL.value,
)

# Generated Awakening output — never frozen birth_exit_pi_star.*.
_AWAKENING_STATE_TARGETS: tuple[str, ...] = (
    "state/lumina_evolution_proof.json",
    "state/lumina_awakening_progress.json",
    "state/awakening_twin_watch.jsonl",
    "state/perfect_birth_complete.flag",
    "state/perfect_birth_complete.json",
    "state/perfect_birth_last_attempt.json",
)

_PLAYGROUND_STATE_TARGETS: tuple[str, ...] = (
    "state/lumina_playground_progress.json",
    "state/lumina_playground_tape.jsonl",
    "state/first_sim_order.json",
)

_APPRENTICESHIP_STATE_TARGETS: tuple[str, ...] = (
    "state/lumina_apprenticeship_progress.json",
    "state/lumina_apprenticeship_tape.jsonl",
    "state/lumina_apprenticeship_days.jsonl",
)

_PROVING_GROUND_STATE_TARGETS: tuple[str, ...] = (
    "state/lumina_proving_ground_progress.json",
    "state/lumina_proving_ground_tape.jsonl",
)

_LATER_THAN_APPRENTICESHIP: tuple[str, ...] = (
    MaturationPhase.PROVING_GROUND.value,
    MaturationPhase.REAL.value,
)
_LATER_THAN_PROVING_GROUND: tuple[str, ...] = (MaturationPhase.REAL.value,)


def _unlink(path: Path, root: Path) -> str | None:
    if not path.exists():
        return None
    try:
        if path.is_dir():
            import shutil

            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        try:
            return str(path.relative_to(root))
        except ValueError:
            return str(path)
    except OSError:
        logger.warning("maturity.wipe.unlink_failed path=%s", path, exc_info=True)
        return None


def wipe_awakening_generated(workspace_root: Path | str) -> list[str]:
    """Delete generated Awakening shot/proof files. Frozen π* and Birth plant stay."""
    root = Path(workspace_root)
    removed: list[str] = []
    live_paths: list[Path] = []
    try:
        from lumina_core.maturity.phase_runners.awakening_shot import (
            CHILD_META_NAME,
            artifacts_dir,
            live_child_zip,
            live_ledger_path,
        )

        live_paths = [
            live_child_zip(root),
            artifacts_dir(root) / CHILD_META_NAME,
            live_ledger_path(root),
        ]
    except Exception:
        art = root / "reports" / "birth_cloud_run" / "artifacts"
        live_paths = [
            art / "awakening_live_pi_star.zip",
            art / "awakening_live_pi_star.json",
            art / "awakening_live_holdout.jsonl",
        ]
    for path in live_paths:
        rel = _unlink(path, root)
        if rel:
            removed.append(rel)
    for relative in _AWAKENING_STATE_TARGETS:
        rel = _unlink(root / relative, root)
        if rel:
            removed.append(rel)
    removed.extend(wipe_playground_generated(root))
    return removed


def wipe_playground_generated(workspace_root: Path | str) -> list[str]:
    """Delete Playground tape/progress. Birth, Awakening, and frozen π* stay."""
    root = Path(workspace_root)
    removed: list[str] = []
    for relative in _PLAYGROUND_STATE_TARGETS:
        rel = _unlink(root / relative, root)
        if rel:
            removed.append(rel)
    removed.extend(wipe_apprenticeship_generated(root))
    return removed


def wipe_apprenticeship_generated(workspace_root: Path | str) -> list[str]:
    """Delete Apprenticeship tape/progress. Playground and earlier stay."""
    root = Path(workspace_root)
    removed: list[str] = []
    for relative in _APPRENTICESHIP_STATE_TARGETS:
        rel = _unlink(root / relative, root)
        if rel:
            removed.append(rel)
    removed.extend(wipe_proving_ground_generated(root))
    return removed


def wipe_proving_ground_generated(workspace_root: Path | str) -> list[str]:
    """Delete Proving Ground tape/progress. Apprenticeship and earlier stay."""
    root = Path(workspace_root)
    removed: list[str] = []
    for relative in _PROVING_GROUND_STATE_TARGETS:
        rel = _unlink(root / relative, root)
        if rel:
            removed.append(rel)
    return removed


def _clear_birth_keep_setup(
    root: Path,
    *,
    preserve_tick_cache: bool,
) -> dict[str, Any]:
    from lumina_launcher.core.birth_reset import clear_birth_training_state

    result = clear_birth_training_state(
        root,
        wipe_genesis=False,
        preserve_tick_cache=preserve_tick_cache,
    )
    return {
        "status": "wiped" if result.success else "error",
        "message": result.message,
        "removed": list(result.removed),
        "preserved": list(result.preserved),
    }


def _scrub_milestones(root: Path, drop: set[str]) -> None:
    progress = load_maturation_progress(root)
    progress.milestones_reached = [m for m in progress.milestones_reached if m not in drop]
    for mid in drop:
        progress.metadata.pop(mid, None)
    progress.current_phase = resolve_current_phase(progress)
    save_maturation_progress(root, progress)


def _cascade_later(root: Path, later: tuple[str, ...], drop: set[str]) -> None:
    for phase in later:
        drop.update(_PHASE_MILESTONES.get(phase, ()))
        wipe_phase_record(root, phase)


def _force_genesis_only(root: Path) -> dict[str, Any]:
    continuum = load_continuum(root)
    genesis = MaturationPhase.GENESIS.value
    continuum["completed_phases"] = [genesis]
    continuum["active_phase"] = None
    records = continuum.get("phase_records")
    if not isinstance(records, dict):
        records = {}
        continuum["phase_records"] = records
    genesis_rec = records.get(genesis)
    if not isinstance(genesis_rec, dict) or genesis_rec.get("status") != "completed":
        records[genesis] = {
            "status": "completed",
            "learned": {"note": "Setup retained after maturation wipe"},
            "exit_proofs": ["setup_complete"],
        }
    continuum["pending_advance"] = None
    save_continuum(root, continuum)
    return continuum


def wipe_phase(workspace_root: Path | str, phase: str, *, confirm: bool) -> dict[str, Any]:
    if not confirm:
        return {"ok": False, "error": "confirm=true required"}
    root = Path(workspace_root)
    phase = str(phase or "").strip().lower()
    if phase not in _PHASE_MILESTONES and phase != MaturationPhase.GENESIS.value:
        return {"ok": False, "error": f"unknown phase: {phase}"}

    removed: list[str] = []
    drop = set(_PHASE_MILESTONES.get(phase, ()))

    if phase == MaturationPhase.AWAKENING.value:
        removed.extend(wipe_awakening_generated(root))
        _cascade_later(root, _LATER_THAN_AWAKENING, drop)
    elif phase == MaturationPhase.PLAYGROUND.value:
        removed.extend(wipe_playground_generated(root))
        _cascade_later(root, _LATER_THAN_PLAYGROUND, drop)
    elif phase == MaturationPhase.APPRENTICESHIP.value:
        removed.extend(wipe_apprenticeship_generated(root))
        _cascade_later(root, _LATER_THAN_APPRENTICESHIP, drop)
    elif phase == MaturationPhase.PROVING_GROUND.value:
        removed.extend(wipe_proving_ground_generated(root))
        _cascade_later(root, _LATER_THAN_PROVING_GROUND, drop)
    elif phase == MaturationPhase.BIRTH.value:
        try:
            result = _clear_birth_keep_setup(root, preserve_tick_cache=True)
            removed.append(f"birth_wipe:{result.get('status')}")
            removed.extend(str(p) for p in (result.get("removed") or []) if p)
        except Exception as exc:
            logger.warning("maturity.wipe.birth_failed: %s", exc)
            return {"ok": False, "error": f"birth_wipe_failed:{exc}", "phase": phase}
        removed.extend(wipe_awakening_generated(root))
        _cascade_later(root, _LATER_THAN_BIRTH, drop)

    _scrub_milestones(root, drop)
    continuum = wipe_phase_record(root, phase)
    if phase == MaturationPhase.BIRTH.value:
        continuum = _force_genesis_only(root)

    logger.info("maturity.wipe_phase phase=%s removed_milestones=%s", phase, sorted(drop))
    return {
        "ok": True,
        "phase": phase,
        "removed_milestones": sorted(drop),
        "continuum": continuum,
        "details": removed,
    }


def wipe_all_maturation(workspace_root: Path | str, *, confirm: bool) -> dict[str, Any]:
    if not confirm:
        return {"ok": False, "error": "confirm=true required"}
    root = Path(workspace_root)
    birth_result: dict[str, Any] = {}
    try:
        birth_result = _clear_birth_keep_setup(root, preserve_tick_cache=False)
    except Exception as exc:
        birth_result = {"error": str(exc)}
        logger.warning("maturity.wipe_all.birth_failed: %s", exc)
        return {"ok": False, "error": f"birth_wipe_failed:{exc}", "birth": birth_result}

    awakening_removed = wipe_awakening_generated(root)
    progress = load_maturation_progress(root)
    progress.milestones_reached = []
    progress.metadata = {}
    progress.current_phase = MaturationPhase.GENESIS
    save_maturation_progress(root, progress)

    continuum = wipe_all_continuum(root)
    logger.info("maturity.wipe_all ok")
    return {
        "ok": True,
        "birth": birth_result,
        "awakening_removed": awakening_removed,
        "continuum": continuum,
    }
