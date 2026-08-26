"""GET /api/core/live auth matrix (loopback free, remote requires key)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_core_live_loopback_no_auth() -> None:
    from lumina_os.backend import core_websocket as cw

    req = MagicMock()
    req.client = SimpleNamespace(host="127.0.0.1")

    with patch.object(cw, "CoreLiveTelemetryReader") as reader_cls:
        reader = reader_cls.return_value
        reader.build_snapshot.return_value = {"ok": True}
        with patch.object(cw, "_build_frame", return_value={"seq": 0, "payload": {"ok": True}}):
            out = await cw.get_core_live(req, x_api_key=None)
    assert out["payload"]["ok"] is True


@pytest.mark.asyncio
async def test_core_live_remote_requires_key() -> None:
    from lumina_os.backend import core_websocket as cw

    req = MagicMock()
    req.client = SimpleNamespace(host="10.0.0.5")

    # Patch where the import resolves inside get_core_live (runtime import).
    import sys

    fake_auth = MagicMock()
    fake_auth.verify_api_key = AsyncMock(
        side_effect=HTTPException(status_code=401, detail="API key required")
    )
    with patch.dict(sys.modules, {"backend.app_auth": fake_auth, "backend": MagicMock()}):
        # Ensure nested attribute path works for `from backend.app_auth import verify_api_key`
        sys.modules["backend"].app_auth = fake_auth
        with pytest.raises(HTTPException) as ei:
            await cw.get_core_live(req, x_api_key=None)
    assert ei.value.status_code == 401
