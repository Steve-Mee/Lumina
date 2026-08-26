"""Cold history load + synthetic fallback for birth data pipeline (M5)."""

from __future__ import annotations

from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.data_pipeline_types import (
    BirthDataPipelineHost,
    BirthDataPrepareResult,
    generate_synthetic_ticks,
)
from lumina_core.birth.foundation_history import (
    apply_foundation_history_manifest,
    history_depth_fail_message,
    load_foundation_history_ticks,
    resolve_reload_history_days,
)
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.data_pipeline")


def _load_historical_ticks(**kwargs: Any) -> Any:
    """Late-bound via façade so tests can monkeypatch data_pipeline.load_historical_ticks."""
    from lumina_core.birth import data_pipeline as _facade

    return _facade.load_historical_ticks(**kwargs)


def _write_birth_progress(*args: Any, **kwargs: Any) -> Any:
    """Late-bound via façade so tests can monkeypatch data_pipeline.write_birth_progress."""
    from lumina_core.birth import data_pipeline as _facade

    return _facade.write_birth_progress(*args, **kwargs)


class BirthDataPipelineLoadMixin:
    """Load historical ticks (or synthetic) when resume cache misses."""

    _host: BirthDataPipelineHost

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
            # Preserve checkpoint counters on resume cold-load (never flash 0 trades).
            cumulative_trades=int(getattr(self._host, "cumulative_trades", 0) or 0),
            target_trades=self._host.birth_config.trade_budget_cap,
            ppo_steps=int(getattr(self._host, "ppo_steps", 0) or 0),
            birth_start_time=self._host.birth_start_time,
            extra_parts=(kwargs,),
        )

    def _load_ticks_cold(
        self,
        *,
        cfg: BirthCurriculumConfig,
        max_days: int,
        prefer_real: bool,
        practice_mode: bool,
        allow_minimal_synthetic: bool,
        resume: bool,
        training_mode: str,
        resume_cache_decision: Any | None,
    ) -> BirthDataPrepareResult | list[dict[str, Any]]:
        """Return early BirthDataPrepareResult or loaded tick list."""
        host = self._host
        days_back = resolve_reload_history_days(host._data_manifest, ceiling=max_days)
        loading_message = (
            resume_cache_decision.resume_message
            if resume and resume_cache_decision and resume_cache_decision.resume_message
            else (
                "Checkpoint hervat — data opnieuw voorbereid (curriculum gaat verder, geen wipe)."
                if resume
                else f"Historische data laden ({days_back} dagen)…"
            )
        )
        _write_birth_progress(
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
                message = f"Historische data laden ({days_back} dagen)…"
            _write_birth_progress(
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

        loaded = load_foundation_history_ticks(
            market_data_service=host.market_data_service,
            runtime=host.runtime,
            days_back=days_back,
            load_fn=_load_historical_ticks,
            on_chunk=_history_chunk_progress,
        )
        apply_foundation_history_manifest(host._data_manifest, loaded)
        ticks = list(loaded.ticks)
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
            fail_msg = history_depth_fail_message(
                requested_days=loaded.requested_days,
                actual_days=loaded.actual_calendar_days,
                instruments=loaded.instruments,
                stitched_from=loaded.stitched_from,
            )
            _write_birth_progress(
                host.workspace_root,
                stage="history_unavailable",
                phase="loading_history_failed",
                message=fail_msg,
                progress_pct=100.0,
                cumulative_trades=0,
                target_trades=cfg.trade_budget_cap,
                birth_start_time=host.birth_start_time,
                retryable=True,
                data_manifest=dict(host._data_manifest),
            )
            host._notify_history_unavailable(fail_msg)
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
        return ticks


__all__ = ["BirthDataPipelineLoadMixin"]
