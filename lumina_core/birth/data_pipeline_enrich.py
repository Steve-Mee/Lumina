"""Enrichment + purged train/holdout split for birth data pipeline (M5)."""

from __future__ import annotations

import time
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.data_pipeline_types import (
    BirthDataPipelineHost,
    BirthDataPrepareResult,
    train_hash,
)
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.purged_split import purged_train_holdout_split
from lumina_core.birth.tick_cache_persist import (
    compute_ticks_fingerprint,
    save_birth_data_cache,
)
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim, real_data_percentage
from lumina_core.logging_utils import get_logger
from lumina_core.rl.trend_features import ENRICH_VERSION, MIN_TREND_LOOKBACK

logger = get_logger("lumina.birth.data_pipeline")


class BirthDataPipelineEnrichMixin:
    """Regime/news enrichment and purged split (full or resume re-enrich)."""

    _host: BirthDataPipelineHost

    def write_data_prep_progress(self, **kwargs: Any) -> None:
        raise NotImplementedError

    def _enrich_and_split(
        self,
        *,
        ticks: list[dict[str, Any]],
        split: Any | None,
        cfg: BirthCurriculumConfig,
        training_mode: str,
        resume_skip_load: bool,
        resume_reenrich_only: bool,
    ) -> BirthDataPrepareResult:
        host = self._host

        if ticks and not host._last_raw_ticks_hash:
            host._last_raw_ticks_hash = compute_ticks_fingerprint(ticks)
        if resume_skip_load:
            host._last_raw_ticks_hash = str(
                host._data_manifest.get("raw_ticks_hash", "")
                or host._last_raw_ticks_hash
                or compute_ticks_fingerprint(ticks)
            )

        if resume_reenrich_only and split is not None:
            return self._reenrich_resume_ticks(
                ticks=ticks,
                split=split,
                cfg=cfg,
                training_mode=training_mode,
            )

        if split is None:
            return self._full_enrich_and_split(
                ticks=ticks,
                cfg=cfg,
                training_mode=training_mode,
            )

        if not ticks:
            return BirthDataPrepareResult(
                ticks=[],
                split=None,
                early_return={
                    "status": "history_unavailable",
                    "total_trades": 0,
                    "ppo_steps": 0,
                    "training_mode": "certified",
                },
            )

        return BirthDataPrepareResult(
            ticks=ticks,
            split=split,
            resume_skip_load=resume_skip_load,
            resume_reenrich_only=resume_reenrich_only,
        )

    def _reenrich_resume_ticks(
        self,
        *,
        ticks: list[dict[str, Any]],
        split: Any,
        cfg: BirthCurriculumConfig,
        training_mode: str,
    ) -> BirthDataPrepareResult:
        host = self._host
        total_ticks = len(ticks)
        last_regime_progress_write_at = 0.0

        def _resume_regime_progress(processed: int, total: int) -> None:
            if host._stop_requested():
                return
            nonlocal last_regime_progress_write_at
            now = time.time()
            is_final = total > 0 and processed >= total
            if not is_final and (now - last_regime_progress_write_at) < 1.0:
                return
            last_regime_progress_write_at = now
            pct = 21.0 + min(3.0, (processed / total) * 3.0) if total > 0 else 21.0
            self.write_data_prep_progress(
                phase="enriching_regimes",
                message=(
                    f"Regime map herberekend: {processed:,}/{total:,} ticks "
                    f"({total_ticks:,} totaal)"
                ),
                progress_pct=pct,
                training_mode=training_mode,
                processed=processed,
                total=total,
            )

        ticks = enrich_ticks_for_sim(
            ticks,
            on_progress=_resume_regime_progress,
            workspace_root=host.workspace_root,
            raw_ticks_hash=host._last_raw_ticks_hash,
        )
        if host._stop_requested():
            return BirthDataPrepareResult(
                ticks=ticks,
                split=split,
                early_return={
                    "status": "paused",
                    "total_trades": 0,
                    "ppo_steps": 0,
                    "training_mode": training_mode,
                },
            )
        host._real_data_pct = real_data_percentage(ticks)
        save_birth_data_cache(
            host.workspace_root,
            ticks=ticks,
            split=split,
            holdout_pct=cfg.holdout_pct,
            raw_ticks_hash=host._last_raw_ticks_hash,
            train_hash=train_hash(split.train),
            enrich_version=ENRICH_VERSION,
        )
        # Signal success via sentinel None; caller uses updated ticks from return path
        # Store enriched ticks on host-less path: return result with ticks
        return BirthDataPrepareResult(
            ticks=ticks,
            split=split,
            resume_skip_load=True,
            resume_reenrich_only=True,
        )

    def _full_enrich_and_split(
        self,
        *,
        ticks: list[dict[str, Any]],
        cfg: BirthCurriculumConfig,
        training_mode: str,
    ) -> BirthDataPrepareResult:
        host = self._host
        news_cfg = cfg.news
        try:
            ticks = enrich_ticks_with_news(
                ticks,
                workspace_root=host.workspace_root,
                primary=news_cfg.primary,
                enable_cache=news_cfg.enable_cache,
                cache_path=news_cfg.cache_path,
            )
        except Exception as exc:
            logger.warning("birth.news.enrich_skipped detail=%s", exc)

        if host._stop_requested():
            return BirthDataPrepareResult(
                ticks=ticks,
                split=None,
                early_return={
                    "status": "paused",
                    "total_trades": 0,
                    "ppo_steps": 0,
                    "training_mode": training_mode,
                },
            )

        total_ticks = len(ticks)
        last_regime_progress_write_at = 0.0

        def _regime_enrich_progress(processed: int, total: int) -> None:
            if host._stop_requested():
                return
            nonlocal last_regime_progress_write_at
            now = time.time()
            is_final = total > 0 and processed >= total
            if not is_final and (now - last_regime_progress_write_at) < 1.0:
                return
            last_regime_progress_write_at = now
            pct = 21.0
            if total > 0:
                pct = 21.0 + min(3.0, (processed / total) * 3.0)
            self.write_data_prep_progress(
                phase="enriching_regimes",
                message=(
                    f"Regime map bouwen: {processed:,}/{total:,} ticks "
                    f"({total_ticks:,} totaal)"
                ),
                progress_pct=pct,
                training_mode=training_mode,
                processed=processed,
                total=total,
            )

        self.write_data_prep_progress(
            phase="enriching_regimes",
            message=f"Regime map bouwen (0/{max(0, total_ticks - MIN_TREND_LOOKBACK):,} ticks)…",
            progress_pct=21.0,
            training_mode=training_mode,
        )
        ticks = enrich_ticks_for_sim(
            ticks,
            on_progress=_regime_enrich_progress,
            workspace_root=host.workspace_root,
            raw_ticks_hash=host._last_raw_ticks_hash or compute_ticks_fingerprint(ticks),
        )
        if host._stop_requested():
            return BirthDataPrepareResult(
                ticks=ticks,
                split=None,
                early_return={
                    "status": "paused",
                    "total_trades": 0,
                    "ppo_steps": 0,
                    "training_mode": training_mode,
                },
            )

        host._real_data_pct = real_data_percentage(ticks)
        self.write_data_prep_progress(
            phase="train_holdout_split",
            message="Train/holdout split (purged)…",
            progress_pct=24.0,
            training_mode=training_mode,
        )
        split = purged_train_holdout_split(ticks, holdout_pct=cfg.holdout_pct)
        self.write_data_prep_progress(
            phase="holdout_preflight",
            message="Holdout preflight controleren…",
            progress_pct=24.5,
            training_mode=training_mode,
        )
        return BirthDataPrepareResult(ticks=ticks, split=split)


__all__ = ["BirthDataPipelineEnrichMixin"]
