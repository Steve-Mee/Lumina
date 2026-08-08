"""Headless production orchestration mixin.

Split (Wave D): headless_production_lifecycle + headless_production_run.
"""
from __future__ import annotations

from lumina_core.runtime.headless_production_lifecycle import HeadlessProductionLifecycleMixin
from lumina_core.runtime.headless_production_run import HeadlessProductionRunMixin

__all__ = ["HeadlessProductionOrchestrateMixin"]


class HeadlessProductionOrchestrateMixin(
    HeadlessProductionLifecycleMixin,
    HeadlessProductionRunMixin,
):
    """Compose lifecycle + run for headless production."""
