"""Operator attention notification API (ADR-0028)."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


class AttentionReportRequest(BaseModel):
    reason_code: Literal[
        "real_safe_mode",
        "real_trading_blocked",
        "backend_unreachable",
        "setup_incomplete",
    ] = Field(description="Attention reason code")
    detail: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


@router.post("/attention")
async def post_attention_report(body: AttentionReportRequest) -> dict[str, Any]:
    """Accept client-reported attention events (e.g. REAL safe mode)."""
    from lumina_core.notifications.attention_events import (
        backend_unreachable_event,
        real_safe_mode_event,
        real_trading_blocked_event,
        setup_incomplete_event,
    )
    from lumina_core.notifications.operator_notifier import notify_problem
    from lumina_launcher.services.birth_service import birth_service

    detail = str(body.detail or "").strip()
    ctx = body.context if isinstance(body.context, dict) else {}
    event = None
    if body.reason_code == "real_safe_mode":
        event = real_safe_mode_event(detail=detail)
    elif body.reason_code == "real_trading_blocked":
        blockers = ctx.get("blockers")
        block_list = [str(x) for x in blockers if x] if isinstance(blockers, list) else []
        if not block_list and detail:
            block_list = [detail]
        event = real_trading_blocked_event(blockers=block_list, source=str(ctx.get("source", "client")))
    elif body.reason_code == "backend_unreachable":
        event = backend_unreachable_event(detail=detail)
    elif body.reason_code == "setup_incomplete":
        event = setup_incomplete_event(detail=detail)

    if event is None:
        return {"ok": False, "sent": False, "reason": "unknown_reason_code"}

    sent = notify_problem(event, workspace_root=birth_service.workspace_root)
    return {"ok": True, "sent": bool(sent), "reason_code": body.reason_code}
