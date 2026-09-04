"""Resume-from-cache branch for birth data pipeline (M5)."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.checkpoint import read_checkpoint_payload, write_checkpoint_payload
from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.data_pipeline_types import BirthDataPipelineHost, train_hash
from lumina_core.birth.enrichment_cache import strip_trend_enrichment
from lumina_core.birth.foundation_history import resolve_birth_history_instrument
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.remediation import ResumeCacheTier, classify_cache_resume_tier
from lumina_core.birth.tick_cache_persist import (
    load_cache_manifest,
    load_split_cache,
    load_ticks_cache,
)
from lumina_core.birth.data_source_honesty import host_real_data_pct
from lumina_core.logging_utils import get_logger
from lumina_core.rl.trend_features import ENRICH_VERSION

logger = get_logger("lumina.birth.data_pipeline")


def _manifest_from_cache_file(cache_manifest: dict[str, Any] | None) -> dict[str, Any]:
    raw = dict(cache_manifest or {})
    try:
        actual = int(raw.get("actual_calendar_days") or 0)
    except (TypeError, ValueError):
        actual = 0
    try:
        requested = int(raw.get("requested_days") or 0)
    except (TypeError, ValueError):
        requested = 0
    try:
        real_pct = float(raw.get("real_data_pct") or 0.0)
    except (TypeError, ValueError):
        real_pct = 0.0
    return {
        "train_hash": str(raw.get("train_hash") or ""),
        "raw_ticks_hash": str(raw.get("raw_ticks_hash") or ""),
        "holdout_pct": float(raw.get("holdout_pct") or 0.2),
        "enrich_version": str(raw.get("enrich_version") or ""),
        "requested_days": requested,
        "actual_calendar_days": actual,
        "days_loaded": actual or requested,
        "tick_count": int(raw.get("tick_count") or 0),
        "train_tick_count": int(raw.get("train_tick_count") or 0),
        "holdout_tick_count": int(raw.get("holdout_tick_count") or 0),
        "instruments": list(raw.get("instruments") or []),
        "stitched": bool(raw.get("stitched")),
        "stitched_from": list(raw.get("stitched_from") or []),
        "real_data_pct": real_pct,
        "preflight_ok": bool(raw.get("preflight_ok", False)),
        "holdout_regimes": list(raw.get("holdout_regimes") or []),
    }


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

        reuse_data = bool(getattr(host, "_reuse_data_manifest", False))
        if not ((resume and host._data_manifest) or reuse_data):
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
        if reuse_data and not host._data_manifest and cache_manifest:
            host._data_manifest = _manifest_from_cache_file(cache_manifest)
        cached_hash = train_hash(cached_split.train) if cached_split else ""
        current_instrument = resolve_birth_history_instrument(
            getattr(host, "market_data_service", None),
            getattr(host, "runtime", None),
        )
        resume_cache_decision = classify_cache_resume_tier(
            checkpoint_manifest=host._data_manifest,
            cache_manifest=cache_manifest,
            cached_ticks=cached_ticks,
            cached_split=cached_split,
            cached_train_hash=cached_hash,
            holdout_pct=cfg.holdout_pct,
            enrich_version=ENRICH_VERSION,
            current_instrument=current_instrument,
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
            host._real_data_pct = host_real_data_pct(
                cached_ticks,
                manifest_pct=float(host._data_manifest.get("real_data_pct", 0.0) or 0.0),
            )
            host._data_manifest["real_data_pct"] = host._real_data_pct
            if resume_cache_decision.repair_manifest:
                repaired = dict(host._data_manifest)
                cache_m = dict(cache_manifest or {})
                repaired["train_hash"] = cached_hash
                repaired["raw_ticks_hash"] = str(cache_m.get("raw_ticks_hash", "") or "")
                repaired["enrich_version"] = ENRICH_VERSION
                repaired["holdout_pct"] = float(cfg.holdout_pct)
                for key in (
                    "requested_days",
                    "actual_calendar_days",
                    "days_loaded",
                    "tick_count",
                    "train_tick_count",
                    "holdout_tick_count",
                    "instruments",
                    "stitched",
                    "stitched_from",
                ):
                    if not repaired.get(key) and cache_m.get(key) not in (None, "", [], {}):
                        repaired[key] = cache_m[key]
                if not repaired.get("days_loaded"):
                    repaired["days_loaded"] = int(cache_m.get("actual_calendar_days") or 0)
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
            if reuse_data and not resume:
                resume_message = (
                    "Certified tick-cache geladen — Stage 1 herstart "
                    "(reused_manifest, geen Fabric history-probe)."
                )
            else:
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
