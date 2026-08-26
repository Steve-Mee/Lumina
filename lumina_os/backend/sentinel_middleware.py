"""ASGI middleware: IP allowlist + Sentinel containment (network plane only).

Must be registered **last** via ``app.add_middleware`` so it is outermost
(Starlette runs last-added middleware first).
"""

from __future__ import annotations

import logging
import os
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


def resolve_request_client_host(request: Request) -> str:
    """Client IP for allowlist.

    X-Forwarded-For is honored only when ``LUMINA_TRUST_PROXY=true`` **and**
    the immediate peer is loopback (or in ``LUMINA_TRUSTED_PROXIES``).
    Prevents spoofed XFF from remote attackers.
    """
    peer = (request.client.host if request.client else "") or ""
    trust = str(os.getenv("LUMINA_TRUST_PROXY", "")).strip().lower() in {
        "1",
        "true",
        "yes",
    }
    if not trust:
        return peer

    try:
        from lumina_core.cyber_sentinel import is_loopback_host

        trusted_raw = str(os.getenv("LUMINA_TRUSTED_PROXIES", "")).strip()
        peer_ok = is_loopback_host(peer)
        if not peer_ok and trusted_raw:
            from lumina_core.cyber_sentinel import client_ip_allowed

            peer_ok = client_ip_allowed(peer, allowlist_raw=trusted_raw)
        if not peer_ok:
            return peer
    except Exception:
        return peer

    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if not xff:
        return peer
    # Left-most is original client in standard proxy chains.
    return xff.split(",")[0].strip() or peer


class SentinelAccessMiddleware(BaseHTTPMiddleware):
    """Fail-closed remote access when allowlist/containment demand it."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path or ""
        try:
            from lumina_core.cyber_sentinel import (
                evaluate_client_access,
                is_loopback_host,
            )
        except Exception:
            return await call_next(request)

        host = resolve_request_client_host(request)

        # Loopback operators (Tauri deck) unrestricted for local UX.
        if is_loopback_host(host):
            return await call_next(request)

        veto = evaluate_client_access(host)
        if veto is not None and veto.hard:
            logger.warning(
                "sentinel.middleware deny host=%s path=%s code=%s",
                host,
                path,
                veto.code,
            )
            return JSONResponse(
                status_code=403,
                content={
                    "detail": veto.message,
                    "code": veto.code,
                    "domain": veto.domain,
                },
            )
        return await call_next(request)
