"""Backward-compatible export for split dashboard admin endpoint core."""

from __future__ import annotations

from .admin_endpoints_core import AdminEndpoints, AdminEndpointsProtocol

__all__ = ["AdminEndpoints", "AdminEndpointsProtocol"]
