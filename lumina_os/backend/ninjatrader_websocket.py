"""FastAPI WebSocket endpoint for the NinjaTrader 8 add-on bridge."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from lumina_core.broker.ninjatrader.bridge_service import get_ninjatrader_bridge_service
from lumina_core.broker.ninjatrader.schemas import AuthFrame, AuthOkFrame, AuthFailedFrame
from lumina_core.config_loader import ConfigLoader
from lumina_core.security import get_security_module

logger = logging.getLogger(__name__)

router = APIRouter(tags=["ninjatrader"])

_AUTH_TIMEOUT_S = 5.0
_ALLOWED_ROLES = {"ninjatrader_bridge", "admin"}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _resolve_bridge_config() -> tuple[str, str, bool]:
    cfg = ConfigLoader.get()
    broker = cfg.get("broker") if isinstance(cfg.get("broker"), dict) else {}
    nt = broker.get("ninjatrader") if isinstance(broker.get("ninjatrader"), dict) else {}
    account = str(nt.get("account_name", "Sim101") or "Sim101").strip()
    trade_mode = str(cfg.get("mode") or cfg.get("trade_mode") or "sim").strip().lower()
    enabled = bool(nt.get("enabled", False))
    return account, trade_mode, enabled


def _verify_token(token: str) -> tuple[bool, str, str]:
    """Return (ok, role, reason)."""
    import os

    token = str(token or "").strip()
    if not token:
        return False, "", "missing_token"

    env_nt8_key = str(os.getenv("LUMINA_NT8_API_KEY", "")).strip()
    if env_nt8_key and token == env_nt8_key:
        return True, "ninjatrader_bridge", "env_key"

    security_cfg = ConfigLoader.section("security", default=None)
    config_dict = security_cfg if isinstance(security_cfg, dict) and security_cfg else None
    try:
        security = get_security_module(config_dict)
    except Exception:
        return False, "", "security_unavailable"
    api_auth = security["api_key"]
    meta = api_auth.verify_api_key(token)
    if meta is None:
        jwt_auth = security["jwt"]
        payload = jwt_auth.verify_token(token)
        if payload is None:
            return False, "", "invalid_credentials"
        role = str(getattr(payload, "role", "user") or "user")
        if role not in _ALLOWED_ROLES:
            return False, role, "insufficient_role"
        return True, role, "jwt"

    role = str(meta.get("role", "user") or "user")
    if role not in _ALLOWED_ROLES:
        return False, role, "insufficient_role"
    return True, role, "api_key"


@router.websocket("/ws/ninjatrader/v1")
async def ws_ninjatrader_v1(websocket: WebSocket) -> None:
    await websocket.accept()
    account, trade_mode, enabled = _resolve_bridge_config()
    bridge = get_ninjatrader_bridge_service(
        configured_account=account,
        trade_mode=trade_mode,
        ninjatrader_enabled=enabled,
    )
    bridge.set_trade_mode(trade_mode)
    bridge.set_configured_account(account)
    bridge.begin_authentication()

    authenticated = False
    session_id: str | None = None

    try:
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=_AUTH_TIMEOUT_S)
        except asyncio.TimeoutError:
            await websocket.close(code=4401, reason="auth_timeout")
            return

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            await websocket.close(code=4403, reason="invalid_json")
            return

        if not isinstance(payload, dict) or str(payload.get("type", "")) != "auth":
            await websocket.close(code=4401, reason="auth_required")
            return

        try:
            auth_frame = AuthFrame.model_validate(payload)
        except Exception:
            await websocket.close(code=4403, reason="schema_violation")
            return

        ok, role, reason = _verify_token(auth_frame.token)
        correlation_id = auth_frame.correlation_id
        if not ok:
            failed = AuthFailedFrame(
                correlation_id=correlation_id,
                ts=_utc_now_iso(),
                code="AUTH_FAILED",
                message=reason,
            )
            await websocket.send_json(failed.model_dump())
            await websocket.close(code=4401, reason="auth_failed")
            return

        session_id = f"nt8-sess-{uuid.uuid4().hex[:12]}"
        bridge.authenticate_session(session_id=session_id, account_name=account)
        bridge.set_client_info(name=auth_frame.client.name, version=auth_frame.client.version)
        authenticated = True

        auth_ok = AuthOkFrame(
            correlation_id=correlation_id,
            ts=_utc_now_iso(),
            session_id=session_id,
            account_name=account,
        )
        await websocket.send_json(auth_ok.model_dump())

        loop = asyncio.get_running_loop()

        def _send_sync(frame: dict[str, Any]) -> None:
            asyncio.run_coroutine_threadsafe(websocket.send_json(frame), loop).result(timeout=5.0)

        bridge.register_send(_send_sync)

        while True:
            try:
                incoming = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                continue

            if not incoming:
                continue
            try:
                frame_payload = json.loads(incoming)
            except json.JSONDecodeError:
                await websocket.close(code=4403, reason="invalid_json")
                break

            if not isinstance(frame_payload, dict):
                await websocket.close(code=4403, reason="schema_violation")
                break

            if frame_payload.get("type") == "ping" and "schema_version" not in frame_payload:
                await websocket.send_json({"type": "pong", "ts": _utc_now_iso()})
                continue

            try:
                response = bridge.handle_inbound(frame_payload)
            except Exception as exc:
                logger.warning("NT8 frame handling error: %s", exc)
                await websocket.close(code=4403, reason="schema_violation")
                break

            if response is not None:
                await websocket.send_json(response)

    except WebSocketDisconnect:
        logger.debug("NinjaTrader WebSocket disconnected (session=%s)", session_id)
    except Exception:
        logger.exception("NinjaTrader WebSocket handler error")
    finally:
        if authenticated:
            bridge.on_disconnect()
