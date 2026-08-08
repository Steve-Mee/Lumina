"""Birth data load, enrichment, cache, and split pipeline (M5 façade ≤400).

Bounded modules:
- ``data_pipeline_types`` — host protocol, result, pure helpers
- ``data_pipeline_resume`` — checkpoint cache resume
- ``data_pipeline_load`` — cold history / synthetic
- ``data_pipeline_enrich`` — news + regime + purged split
"""

from __future__ import annotations

from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.data_pipeline_enrich import BirthDataPipelineEnrichMixin
from lumina_core.birth.data_pipeline_load import BirthDataPipelineLoadMixin
from lumina_core.birth.data_pipeline_resume import BirthDataPipelineResumeMixin
from lumina_core.birth.data_pipeline_types import (
    BirthDataPipelineHost,
    BirthDataPrepareResult,
    generate_synthetic_ticks,
    train_hash,
)
# Re-exports for public API + unit monkeypatch sites (tests patch this module).
from lumina_core.birth.history_loader import load_historical_ticks  # noqa: F401
from lumina_core.birth.progress import write_birth_progress  # noqa: F401
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim  # noqa: F401

__all__ = [
    "BirthDataPipeline",
    "BirthDataPipelineHost",
    "BirthDataPrepareResult",
    "enrich_ticks_for_sim",
    "generate_synthetic_ticks",
    "load_historical_ticks",
    "train_hash",
    "write_birth_progress",
]


class BirthDataPipeline(
    BirthDataPipelineResumeMixin,
    BirthDataPipelineLoadMixin,
    BirthDataPipelineEnrichMixin,
):
    """Orchestrates prepare_ticks_and_split via resume → load → enrich."""

    def __init__(self, host: BirthDataPipelineHost) -> None:
        self._host = host

    def prepare_ticks_and_split(
        self,
        *,
        cfg: BirthCurriculumConfig,
        max_days: int,
        prefer_real: bool,
        practice_mode: bool,
        allow_minimal_synthetic: bool,
        resume: bool,
        training_mode: str,
    ) -> BirthDataPrepareResult:
        resume_state = self._resolve_resume_cache(
            cfg=cfg,
            resume=resume,
            training_mode=training_mode,
        )
        ticks: list[dict[str, Any]] = list(resume_state["ticks"])
        split = resume_state["split"]
        resume_cache_decision = resume_state["resume_cache_decision"]
        resume_skip_load = bool(resume_state["resume_skip_load"])
        resume_reenrich_only = bool(resume_state["resume_reenrich_only"])

        if not ticks:
            loaded = self._load_ticks_cold(
                cfg=cfg,
                max_days=max_days,
                prefer_real=prefer_real,
                practice_mode=practice_mode,
                allow_minimal_synthetic=allow_minimal_synthetic,
                resume=resume,
                training_mode=training_mode,
                resume_cache_decision=resume_cache_decision,
            )
            if isinstance(loaded, BirthDataPrepareResult):
                return loaded
            ticks = loaded

        result = self._enrich_and_split(
            ticks=ticks,
            split=split,
            cfg=cfg,
            training_mode=training_mode,
            resume_skip_load=resume_skip_load,
            resume_reenrich_only=resume_reenrich_only,
        )
        # Preserve resume metadata on all success paths
        if result.early_return is None:
            result = BirthDataPrepareResult(
                ticks=result.ticks,
                split=result.split,
                resume_cache_decision=resume_cache_decision,
                resume_skip_load=resume_skip_load,
                resume_reenrich_only=resume_reenrich_only,
                early_return=None,
            )
        else:
            result = BirthDataPrepareResult(
                ticks=result.ticks,
                split=result.split,
                resume_cache_decision=resume_cache_decision,
                resume_skip_load=resume_skip_load,
                resume_reenrich_only=resume_reenrich_only,
                early_return=result.early_return,
            )
        return result
