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

    # Preflight loads ApplicationContainer + historical OHLC; never block the event loop.
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
    """Continue learning from certificate failure (alias for retry without wipe)."""
    result = birth_service.retry_birth(target_trades=target_trades, wipe=False)
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
