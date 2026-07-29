"""FastAPI Birth Phase endpoints — start and poll LuminaBirthEngine via BirthService."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from lumina_launcher.services.birth_service import birth_service
from lumina_launcher.services.birth_status_diagnostics import merge_certificate_diagnostics
from lumina_core.birth.birth_certificate import load_certificate, validate_certificate_artifacts
from lumina_core.birth.checkpoint import load_checkpoint_state
from lumina_core.birth.config import load_birth_v2_config, BRO_ENGINE_VERSION
from lumina_core.birth.remediation import should_fast_path_remediation_from_state

router = APIRouter(prefix="/api/birth", tags=["birth"])
logger = logging.getLogger(__name__)

_ENRICH_ARTIFACT_CACHE_TTL_SEC = 20.0
_ENRICH_ARTIFACT_CACHE: tuple[float, dict[str, Any]] | None = None
_ENRICH_ARTIFACT_LOCK = Lock()
_ACTIVE_BIRTH_POLL_PHASES = frozenset(
    {
        "loading_history",
        "loading_history_failed",
        "enriching_news",
        "enriching_regimes",
        "train_holdout_split",
        "holdout_preflight",
        "holdout_preflight_expansion",
        "policy_init",
        "ticks_ready",
        "curriculum_stage",
        "curriculum_learning",
        "curriculum_research",
        "ppo_training",
        "parallel_simulation",
    }
)
_ENRICH_ARTIFACT_KEYS = (
    "artifacts_ok",
    "certificate_ok",
    "certificate_reason",
    "evolution_proof_ok",
    "real_trading_eligible",
    "certificate",
    "artifacts_label",
    "fast_path_eligible",
    "checkpoint_phase",
    "checkpoint_quality_score",
    "checkpoint_resumable",
    "checkpoint_ppo_steps",
    "checkpoint_cumulative_trades",
    "checkpoint_stage_trades",
)


def _is_active_birth_poll(payload: dict[str, Any]) -> bool:
    status = str(payload.get("status", "") or "").strip().lower()
    if status == "running":
        return True
    progress = payload.get("progress")
    if not isinstance(progress, dict):
        return False
    stage = str(progress.get("stage", "") or "").strip().lower()
    phase = str(progress.get("phase", "") or "").strip().lower()
    if stage == "loading_data":
        return True
    return phase in _ACTIVE_BIRTH_POLL_PHASES


def _apply_progress_fields(payload: dict[str, Any], *, checkpoint: dict[str, Any] | None = None) -> str:
    progress = payload.get("progress")
    progress_phase = ""
    if isinstance(progress, dict):
        progress_phase = str(progress.get("phase", "") or "").strip().lower()
        diag = merge_certificate_diagnostics(progress, checkpoint)
        payload["curriculum_stage"] = progress.get("curriculum_stage")
        payload["oos_metrics"] = diag.get("oos_metrics") or progress.get("oos_metrics")
        payload["failure_reasons"] = diag.get("failure_reasons") or (
            (progress.get("oos_metrics") or {}).get("failure_reasons")
            if isinstance(progress.get("oos_metrics"), dict)
            else None
        )
        payload["runway_phase"] = diag.get("runway_phase") or progress.get("runway_phase")
        payload["birth_exit_winrate"] = diag.get("birth_exit_winrate")
        if isinstance(progress, dict) and diag.get("oos_metrics"):
            merged_progress = dict(progress)
            merged_progress["oos_metrics"] = diag["oos_metrics"]
            if diag.get("failure_reasons"):
                merged_progress.setdefault("failure_reasons", diag["failure_reasons"])
            payload["progress"] = merged_progress
        payload["quality_score"] = progress.get("quality_score")
        payload["remediation_attempt"] = progress.get("remediation_attempt")
        payload["remediation_max"] = progress.get("remediation_max")
        payload["data_manifest"] = progress.get("data_manifest")
    return progress_phase


def _enrich_status_full(payload: dict[str, Any]) -> dict[str, Any]:
    """Attach SSOT artifact readiness (Birth Certificate v2 + policy zip)."""
    root = birth_service.workspace_root
    thresholds = load_birth_v2_config(root).certificate_thresholds
    cert_ok, cert_reason, cert = validate_certificate_artifacts(root, thresholds=thresholds)
    ckpt = load_checkpoint_state(root)
    progress_phase = _apply_progress_fields(payload, checkpoint=ckpt if isinstance(ckpt, dict) else None)
    resumable = birth_service.checkpoint_resumable()
    payload["checkpoint_resumable"] = resumable
    if resumable and ckpt:
        if payload.get("quality_score") in (None, 0, 0.0):
            payload["quality_score"] = ckpt.get("quality_score")
        if not payload.get("data_manifest"):
            payload["data_manifest"] = ckpt.get("data_manifest")
        payload.setdefault("checkpoint_phase", ckpt.get("phase"))
        payload.setdefault("checkpoint_quality_score", ckpt.get("quality_score"))
        payload["checkpoint_ppo_steps"] = int(ckpt.get("ppo_steps", 0) or 0)
        payload["checkpoint_cumulative_trades"] = int(ckpt.get("cumulative_trades", 0) or 0)
        payload["curriculum_stage"] = ckpt.get("curriculum_stage") or payload.get("curriculum_stage")
        stage_metrics = ckpt.get("stage_metrics")
        if isinstance(stage_metrics, dict):
            payload["checkpoint_stage_trades"] = int(stage_metrics.get("stage_trades", 0) or 0)
    elif isinstance(ckpt, dict) and ckpt:
        if payload.get("quality_score") in (None, 0, 0.0):
            payload["quality_score"] = ckpt.get("quality_score")
        if not payload.get("data_manifest"):
            payload["data_manifest"] = ckpt.get("data_manifest")
        payload.setdefault("checkpoint_phase", ckpt.get("phase"))
        payload.setdefault("checkpoint_quality_score", ckpt.get("quality_score"))
    if progress_phase in {"certificate_failed", "certificate_remediation"}:
        failure_reasons = payload.get("failure_reasons")
        if isinstance(failure_reasons, list) and failure_reasons:
            cert_reason = "; ".join(str(item) for item in failure_reasons)
    payload["artifacts_ok"] = birth_service.artifacts_ok()
    payload["certificate_ok"] = cert_ok
    payload["certificate_reason"] = cert_reason
    payload["evolution_proof_ok"] = birth_service.evolution_proof_ok()
    payload["real_trading_eligible"] = birth_service.real_trading_eligible()
    payload["certificate"] = cert.model_dump(mode="json") if cert is not None else None
    payload["artifacts_label"] = (
        "Birth Certificate v2 OK" if payload["artifacts_ok"] else "Certificate or policy missing"
    )
    payload["phase_label"] = "Birth Phase v2"
    payload["engine_version"] = BRO_ENGINE_VERSION
    progress_for_fast_path = payload.get("progress") if isinstance(payload.get("progress"), dict) else {}
    payload["fast_path_eligible"] = should_fast_path_remediation_from_state(
        progress_for_fast_path,
        ckpt if isinstance(ckpt, dict) else {},
    )
    from lumina_launcher.services.birth_maturity_wiring import maturity_status_fields

    payload.update(maturity_status_fields(root))
    return payload


def _enrich_status(payload: dict[str, Any]) -> dict[str, Any]:
    if not _is_active_birth_poll(payload):
        return _enrich_status_full(payload)

    global _ENRICH_ARTIFACT_CACHE
    now = time.time()
    ckpt = load_checkpoint_state(birth_service.workspace_root)
    progress_phase = _apply_progress_fields(
        payload,
        checkpoint=ckpt if isinstance(ckpt, dict) else None,
    )
    if isinstance(ckpt, dict):
        if payload.get("quality_score") in (None, 0, 0.0):
            payload["quality_score"] = ckpt.get("quality_score")
        if not payload.get("data_manifest"):
            payload["data_manifest"] = ckpt.get("data_manifest")

    with _ENRICH_ARTIFACT_LOCK:
        cached = _ENRICH_ARTIFACT_CACHE
    if cached is not None:
        cached_at, artifact_fields = cached
        if (now - cached_at) < _ENRICH_ARTIFACT_CACHE_TTL_SEC:
            payload.update(artifact_fields)
            payload["phase_label"] = "Birth Phase v2"
            payload["engine_version"] = BRO_ENGINE_VERSION
            if progress_phase in {"certificate_failed", "certificate_remediation"}:
                failure_reasons = payload.get("failure_reasons")
                if isinstance(failure_reasons, list) and failure_reasons:
                    payload["certificate_reason"] = "; ".join(str(item) for item in failure_reasons)
            return payload

    enriched = _enrich_status_full(payload)
    artifact_fields = {key: enriched[key] for key in _ENRICH_ARTIFACT_KEYS if key in enriched}
    with _ENRICH_ARTIFACT_LOCK:
        _ENRICH_ARTIFACT_CACHE = (now, artifact_fields)
    return enriched


def _build_birth_status_payload() -> dict[str, Any]:
    return _enrich_status(birth_service.get_status())


@router.post("/start")
async def start_birth(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
    force: bool = Query(False),
    practice_mode: bool = Query(False),
    explicit_user_start: bool = Query(True),
    continue_training: bool = Query(False),
    reuse_data: bool = Query(False),
) -> dict[str, Any]:
    # Fail-closed: Fabric link must be GREEN before Birth / Genesis training.
    try:
        from lumina_launcher.services.fabric_link_certificate import is_fabric_link_green

        ok, reason = is_fabric_link_green(workspace_root=birth_service.workspace_root)
        if not ok:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": reason or "FABRIC_LINK_NOT_GREEN",
                    "message": (
                        "Fabric diagnostic must be GREEN before Birth. "
                        "Open Setup & connection → Run fabric diagnostic."
                    ),
                },
            )
    except HTTPException:
        raise
    except Exception:
        # If certificate subsystem fails open would be unsafe — block.
        raise HTTPException(
            status_code=403,
            detail={
                "code": "FABRIC_LINK_NOT_GREEN",
                "message": "Fabric link certificate unavailable — run Operator Vault diagnostic.",
            },
        ) from None

    return birth_service.start_birth(
        target_trades=target_trades,
        force=force,
        practice_mode=practice_mode,
        explicit_user_start=explicit_user_start,
        continue_training=continue_training,
        reuse_data=reuse_data,
    )


@router.post("/stop")
async def stop_birth() -> dict[str, Any]:
    return birth_service.stop_birth()


def _invalidate_enrich_artifact_cache() -> None:
    global _ENRICH_ARTIFACT_CACHE
    with _ENRICH_ARTIFACT_LOCK:
        _ENRICH_ARTIFACT_CACHE = None


@router.post("/wipe-all")
async def wipe_all_birth_data(
    confirm: bool = Query(False),
    preserve_tick_cache: bool = Query(False),
) -> dict[str, Any]:
    """Remove birth training artifacts (progress, checkpoint, policies; optional tick cache)."""
    logger.info(
        "birth.wipe_all.request confirm=%s preserve_tick_cache=%s workspace=%s",
        confirm,
        preserve_tick_cache,
        birth_service.workspace_root,
    )
    if not confirm:
        logger.warning("birth.wipe_all.rejected missing_confirm=true")
        raise HTTPException(
            status_code=400,
            detail="Set confirm=true to wipe all birth data",
        )
    result = birth_service.wipe_all_birth_data(preserve_tick_cache=preserve_tick_cache)
    status = str(result.get("status", "") or "")
    removed = result.get("removed_artifacts")
    removed_count = len(removed) if isinstance(removed, list) else 0
    logger.info(
        "birth.wipe_all.result status=%s removed=%s checkpoint_resumable=%s message=%s",
        status,
        removed_count,
        result.get("checkpoint_resumable"),
        result.get("message"),
    )
    _invalidate_enrich_artifact_cache()
    return result


@router.post("/extra-training")
async def extra_training() -> dict[str, Any]:
    """Clear birth completion artifacts so operator can run extra training."""
    from lumina_launcher.core.first_boot import FirstBootManager

    root = birth_service.workspace_root
    FirstBootManager(root).clear_completion_artifacts_for_extra_training()
    return {"ok": True, "message": "Completion artifacts cleared — start birth with continue_training"}


def _merge_start_result(result: dict[str, Any]) -> dict[str, Any]:
    """Keep start acknowledgement when enriching with polled status."""
    payload: dict[str, Any] = dict(result)
    start_status = str(result.get("status", "") or "").strip().lower()
    if start_status not in {"started", "already_running"}:
        return payload
    live = birth_service.get_status()
    payload.update(live)
    payload["status"] = start_status
    payload["start_acknowledged"] = True
    if result.get("message"):
        payload.setdefault("start_message", result.get("message"))
    return payload


@router.post("/retry")
async def retry_birth(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
    wipe: bool = Query(False),
) -> dict[str, Any]:
    """Resume certified birth on certificate failure; wipe=True starts completely fresh."""
    result = birth_service.retry_birth(target_trades=target_trades, wipe=wipe)
    return _enrich_status(_merge_start_result(result))


@router.post("/resume-stage")
async def resume_stalled_stage(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
) -> dict[str, Any]:
    """Resume curriculum from stage_stalled without wiping checkpoint."""
    result = birth_service.resume_stalled_stage(target_trades=target_trades)
    return _enrich_status(_merge_start_result(result))


@router.post("/expand-and-retry")
async def expand_and_retry_stalled_stage(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
) -> dict[str, Any]:
    """Expand data window and resume stalled stage (checkpoint preserved)."""
    result = birth_service.expand_and_retry_stalled_stage(target_trades=target_trades)
    return _enrich_status(_merge_start_result(result))


@router.post("/autonomous-recovery")
async def autonomous_recovery(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
) -> dict[str, Any]:
    """Execute organism autonomy recovery policy without operator input."""
    result = birth_service.execute_autonomous_recovery(target_trades=target_trades)
    return _enrich_status(_merge_start_result(result))


@router.post("/resume")
async def resume_birth(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
) -> dict[str, Any]:
    """Continue learning from certificate failure (alias for retry without wipe)."""
    result = birth_service.retry_birth(target_trades=target_trades, wipe=False)
    return _enrich_status(_merge_start_result(result))


@router.post("/accept-champion")
async def accept_champion(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
) -> dict[str, Any]:
    """Accept frozen champion after swarm no-lift and continue curriculum."""
    result = birth_service.accept_champion_birth(target_trades=target_trades)
    return _enrich_status(_merge_start_result(result))


@router.post("/reuse-data")
async def reuse_data_birth(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
) -> dict[str, Any]:
    """Resume from checkpoint and reuse cached data manifest when hash matches."""
    result = birth_service.reuse_data_birth(target_trades=target_trades)
    return _enrich_status(_merge_start_result(result))


@router.get("/status")
async def get_birth_status() -> dict[str, Any]:
    return await asyncio.to_thread(_build_birth_status_payload)


@router.get("/certificate")
async def get_birth_certificate() -> dict[str, Any]:
    root = birth_service.workspace_root
    cert = load_certificate(root)
    thresholds = load_birth_v2_config(root).certificate_thresholds
    ok, reason, validated = validate_certificate_artifacts(root, thresholds=thresholds)
    return {
        "certificate_ok": ok,
        "certificate_reason": reason,
        "certificate": validated.model_dump(mode="json") if validated is not None else cert.model_dump(mode="json") if cert else None,
        "artifacts_ok": birth_service.artifacts_ok(),
    }


class BirthSettingsRequest(BaseModel):
    training_trades: int = Field(ge=500, le=2_000_000)
    prefer_real_data_only: bool = True
    max_real_days: int = Field(ge=30, le=3650)
    allow_minimal_synthetic_fallback: bool = False
    require_real_simulator_data: bool = True
    stage1_winrate_pass_threshold: float | None = Field(default=None, ge=0.35, le=0.45)


@router.post("/settings")
async def save_birth_settings(body: BirthSettingsRequest) -> dict[str, Any]:
    from lumina_launcher.core.first_boot import FirstBootManager

    root = birth_service.workspace_root
    manager = FirstBootManager(root)
    status = birth_service.get_status()
    if str(status.get("status", "")).lower() in {"running", "active", "started"}:
        raise HTTPException(
            status_code=409,
            detail="Cannot change settings while birth training is active",
        )
    manager.save_full_settings(
        training_trades=body.training_trades,
        prefer_real_data_only=body.prefer_real_data_only,
        max_real_days=body.max_real_days,
        allow_minimal_synthetic_fallback=body.allow_minimal_synthetic_fallback,
        require_real_simulator_data=body.require_real_simulator_data,
        stage1_winrate_pass_threshold=body.stage1_winrate_pass_threshold,
        mark_user_configured=True,
    )
    return {"ok": True, "settings": manager.read_settings()}


@router.post("/adjust-max-days")
async def adjust_max_real_days() -> dict[str, Any]:
    """Raise max_real_days to estimated window (Streamlit 'Pas max days aan' parity)."""
    from lumina_core.first_boot_ui import estimate_first_boot_real_days
    from lumina_launcher.core.first_boot import FirstBootManager

    root = birth_service.workspace_root
    manager = FirstBootManager(root)
    settings = manager.read_settings()
    estimate_days = int(
        estimate_first_boot_real_days(int(settings.get("training_trades", 25000)))
    )
    new_max = max(int(settings.get("max_real_days", 30)), estimate_days)
    manager.save_full_settings(
        training_trades=int(settings.get("training_trades", 25000)),
        prefer_real_data_only=bool(settings.get("prefer_real_data_only", True)),
        max_real_days=new_max,
        allow_minimal_synthetic_fallback=bool(settings.get("allow_minimal_synthetic_fallback", False)),
        require_real_simulator_data=bool(settings.get("require_real_simulator_data", True)),
        mark_user_configured=True,
    )
    return {"ok": True, "max_real_days": new_max, "estimated_days": estimate_days}


@router.get("/logs-tail")
async def get_birth_logs_tail(limit: int = Query(40, ge=5, le=200)) -> dict[str, Any]:
    root = Path(birth_service.workspace_root)
    logs_dir = root / "logs"
    stderr_candidates = sorted(logs_dir.glob("runtime_stderr*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    stderr_tail: list[str] = []
    stderr_path = str(stderr_candidates[0]) if stderr_candidates else ""
    if stderr_path:
        try:
            lines = Path(stderr_path).read_text(encoding="utf-8", errors="replace").splitlines()
            stderr_tail = lines[-limit:]
        except OSError:
            stderr_tail = []
    full_log = logs_dir / "lumina_full_log.csv"
    full_tail: list[str] = []
    if full_log.is_file():
        try:
            full_tail = full_log.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
        except OSError:
            full_tail = []
    return {
        "stderr_path": stderr_path,
        "stderr_tail": stderr_tail,
        "full_log_path": str(full_log),
        "full_log_tail": full_tail,
    }
