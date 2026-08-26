"""Birth endpoint action handlers (global residual)."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import HTTPException, Query

from lumina_launcher.services.birth_service import birth_service
from lumina_os.backend.birth_endpoints_enrich import (
    _enrich_status,
    _invalidate_enrich_artifact_cache,
    _merge_start_result,
)

logger = logging.getLogger(__name__)

async def start_birth(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
    force: bool = Query(False),
    practice_mode: bool = Query(False),
    explicit_user_start: bool = Query(True),
    continue_training: bool = Query(False),
    reuse_data: bool = Query(False),
) -> dict[str, Any]:
    # Fail-closed: live host + recent dual-plane proof (never paper cert alone).
    # Exception: reuse_data + certified tick-cache — AMBER must not block history restart.
    skip_live_fabric = False
    if reuse_data is True:
        try:
            from lumina_core.birth.tick_cache_persist import certified_tick_cache_present

            skip_live_fabric = certified_tick_cache_present(birth_service.workspace_root)
        except Exception:
            skip_live_fabric = False
    if not skip_live_fabric:
        try:
            from lumina_launcher.services.fabric_link_health import build_fabric_link_health

            live: dict = {}
            try:
                from lumina_core.broker.ninjatrader.fabric_link_supervisor import (
                    get_fabric_link_supervisor,
                )

                live = get_fabric_link_supervisor().status().to_dict()
            except Exception:
                live = {}
            health = build_fabric_link_health(
                workspace_root=birth_service.workspace_root,
                live=live,
            )
            if not health.get("gate_birth_ok"):
                reason = str(health.get("gate_reason") or "FABRIC_LINK_NOT_GREEN")
                level = str(health.get("level") or "RED")
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": reason,
                        "message": (
                            "Connecting to NinjaTrader Fabric is not ready for Birth "
                            f"({reason}, live={level}). "
                            "Start NinjaTrader (datafeed Connected), open New → LUMINA, "
                            "then Setup → Test connection until live host is up and "
                            "diagnostic is GREEN before Birth."
                        ),
                        "level": level,
                        "meaning": str(health.get("meaning") or ""),
                    },
                )
        except HTTPException:
            raise
        except Exception:
            # If health subsystem fails open would be unsafe — block.
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "FABRIC_LINK_NOT_GREEN",
                    "message": "Fabric link health unavailable — run Operator Vault diagnostic.",
                },
            ) from None

    # ADR-0037: Twin base curriculum is a foundation block (Operator Vault).
    # Without birth_ready the organism has no operator judgment DNA — fail-closed.
    try:
        from lumina_core.evolution.twin_base_training import is_twin_birth_ready

        if not is_twin_birth_ready():
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "TWIN_BASE_TRAINING_INCOMPLETE",
                    "message": (
                        "Twin base training is not complete. "
                        "Open Operator Vault → Twin and finish the base curriculum "
                        "(~10–12 min forced-choice) before Birth can start."
                    ),
                },
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TWIN_BASE_TRAINING_INCOMPLETE",
                "message": (
                    "Twin birth-ready flag unavailable — complete Operator Vault → Twin base training."
                ),
            },
        ) from None

    # History preflight is sync inside start_birth (fail before promise).
    # Offload the whole start path so the event loop stays responsive.
    return await asyncio.to_thread(
        birth_service.start_birth,
        target_trades=target_trades,
        force=force,
        practice_mode=practice_mode,
        explicit_user_start=explicit_user_start,
        continue_training=continue_training,
        reuse_data=reuse_data,
    )

async def stop_birth() -> dict[str, Any]:
    return await asyncio.to_thread(birth_service.stop_birth)

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

async def extra_training() -> dict[str, Any]:
    """Clear birth completion artifacts so operator can run extra training."""
    from lumina_launcher.core.first_boot import FirstBootManager

    root = birth_service.workspace_root
    FirstBootManager(root).clear_completion_artifacts_for_extra_training()
    return {"ok": True, "message": "Completion artifacts cleared — start birth with continue_training"}

async def retry_birth(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
    wipe: bool = Query(False),
) -> dict[str, Any]:
    """Resume certified birth on certificate failure; wipe=True starts completely fresh."""
    result = birth_service.retry_birth(target_trades=target_trades, wipe=wipe)
    return _enrich_status(_merge_start_result(result))

async def resume_stalled_stage(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
) -> dict[str, Any]:
    """Resume curriculum from stage_stalled without wiping checkpoint."""
    result = birth_service.resume_stalled_stage(target_trades=target_trades)
    return _enrich_status(_merge_start_result(result))

async def expand_and_retry_stalled_stage(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
) -> dict[str, Any]:
    """Expand data window and resume stalled stage (checkpoint preserved)."""
    result = birth_service.expand_and_retry_stalled_stage(target_trades=target_trades)
    return _enrich_status(_merge_start_result(result))

async def autonomous_recovery(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
) -> dict[str, Any]:
    """Execute organism autonomy recovery policy without operator input."""
    result = birth_service.execute_autonomous_recovery(target_trades=target_trades)
    return _enrich_status(_merge_start_result(result))

async def resume_birth(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
) -> dict[str, Any]:
    """Continue learning from the last checkpoint (continue_training + reuse_data)."""
    result = birth_service.resume_birth(target_trades=target_trades)
    return _enrich_status(_merge_start_result(result))

async def accept_champion(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
) -> dict[str, Any]:
    """Accept frozen champion after swarm no-lift and continue curriculum."""
    result = birth_service.accept_champion_birth(target_trades=target_trades)
    return _enrich_status(_merge_start_result(result))

async def reuse_data_birth(
    target_trades: int | None = Query(None, ge=1000, le=5_000_000),
) -> dict[str, Any]:
    """Resume from checkpoint and reuse cached data manifest when hash matches."""
    result = birth_service.reuse_data_birth(target_trades=target_trades)
    return _enrich_status(_merge_start_result(result))
