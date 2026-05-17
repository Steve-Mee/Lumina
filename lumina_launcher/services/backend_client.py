"""
Backend Client for Lumina OS
Robuuste, async-ready client voor de FastAPI backend in lumina_os/backend.

GET-handlers gebruiken standaard synchrone httpx (Streamlit-schrijven zonder await).
Mutaties en bestaande async-callers blijven via ``_request`` / ``async`` methodes.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

import httpx

from lumina_launcher.observability import log_event

logger = logging.getLogger(__name__)

DEFAULT_BACKEND_URL = os.getenv("LUMINA_BACKEND_URL", "http://localhost:8000")


class BackendClient:
    def __init__(self, base_url: str = DEFAULT_BACKEND_URL, timeout: float = 12.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client: Optional[httpx.AsyncClient] = None
        self.sync_client: Optional[httpx.Client] = None
        self.api_key: str = (
            os.getenv("LUMINA_ADMIN_API_KEY", "").strip()
            or os.getenv("LUMINA_BACKEND_API_KEY", "").strip()
            or os.getenv("LUMINA_DASHBOARD_API_KEY", "").strip()
            or os.getenv("X_API_KEY", "").strip()
        )

    async def _get_client(self) -> httpx.AsyncClient:
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(timeout=self.timeout)
        return self.client

    def _sync_request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Sync HTTP helper for Streamlit (no asyncio event-loop coupling)."""
        url = f"{self.base_url}{path}"
        started = time.perf_counter()
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.api_key and "X-API-Key" not in headers:
            headers["X-API-Key"] = self.api_key
        try:
            if self.sync_client is None or self.sync_client.is_closed:
                self.sync_client = httpx.Client(timeout=self.timeout)
            response = self.sync_client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            payload = response.json()
            elapsed = int((time.perf_counter() - started) * 1000)
            log_event("launcher.http.request", method=method, path=path, status=response.status_code, duration_ms=elapsed)
            return payload
        except httpx.HTTPStatusError as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            logger.warning(f"Backend HTTP error {exc.response.status_code} on {path}")
            log_event(
                "launcher.http.error",
                level=logging.WARNING,
                method=method,
                path=path,
                status=exc.response.status_code,
                duration_ms=elapsed,
            )
            return {"error": f"HTTP {exc.response.status_code}", "detail": exc.response.text}
        except httpx.RequestError as exc:
            elapsed = int((time.perf_counter() - started) * 1000)
            logger.debug("Backend unavailable on %s: %s", path, exc)
            log_event(
                "launcher.http.error",
                level=logging.DEBUG,
                method=method,
                path=path,
                status="unavailable",
                duration_ms=elapsed,
            )
            return {"error": "Backend unavailable", "detail": str(exc)}

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        client = await self._get_client()
        url = f"{self.base_url}{path}"
        headers = dict(kwargs.pop("headers", {}) or {})
        if self.api_key and "X-API-Key" not in headers:
            headers["X-API-Key"] = self.api_key
        try:
            response = await client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(f"Backend HTTP error {exc.response.status_code} on {path}")
            return {"error": f"HTTP {exc.response.status_code}", "detail": exc.response.text}
        except httpx.RequestError as exc:
            logger.debug("Backend unavailable on %s: %s", path, exc)
            return {"error": "Backend unavailable", "detail": str(exc)}

    def _cached_sync_get(self, cache_key: str, path: str, ttl_seconds: int = 10) -> dict[str, Any]:
        now = time.time()
        cached = self._cache.get(cache_key)
        if isinstance(cached, dict) and (now - float(cached.get("timestamp", 0.0))) < ttl_seconds:
            return cached.get("data", {})
        payload = self._sync_request("GET", path)
        self._cache[cache_key] = {"data": payload, "timestamp": now}
        return payload

    def get_leaderboard(self, ttl_seconds: int = 10) -> dict[str, Any]:
        return self._cached_sync_get("leaderboard_sync", "/leaderboard", ttl_seconds=ttl_seconds)

    def get_leaderboard_sync(self) -> dict[str, Any]:
        return self.get_leaderboard(ttl_seconds=10)

    def get_global_wisdom(self, ttl_seconds: int = 15) -> dict[str, Any]:
        return self._cached_sync_get("global_wisdom_sync", "/global_wisdom", ttl_seconds=ttl_seconds)

    def get_global_wisdom_sync(self) -> dict[str, Any]:
        return self.get_global_wisdom(ttl_seconds=15)

    async def get_leaderboard_async(self) -> dict[str, Any]:
        return await self._request("GET", "/leaderboard")

    async def get_global_wisdom_async(self) -> dict[str, Any]:
        return await self._request("GET", "/global_wisdom")

    # Simpele caching (kan later uitgebreid worden met TTL)
    _cache: dict[str, Any] = {}

    async def get_leaderboard_cached(self, ttl_seconds: int = 30) -> dict[str, Any]:
        import time

        key = "leaderboard"
        now = time.time()
        if key in self._cache and (now - self._cache[key]["timestamp"]) < ttl_seconds:
            return self._cache[key]["data"]
        data = self.get_leaderboard()
        self._cache[key] = {"data": data, "timestamp": now}
        return data

    async def get_reconciliation_status(self) -> dict[str, Any]:
        return await self._request("GET", "/reconciliation-status")

    async def delete_all_trades(self) -> dict[str, Any]:
        return await self._request("DELETE", "/trades")

    async def delete_demo_data(self) -> dict[str, Any]:
        return await self._request("DELETE", "/demo-data")

    def start_birth_sync(self, target_trades: int = 25000, force: bool = False) -> dict[str, Any]:
        params = f"target_trades={int(target_trades)}&force={'true' if force else 'false'}"
        return self._sync_request("POST", f"/api/birth/start?{params}")

    def get_birth_status_sync(self) -> dict[str, Any]:
        return self._sync_request("GET", "/api/birth/status")

    def emergency_flatten_and_cancel(self) -> dict[str, Any]:
        """Production safety action: backend emergency order stop."""
        response = self._sync_request("POST", "/orders/emergency-stop")
        if response.get("error"):
            return {"ok": False, "error": response.get("error"), "detail": response.get("detail")}
        return {"ok": True, "response": response}

    async def close(self):
        if self.client and not self.client.is_closed:
            await self.client.aclose()
        if self.sync_client and not self.sync_client.is_closed:
            self.sync_client.close()
