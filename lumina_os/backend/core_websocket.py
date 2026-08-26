"""FastAPI WebSocket for LUMINA Core live telemetry.

Endpoint
--------
WS /ws/core/live — pushes aggregated organism telemetry every 500ms.

Sources: state/ JSON files + optional ObservabilityService snapshot.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field


try:
    from api.monitoring import _safe_read_json, resolve_state_directory
except ImportError:  # pragma: no cover

    def resolve_state_directory() -> Path:
        raw = os.environ.get("LUMINA_STATE_DIR", "").strip()
        if raw:
            return Path(raw)
        return Path(__file__).resolve().parents[2] / "state"

    def _safe_read_json(path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            parsed = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}


logger = logging.getLogger(__name__)

router = APIRouter(tags=["core"])

_TELEMETRY_INTERVAL_S = 0.5
_obs_service: Any = None
_operator_mode_override: str | None = None


class OperatorModeRequest(BaseModel):
    mode: Literal["sim", "real"] = Field(description="Operator-selected trading mode")


class OperatorModeResponse(BaseModel):
    ok: bool = True
    mode: str
    blockers: list[str] = Field(default_factory=list)


def set_observability_service(service: Any) -> None:
    """Inject the shared ObservabilityService instance at app startup."""
    global _obs_service
    _obs_service = service


from lumina_os.backend.core_websocket_telemetry import (  # noqa: E402
    CoreLiveTelemetryReader,
    _build_frame,
    _utc_now_iso,
)















def _is_loopback_client(request: Request) -> bool:
    client = request.client
    if client is None:
        return False
    host = (client.host or "").strip().lower()
    return host in {"127.0.0.1", "::1", "localhost", "testclient"} or host.startswith("127.")


@router.get("/api/core/live")
async def get_core_live(
    request: Request,
    x_api_key: str | None = Header(None),
) -> dict[str, Any]:
    """REST snapshot when WebSocket is unavailable.

    Loopback (local Command Deck) remains unauthenticated for operator UX.
    Non-loopback requires API key (ADR-0040 fail-closed observation plane).
    """
    if not _is_loopback_client(request):
        try:
            from backend.app_auth import verify_api_key

            await verify_api_key(x_api_key)
        except HTTPException:
            raise
        except Exception:
            if not x_api_key:
                raise HTTPException(status_code=401, detail="API key required off-localhost")
            raise HTTPException(status_code=401, detail="Invalid API key")
    reader = CoreLiveTelemetryReader()
    payload = reader.build_snapshot(_obs_service)
    return _build_frame(seq=0, payload=payload)


@router.post("/api/core/mode", response_model=OperatorModeResponse)
async def post_core_mode(body: OperatorModeRequest) -> OperatorModeResponse:
    """Accept operator mode selection from the command deck (fail-closed for REAL)."""
    global _operator_mode_override

    if body.mode == "real":
        from lumina_launcher.services.birth_service import birth_service
        from lumina_core.risk.real_multi_gate import real_mode_switch_allowed
        from lumina_core.maturity.milestone_hooks import hook_real_trading_live

        # H2: multi-gate — maturation + explicit human approve-real (Twin cannot substitute)
        eligible, blockers = real_mode_switch_allowed(birth_service.workspace_root)
        if not eligible:
            try:
                from lumina_core.notifications.attention_events import real_trading_blocked_event
                from lumina_core.notifications.operator_notifier import notify_problem

                notify_problem(
                    real_trading_blocked_event(blockers=blockers, source="command_deck"),
                    workspace_root=birth_service.workspace_root,
                )
            except Exception:
                pass
            raise HTTPException(
                status_code=422,
                detail={
                    "message": "REAL blocked by multi-gate (maturation + human approval)",
                    "blockers": blockers,
                    "twin_cannot_bypass": True,
                },
            )
        hook_real_trading_live(birth_service.workspace_root, mode="real")

    _operator_mode_override = body.mode
    logger.info("Operator mode override set to %s", body.mode)
    return OperatorModeResponse(mode=body.mode)


@router.websocket("/ws/core/live")
async def ws_core_live(websocket: WebSocket) -> None:
    await websocket.accept()
    reader = CoreLiveTelemetryReader()
    seq = 0

    try:
        while True:
            payload = reader.build_snapshot(_obs_service)
            await websocket.send_json(_build_frame(seq=seq, payload=payload))
            seq += 1

            try:
                incoming = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=_TELEMETRY_INTERVAL_S,
                )
            except asyncio.TimeoutError:
                continue

            if not incoming:
                continue
            try:
                frame = json.loads(incoming)
            except json.JSONDecodeError:
                continue
            if isinstance(frame, dict) and frame.get("type") == "ping":
                await websocket.send_json({"type": "pong", "ts": _utc_now_iso()})
    except WebSocketDisconnect:
        logger.debug("Core live WebSocket disconnected")
    except Exception:
        logger.exception("Core live WebSocket error")
        raise
