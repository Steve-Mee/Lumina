"""WebSocket endpoint for live PPO training evolution metrics."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from lumina_launcher.services.ppo_realtime import ppo_realtime_tailer

router = APIRouter(tags=["ppo"])


@router.websocket("/ws/ppo-evolution")
async def ws_ppo_evolution(websocket: WebSocket) -> None:
    await ppo_realtime_tailer.register_client(websocket)
    try:
        while True:
            try:
                incoming = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                continue
            if incoming == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        ppo_realtime_tailer.unregister_client(websocket)
