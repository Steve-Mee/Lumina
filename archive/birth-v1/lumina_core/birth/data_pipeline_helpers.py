"""Compat re-export — helpers live in data_pipeline_* modules (M5)."""

from __future__ import annotations

from lumina_core.birth.data_pipeline_types import BirthDataPipelineHost

__all__ = ["BirthDataPipelineHost", "BirthDataPipelineHelpersMixin"]


class BirthDataPipelineHelpersMixin:
    """Deprecated empty mixin kept for import compatibility."""

    def __init__(self, host: BirthDataPipelineHost) -> None:
        self._host = host
