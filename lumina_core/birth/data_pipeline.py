"""Birth data load, enrichment, cache, and split pipeline (extracted from engine)."""

from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.checkpoint import read_checkpoint_payload, write_checkpoint_payload
from lumina_core.birth.enrichment_cache import strip_trend_enrichment
from lumina_core.birth.history_loader import load_historical_ticks
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.purged_split import purged_train_holdout_split
from lumina_core.birth.remediation import ResumeCacheTier, classify_cache_resume_tier
from lumina_core.birth.tick_cache_persist import (
    compute_ticks_fingerprint,
    load_cache_manifest,
    load_split_cache,
    load_ticks_cache,
    save_birth_data_cache,
)
from lumina_core.birth.tick_enricher import enrich_ticks_for_sim, real_data_percentage
from lumina_core.logging_utils import get_logger
from lumina_core.rl.trend_features import ENRICH_VERSION, MIN_TREND_LOOKBACK

logger = get_logger("lumina.birth.data_pipeline")


class BirthDataPipelineHost(Protocol):
    workspace_root: Path
    birth_config: BirthCurriculumConfig
    market_data_service: Any
    runtime: Any
    birth_start_time: float
    cumulative_trades: int
    ppo_steps: int
    _data_manifest: dict[str, Any]
    _last_raw_ticks_hash: str
    _real_data_pct: float

    def _stop_requested(self) -> bool: ...

    def _emit_birth_progress(self, **kwargs: Any) -> None: ...

    def _notify_history_unavailable(self, detail: str) -> None: ...


def generate_synthetic_ticks(n_ticks: int, *, start_price: float) -> list[dict[str, Any]]:
    rng = random.Random(51)
    price = max(100.0, float(start_price))
    out: list[dict[str, Any]] = []
    for i in range(max(1, n_ticks)):
        shock = rng.gauss(0.0, 0.0016)
        price = max(10.0, price * (1.0 + shock))
        out.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "last": float(price),
                "close": float(price),
                "bid": float(price - 0.125),
                "ask": float(price + 0.125),
                "volume": 1000,
                "regime": "SYNTHETIC",
                "imbalance": 1.0,
                "source": "synthetic",
                "bar_index": i,
            }
        )
    return out


def train_hash(ticks: list[dict[str, Any]]) -> str:
    if not ticks:
        return ""
    head = str(ticks[0].get("timestamp", ""))
    tail = str(ticks[-1].get("timestamp", ""))
    payload = f"{len(ticks)}:{head}:{tail}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


@dataclass(slots=True)
class BirthDataPrepareResult:
    ticks: list[dict[str, Any]]
    split: Any | None
    resume_cache_decision: Any | None = None
    resume_skip_load: bool = False
    resume_reenrich_only: bool = False
    early_return: dict[str, Any] | None = None


class BirthDataPipeline:
    def __init__(self, host: BirthDataPipelineHost) -> None:
        self._host = host

    def write_data_prep_progress(
        self,
        *,
        phase: str,
        message: str,
        progress_pct: float,
        training_mode: str,
        processed: int | None = None,
        total: int | None = None,
    ) -> None:
        kwargs: dict[str, Any] = {"training_mode": training_mode}
        if processed is not None:
            kwargs["loading_chunk"] = int(processed)
        if total is not None:
            kwargs["chunk_total"] = int(total)
        self._host._emit_birth_progress(
            stage="loading_data",
            phase=phase,
            message=message,
            progress_pct=float(progress_pct),
            cumulative_trades=0,
            target_trades=self._host.birth_config.trade_budget_cap,
            birth_start_time=self._host.birth_start_time,
            extra_parts=(kwargs,),
        )

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
        host = self._host
        ticks: list[dict[str, Any]] = []
        split: Any | None = None
        resume_cache_decision = None
        resume_skip_load = False
        resume_reenrich_only = False

        if resume and host._data_manifest:
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

        if not ticks:
            loading_message = (
                resume_cache_decision.resume_message
                if resume and resume_cache_decision and resume_cache_decision.resume_message
                else (
                    "Checkpoint hervat — data opnieuw voorbereid (curriculum gaat verder, geen wipe)."
                    if resume
                    else f"Historische data laden ({max_days} dagen)…"
                )
            )
            write_birth_progress(
                host.workspace_root,
                stage="loading_data",
                phase="loading_history",
                message=loading_message,
                progress_pct=8.0,
                cumulative_trades=host.cumulative_trades if resume else 0,
                target_trades=cfg.trade_budget_cap,
                birth_start_time=host.birth_start_time,
                training_mode=training_mode,
                ppo_steps=host.ppo_steps if resume else 0,
            )

            def _history_chunk_progress(**chunk_meta: Any) -> None:
                if host._stop_requested():
                    return
                chunk_idx = int(
                    chunk_meta.get("chunk_index")
                    or chunk_meta.get("chunk")
                    or chunk_meta.get("loading_chunk")
                    or 0
                )
                chunk_total = int(
                    chunk_meta.get("chunk_total") or chunk_meta.get("total_chunks") or 0
                )
                bars_loaded = int(
                    chunk_meta.get("bars_merged")
                    or chunk_meta.get("bars_loaded")
                    or chunk_meta.get("chunk_bars")
                    or 0
                )
                chunk_phase = str(chunk_meta.get("chunk_phase", "fetch") or "fetch").strip().lower()
                pct = 8.0
                if chunk_total > 0 and chunk_idx > 0:
                    if chunk_phase == "expand":
                        pct = 15.0 + min(5.0, (chunk_idx / chunk_total) * 5.0)
                    else:
                        pct = 8.0 + min(7.0, (chunk_idx / chunk_total) * 7.0)
                if chunk_idx > 0 and chunk_total > 0:
                    if chunk_phase == "expand":
                        message = (
                            f"Ticks uitbreiden: {chunk_idx:,}/{chunk_total:,} bars "
                            f"({bars_loaded:,} merged)"
                        )
                    else:
                        message = (
                            f"Historische data laden: chunk {chunk_idx}/{chunk_total} "
                            f"({bars_loaded:,} bars)"
                        )
                else:
                    message = f"Historische data laden ({max_days} dagen)…"
                write_birth_progress(
                    host.workspace_root,
                    stage="loading_data",
                    phase="loading_history",
                    message=message,
                    progress_pct=pct,
                    cumulative_trades=host.cumulative_trades if resume else 0,
                    target_trades=cfg.trade_budget_cap,
                    birth_start_time=host.birth_start_time,
                    training_mode=training_mode,
                    ppo_steps=host.ppo_steps if resume else 0,
                    loading_chunk=chunk_idx,
                    chunk_total=chunk_total,
                    bars_loaded=bars_loaded,
                    chunk_phase=chunk_phase,
                )

            ticks = load_historical_ticks(
                market_data_service=host.market_data_service,
                runtime=host.runtime,
                days_back=max_days,
                limit=None,
                on_chunk=_history_chunk_progress,
            )
            if host._stop_requested():
                return BirthDataPrepareResult(
                    ticks=[],
                    split=None,
                    early_return={
                        "status": "paused",
                        "total_trades": 0,
                        "ppo_steps": 0,
                        "training_mode": training_mode,
                    },
                )
            self.write_data_prep_progress(
                phase="enriching_news",
                message=f"Historische data geladen ({len(ticks):,} ticks) — news enrichment…",
                progress_pct=20.5,
                training_mode=training_mode,
            )

        if not ticks and not prefer_real:
            ticks = generate_synthetic_ticks(max(20_000, max_days * 1000), start_price=5000.0)
        elif not ticks and prefer_real and practice_mode:
            ticks = generate_synthetic_ticks(20_000, start_price=5000.0)
        elif not ticks and prefer_real and allow_minimal_synthetic:
            logger.info("birth.synthetic.minimal_fallback reason=allow_minimal_synthetic_fallback")
            ticks = generate_synthetic_ticks(20_000, start_price=5000.0)
        elif not ticks:
            write_birth_progress(
                host.workspace_root,
                stage="history_unavailable",
                phase="loading_history_failed",
                message="Geen historische data beschikbaar.",
                progress_pct=100.0,
                cumulative_trades=0,
                target_trades=cfg.trade_budget_cap,
                birth_start_time=host.birth_start_time,
                retryable=True,
            )
            host._notify_history_unavailable("Geen historische data beschikbaar.")
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

        if ticks and not host._last_raw_ticks_hash:
            host._last_raw_ticks_hash = compute_ticks_fingerprint(ticks)
        if resume_skip_load:
            host._last_raw_ticks_hash = str(
                host._data_manifest.get("raw_ticks_hash", "")
                or host._last_raw_ticks_hash
                or compute_ticks_fingerprint(ticks)
            )

        if resume_reenrich_only and split is not None:
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

        if split is None:
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
        elif not ticks:
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
            resume_cache_decision=resume_cache_decision,
            resume_skip_load=resume_skip_load,
            resume_reenrich_only=resume_reenrich_only,
        )