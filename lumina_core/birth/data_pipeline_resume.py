"""Resume-from-cache branch for birth data pipeline (M5)."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.checkpoint import read_checkpoint_payload, write_checkpoint_payload
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.data_pipeline_types import BirthDataPipelineHost, train_hash
from lumina_core.birth.enrichment_cache import strip_trend_enrichment
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.remediation import ResumeCacheTier, classify_cache_resume_tier
from lumina_core.birth.tick_cache_persist import (
    load_cache_manifest,
    load_split_cache,
    load_ticks_cache,
)
from lumina_core.logging_utils import get_logger
from lumina_core.rl.trend_features import ENRICH_VERSION

logger = get_logger("lumina.birth.data_pipeline")


class BirthDataPipelineResumeMixin:
    """Cache resume tier resolution before cold history load."""

    _host: BirthDataPipelineHost

    def _resolve_resume_cache(
        self,
        *,
        cfg: BirthCurriculumConfig,
        resume: bool,
        training_mode: str,
    ) -> dict[str, Any]:
        """Return ticks/split/flags after optional resume cache hit."""
        host = self._host
        ticks: list[dict[str, Any]] = []
        split: Any | None = None
        resume_cache_decision = None
        resume_skip_load = False
        resume_reenrich_only = False

        if not (resume and host._data_manifest):
            return {
                "ticks": ticks,
                "split": split,
                "resume_cache_decision": resume_cache_decision,
                "resume_skip_load": resume_skip_load,
                "resume_reenrich_only": resume_reenrich_only,
            }

        cached_split = load_split_cache(host.workspace_root, holdout_pct=cfg.holdout_pct)
        cached_ticks = load_ticks_cache(host.workspace_root)
        cache_manifest = load_cache_manifest(host.workspace_root)
        cached_hash = train_hash(cached_split.train) if cached_split else ""
        resume_cache_decision = classify_cache_resume_tier(
            checkpoint_manifest=host._data_manifest,
            cache_manifest=cache_manifest,
            cached_ticks=cached_ticks,
            cached_split=cached_split,
            cached_train_hash=cached_hash,
            holdout_pct=cfg.holdout_pct,
            enrich_version=ENRICH_VERSION,
        )
        logger.info(
            "birth.resume.tier=%s reason=%s",
            resume_cache_decision.tier.value,
            resume_cache_decision.reason,
        )
        if resume_cache_decision.skip_load and cached_ticks and cached_split:
            ticks = [dict(t) for t in cached_ticks]
            split = cached_split
            resume_skip_load = True
            host._real_data_pct = float(host._data_manifest.get("real_data_pct", 0.0) or 0.0)
            if resume_cache_decision.repair_manifest:
                repaired = dict(host._data_manifest)
                repaired["train_hash"] = cached_hash
                repaired["raw_ticks_hash"] = str(
                    (cache_manifest or {}).get("raw_ticks_hash", "") or ""
                )
                repaired["enrich_version"] = ENRICH_VERSION
                repaired["holdout_pct"] = float(cfg.holdout_pct)
                host._data_manifest = repaired
                payload = read_checkpoint_payload(host.workspace_root)
                if payload:
                    payload["data_manifest"] = repaired
                    write_checkpoint_payload(host.workspace_root, payload)
            if not resume_cache_decision.skip_enrich:
                resume_reenrich_only = True
                strip_trend_enrichment(ticks)
        elif resume_cache_decision.tier == ResumeCacheTier.T4:
            logger.info(
                "birth.resume.cache_miss cached_ticks=%s cached_split=%s reason=%s",
                bool(cached_ticks),
                bool(cached_split),
                resume_cache_decision.reason,
            )

        if resume_skip_load:
            resume_message = (
                resume_cache_decision.resume_message
                if resume_cache_decision and resume_cache_decision.resume_message
                else "Checkpoint hervat — cached data geladen (curriculum gaat verder)."
            )
            write_birth_progress(
                host.workspace_root,
                stage="loading_data",
                phase="ticks_ready" if not resume_reenrich_only else "enriching_regimes",
                message=resume_message,
                progress_pct=24.0 if not resume_reenrich_only else 21.0,
                cumulative_trades=host.cumulative_trades,
                target_trades=cfg.trade_budget_cap,
                ppo_steps=host.ppo_steps,
                birth_start_time=host.birth_start_time,
                training_mode=training_mode,
                needs_attention=False,
                attention_summary="",
                attention_reason_code="",
                user_initiated_stop=False,
                resume_cache_tier=(
                    resume_cache_decision.tier.value if resume_cache_decision else ""
                ),
            )

        return {
            "ticks": ticks,
            "split": split,
            "resume_cache_decision": resume_cache_decision,
            "resume_skip_load": resume_skip_load,
            "resume_reenrich_only": resume_reenrich_only,
        }


__all__ = ["BirthDataPipelineResumeMixin"]
