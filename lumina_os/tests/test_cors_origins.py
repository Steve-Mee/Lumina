"""Tests for local dev CORS origin allowlist (Tauri + Vite)."""

from __future__ import annotations

import pytest

from api.monitoring import REACT_LOCAL_DEV_ORIGINS, extend_cors_origins_with_local_vite_dev


@pytest.mark.unit
def test_react_local_dev_origins_includes_tauri_vite_port() -> None:
    origins = {o.rstrip("/").lower() for o in REACT_LOCAL_DEV_ORIGINS}
    assert "http://localhost:1420" in origins
    assert "http://127.0.0.1:1420" in origins


@pytest.mark.unit
def test_extend_cors_origins_merges_tauri_port() -> None:
    merged = extend_cors_origins_with_local_vite_dev([])
    keys = {o.rstrip("/").lower() for o in merged}
    assert "http://localhost:1420" in keys
    assert "http://localhost:5173" in keys
