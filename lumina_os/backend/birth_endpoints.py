"""FastAPI Birth Phase endpoints — start and poll LuminaBirthEngine via BirthService."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from lumina_launcher.services.birth_service import birth_service
from lumina_core.birth.birth_certificate import load_certificate, validate_certificate_artifacts
from lumina_core.birth.config import load_birth_v2_config

router = APIRouter(prefix="/api/birth", tags=["birth"])
logger = logging.getLogger(__name__)

from lumina_os.backend.birth_endpoints_enrich import (  # noqa: E402
    _build_birth_status_payload,
)

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












@router.get("/status")
async def get_birth_status() -> dict[str, Any]:
    return await asyncio.to_thread(_build_birth_status_payload)


@router.get("/recovery-status")
async def get_birth_recovery_status() -> dict[str, Any]:
    """H6 recovery ladder + C2 organism autonomy posture (phoenix budget / notify-as-exception)."""
    from lumina_core.birth.config import load_birth_v2_config
    from lumina_core.birth.organism_autonomy import (
        OrganismAutonomyState,
        organism_autonomy_status,
    )
    from lumina_core.birth.recovery_compress import recovery_from_progress

    def _build() -> dict[str, Any]:
        status = _build_birth_status_payload()
        progress = status.get("progress") if isinstance(status, dict) else None
        if not isinstance(progress, dict):
            progress = {}
        recovery = progress.get("recovery")
        if not isinstance(recovery, dict) or recovery.get("schema") != "recovery_compress_v1":
            recovery = recovery_from_progress(progress)
        autonomy_block: dict[str, Any] = {}
        try:
            root = birth_service.workspace_root
            cfg = load_birth_v2_config(root).curriculum
            metrics = progress.get("autonomy_metrics") or progress.get("organism_autonomy")
            state = OrganismAutonomyState.from_metrics(
                metrics if isinstance(metrics, dict) else None
            )
            autonomy_block = organism_autonomy_status(cfg, state)
        except Exception:
            autonomy_block = {"error": "organism_autonomy_status_unavailable"}
        return {
            "schema": "birth_recovery_status_v1",
            "status": status.get("status") if isinstance(status, dict) else None,
            "live": status.get("live") if isinstance(status, dict) else None,
            "recovery": recovery,
            "organism_autonomy": autonomy_block,
            "local_only": True,
        }

    return await asyncio.to_thread(_build)


@router.get("/perfect-birth-status")
async def get_perfect_birth_status() -> dict[str, Any]:
    """Perfect Birth KPI gaps, unlock state, and Phase 2 shadow profile suggestion."""
    from lumina_core.birth.perfect_birth_gate import (
        PerfectBirthThresholds,
        perfect_birth_status,
    )

    root = birth_service.workspace_root
    thr = PerfectBirthThresholds()
    try:
        thr = PerfectBirthThresholds.from_curriculum_cfg(
            load_birth_v2_config(root).curriculum
        )
    except Exception:
        pass
    return await asyncio.to_thread(perfect_birth_status, root, thresholds=thr)


@router.get("/phase2-status")
async def get_phase2_status() -> dict[str, Any]:
    """Phase 2 features + metrics + H3 SIM campaign status."""
    from lumina_core.birth.phase2_autonomy import (
        phase2_status_payload,
        resolve_features_with_campaign,
    )

    root = birth_service.workspace_root
    cfg = load_birth_v2_config(root).curriculum
    features = resolve_features_with_campaign(cfg, root)
    return await asyncio.to_thread(
        phase2_status_payload,
        window_hours=24,
        recent_limit=8,
        features=features,
        workspace_root=root,
    )


class Phase2CampaignRequest(BaseModel):
    confirm: bool = Field(default=False, description="Operator confirms campaign action")
    allow_sim_scaffold: bool = Field(
        default=False,
        description="Lab only: enable without Perfect Birth evidence",
    )


@router.post("/phase2-enable-shadow")
async def post_phase2_enable_shadow(body: Phase2CampaignRequest) -> dict[str, Any]:
    """Enable productive Phase 2 SIM shadow campaign after Perfect Birth unlock."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="confirm=true required")
    from lumina_core.birth.phase2_autonomy import enable_sim_shadow_campaign

    root = birth_service.workspace_root
    result = await asyncio.to_thread(
        enable_sim_shadow_campaign,
        root,
        allow_sim_scaffold=bool(body.allow_sim_scaffold),
        source="api",
    )
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/phase2-promote-sim-apply")
async def post_phase2_promote_sim_apply(body: Phase2CampaignRequest) -> dict[str, Any]:
    """Promote SIM campaign shadow→apply after shadow evidence (never REAL)."""
    if not body.confirm:
        raise HTTPException(status_code=400, detail="confirm=true required")
    from lumina_core.birth.phase2_autonomy import promote_sim_apply_campaign

    root = birth_service.workspace_root
    result = await asyncio.to_thread(promote_sim_apply_campaign, root)
    if not result.get("ok"):
        raise HTTPException(status_code=422, detail=result)
    return result


@router.post("/phase2-disable-campaign")
async def post_phase2_disable_campaign(body: Phase2CampaignRequest) -> dict[str, Any]:
    if not body.confirm:
        raise HTTPException(status_code=400, detail="confirm=true required")
    from lumina_core.birth.phase2_autonomy import disable_sim_campaign

    root = birth_service.workspace_root
    return await asyncio.to_thread(disable_sim_campaign, root)


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

from lumina_os.backend.birth_endpoints_actions import (  # noqa: E402
    accept_champion,
    autonomous_recovery,
    expand_and_retry_stalled_stage,
    extra_training,
    resume_birth,
    resume_stalled_stage,
    retry_birth,
    reuse_data_birth,
    start_birth,
    stop_birth,
    wipe_all_birth_data,
)

# Re-bind FastAPI routes onto extracted action handlers.
start_birth = router.post("/start")(start_birth)
stop_birth = router.post("/stop")(stop_birth)
wipe_all_birth_data = router.post("/wipe-all")(wipe_all_birth_data)
extra_training = router.post("/extra-training")(extra_training)
retry_birth = router.post("/retry")(retry_birth)
resume_stalled_stage = router.post("/resume-stage")(resume_stalled_stage)
expand_and_retry_stalled_stage = router.post("/expand-and-retry")(expand_and_retry_stalled_stage)
autonomous_recovery = router.post("/autonomous-recovery")(autonomous_recovery)
resume_birth = router.post("/resume")(resume_birth)
accept_champion = router.post("/accept-champion")(accept_champion)
reuse_data_birth = router.post("/reuse-data")(reuse_data_birth)
