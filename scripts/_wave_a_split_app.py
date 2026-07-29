"""Extract lumina_os/backend/app.py into focused modules. Run: python scripts/_wave_a_split_app.py"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "lumina_os" / "backend" / "app.py"
BACKEND = APP.parent

# Read current app for splicing by markers — we'll write modules from known content.


def main() -> None:
    (BACKEND / "embedded_ui.py").write_text(
        '''"""Serve frontend/dist under /ui."""
from __future__ import annotations

import os
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.types import ASGIApp

_LUMINA_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def embedded_ui_dist_dir() -> Path:
    override = os.getenv("LUMINA_EMBEDDED_UI_DIST", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return (_LUMINA_REPO_ROOT / "frontend" / "dist").resolve()


class LuminaEmbeddedUIMiddleware(BaseHTTPMiddleware):
    """Serve `frontend/dist` under `/ui` on every request (no import-time gate)."""

    def __init__(self, app: ASGIApp, *, dist_dir: Path):
        super().__init__(app)
        self._dist = dist_dir.resolve()

    @staticmethod
    def _apply_ui_cache_headers(*, response: FileResponse, is_index: bool) -> FileResponse:
        if is_index:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.scope["type"] != "http":
            return await call_next(request)
        if request.method not in ("GET", "HEAD"):
            return await call_next(request)
        path = request.url.path
        if path != "/ui" and not path.startswith("/ui/"):
            return await call_next(request)

        idx = self._dist / "index.html"
        if not idx.is_file():
            return JSONResponse(
                {
                    "detail": "Embedded React UI not built",
                    "hint": (
                        "Run from repo root: cd frontend && npm ci && npm run build:embedded "
                        "(or scripts/build_embedded_ui.ps1). Reload this URL after the build."
                    ),
                },
                status_code=503,
            )

        tail = path[len("/ui") :].lstrip("/")
        if not tail:
            return self._apply_ui_cache_headers(response=FileResponse(idx), is_index=True)

        target = (self._dist / tail).resolve()
        root = self._dist.resolve()
        try:
            target.relative_to(root)
        except ValueError:
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        if target.is_file():
            return self._apply_ui_cache_headers(response=FileResponse(target), is_index=False)
        return self._apply_ui_cache_headers(response=FileResponse(idx), is_index=True)
''',
        encoding="utf-8",
    )

    (BACKEND / "app_auth.py").write_text(
        '''"""API key / admin / rate-limit FastAPI dependencies."""
from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, Header, HTTPException

_SECURITY: dict[str, Any] | None = None


def configure_app_security(security: dict[str, Any]) -> None:
    global _SECURITY
    _SECURITY = security


def _sec() -> dict[str, Any]:
    if _SECURITY is None:
        raise RuntimeError("app_auth.configure_app_security not called")
    return _SECURITY


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> dict[str, Any]:
    """Dependency to verify API key authentication."""
    security = _sec()
    if not x_api_key:
        security["audit_log"].log_auth_attempt("unknown", False, "api_key")
        raise HTTPException(status_code=401, detail="API key required")

    key_meta = security["api_key"].verify_api_key(x_api_key)
    if not key_meta:
        security["audit_log"].log_auth_attempt("unknown", False, "api_key")
        raise HTTPException(status_code=401, detail="Invalid API key")

    security["audit_log"].log_auth_attempt(key_meta.get("name", "api_key"), True, "api_key")
    return {"api_key": x_api_key, "metadata": key_meta}


async def verify_admin_role(auth: dict[str, Any] = Depends(verify_api_key)) -> dict[str, Any]:
    """Dependency to verify admin role for destructive operations."""
    security = _sec()
    if not security["config"].admin_role_required:
        return auth

    role = auth["metadata"].get("role", "user")
    if role != "admin":
        security["audit_log"].log_unauthorized_access(
            auth["metadata"].get("name", "unknown"),
            "admin_operation",
            f"insufficient_role_{role}",
        )
        raise HTTPException(status_code=403, detail="Admin role required")

    return auth


async def check_rate_limit(x_api_key: Optional[str] = Header(None)) -> None:
    """Dependency to check rate limiting."""
    security = _sec()
    client_id = x_api_key or "anonymous"
    if not security["rate_limiter"].is_allowed(client_id):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
''',
        encoding="utf-8",
    )

    (BACKEND / "app_lifespan.py").write_text(
        '''"""FastAPI lifespan hooks for the OS backend."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from lumina_launcher.services.ppo_realtime import ppo_realtime_tailer


@asynccontextmanager
async def app_lifespan(_app: FastAPI):
    ppo_realtime_tailer.start_watching(loop=asyncio.get_running_loop())
    yield
    ppo_realtime_tailer.stop_watching()
''',
        encoding="utf-8",
    )

    print("Wrote embedded_ui, app_auth, app_lifespan — emergency/community via follow-up write")


if __name__ == "__main__":
    main()
