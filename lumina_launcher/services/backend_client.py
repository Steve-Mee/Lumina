"""
Backend Client for Lumina OS
Robuuste, async-ready client voor de FastAPI backend in lumina_os/backend.

GET-handlers gebruiken standaard synchrone httpx (Streamlit-schrijven zonder await).
Mutaties en bestaande async-callers blijven via ``_request`` / ``async`` methodes.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BACKEND_URL = os.getenv("LUMINA_BACKEND_URL", "http://localhost:8000")


class BackendClient:
    def __init__(self, base_url: str = DEFAULT_BACKEND_URL, timeout: float = 12.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(timeout=self.timeout)
        return self.client

    def _sync_request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Sync HTTP helper for Streamlit (no asyncio event-loop coupling)."""
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout) as sync_client:
                response = sync_client.request(method, url, **kwargs)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(f"Backend HTTP error {exc.response.status_code} on {path}")
            return {"error": f"HTTP {exc.response.status_code}", "detail": exc.response.text}
        except httpx.RequestError as exc:
            logger.error(f"Backend connection error: {exc}")
            return {"error": "Backend unavailable", "detail": str(exc)}

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        client = await self._get_client()
        url = f"{self.base_url}{path}"
        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            logger.warning(f"Backend HTTP error {exc.response.status_code} on {path}")
            return {"error": f"HTTP {exc.response.status_code}", "detail": exc.response.text}
        except httpx.RequestError as exc:
            logger.error(f"Backend connection error: {exc}")
            return {"error": "Backend unavailable", "detail": str(exc)}

    def get_leaderboard(self) -> dict[str, Any]:
        return self._sync_request("GET", "/leaderboard")

    def get_leaderboard_sync(self) -> dict[str, Any]:
        # Direct _sync_request: do not chain via get_leaderboard() — old hot-reload
        # states could leave an async get_leaderboard on the class and return a coroutine.
        return self._sync_request("GET", "/leaderboard")

    def get_global_wisdom(self) -> dict[str, Any]:
        return self._sync_request("GET", "/global_wisdom")

    def get_global_wisdom_sync(self) -> dict[str, Any]:
        return self._sync_request("GET", "/global_wisdom")

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

    async def close(self):
        if self.client and not self.client.is_closed:
            await self.client.aclose()
