"""Dash admin dashboard layout façade (M5)."""
from __future__ import annotations

from lumina_core.engine.admin_dashboard_layout_build import AdminDashboardLayoutBuildMixin


class AdminDashboardLayoutMixin(AdminDashboardLayoutBuildMixin):
    """Admin dashboard layout — implementation in build mixin."""


__all__ = ["AdminDashboardLayoutMixin"]
