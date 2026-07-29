"""Serve frontend/dist under /ui."""
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
