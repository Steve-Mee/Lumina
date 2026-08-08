"""Birth phase data preparation, preflight, and policy initialization."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.birth.birth_phase_bootstrap import BirthPhaseBootstrap
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.stage_scorecard import compute_regime_distribution
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.birth_phase_data_policy")


@dataclass(slots=True)
class BirthPhaseDataReady:
    ticks: list
    split: Any
    start_price: float
    early_return: dict[str, Any] | None = None
    # checkpoint_phase may be repaired from progress during this step
    checkpoint_phase: str = ""


def prepare_birth_data_and_policy(
    host: Any,
    boot: BirthPhaseBootstrap,
) -> BirthPhaseDataReady:
    cfg = boot.cfg
    training_mode = boot.training_mode
    resume = boot.resume
    max_days = boot.max_days
    prefer_real = boot.prefer_real
    practice_mode = boot.practice_mode
    allow_minimal_synthetic = boot.allow_minimal_synthetic
    allow_load = boot.allow_load
    resume_policy_path = boot.resume_policy_path
    progress_snapshot = boot.progress_snapshot
    checkpoint_phase = boot.checkpoint_phase
    data_prep = host._data_pipeline().prepare_ticks_and_split(
        cfg=cfg,
        max_days=max_days,
        prefer_real=prefer_real,
        practice_mode=practice_mode,
        allow_minimal_synthetic=allow_minimal_synthetic,
        resume=resume,
        training_mode=training_mode,
    )
    if data_prep.early_return is not None:
        return BirthPhaseDataReady(ticks=[], split=None, start_price=0.0, early_return=data_prep.early_return)
    ticks = data_prep.ticks
    split = data_prep.split
    resume_cache_decision = data_prep.resume_cache_decision
    resume_skip_load = data_prep.resume_skip_load
    _ = data_prep.resume_reenrich_only

    preflight_result = host._ensure_holdout_preflight(
        ticks=ticks,
        split=split,
        max_days=max_days,
        prefer_real=prefer_real,
        start_price=float(ticks[-1].get("last", 5000.0) or 5000.0) if ticks else 5000.0,
        training_mode=training_mode,
        reuse_manifest=bool(resume and host._data_manifest),
        saved_manifest=host._data_manifest if resume else None,
    )
    if isinstance(preflight_result, dict):
        return BirthPhaseDataReady(ticks=[], split=None, start_price=0.0, early_return=preflight_result)
    ticks, split, host._data_manifest = preflight_result

    write_birth_progress(
        host.workspace_root,
        stage="historical_loaded",
        phase="ticks_ready",
        message=(
            f"Data geladen: {len(ticks):,} ticks, holdout {split.holdout_days} dagen, "
            f"regimes {','.join(host._data_manifest.get('holdout_regimes', []))}."
        ),
        progress_pct=25.0,
        cumulative_trades=host.cumulative_trades if resume else 0,
        target_trades=cfg.trade_budget_cap,
        birth_start_time=host.birth_start_time,
        ppo_steps=host.ppo_steps if resume else 0,
        actual_real_days_loaded=max(
            1,
            int(
                (host._data_manifest or {}).get("actual_calendar_days")
                or (host._data_manifest or {}).get("days_loaded")
                or 1
            ),
        ),
        real_data_pct=host._real_data_pct,
        preflight_report={
            "ok": True,
            "holdout_regimes": host._data_manifest.get("holdout_regimes", []),
        },
        data_manifest=host._data_manifest,
        regime_distribution=compute_regime_distribution(ticks),
        resume_cache_tier=(
            resume_cache_decision.tier.value
            if resume_cache_decision and resume_skip_load
            else ""
        ),
    )

    from lumina_core.notifications.milestone_events import (
        history_loaded_event,
        regime_map_ready_event,
    )

    host._notify_milestone(
        history_loaded_event(
            tick_count=len(ticks),
            real_data_pct=host._real_data_pct,
            max_real_days=max_days,
        )
    )
    host._notify_milestone(
        regime_map_ready_event(
            tick_count=len(ticks),
            train_bars=len(split.train),
            holdout_bars=len(split.holdout),
            holdout_days=int(split.holdout_days),
            real_data_pct=host._real_data_pct,
        )
    )

    host._write_data_prep_progress(
        phase="policy_init",
        message="Birth policy initialiseren…",
        progress_pct=26.0,
        training_mode=training_mode,
    )
    host.current_policy = host._create_birth_policy(
        allow_load_existing=allow_load and resume,
        policy_path=resume_policy_path or None,
    )
    start_price = float(ticks[-1].get("last", 5000.0) or 5000.0) if ticks else 5000.0

    if resume and not checkpoint_phase:
        progress_phase = str(progress_snapshot.get("phase", "") or "").strip().lower()
        if progress_phase in {"certificate_failed", "certificate_remediation"}:
            checkpoint_phase = progress_phase
            if not host._stages_passed:
                host._stages_passed = list(progress_snapshot.get("stages_passed") or [])
            host._remediation_attempt = max(
                host._remediation_attempt,
                int(progress_snapshot.get("remediation_attempt", 0) or 0),
            )
            if not host._data_manifest:
                manifest = progress_snapshot.get("data_manifest")
                if isinstance(manifest, dict):
                    host._data_manifest = dict(manifest)

    return BirthPhaseDataReady(
        ticks=ticks,
        split=split,
        start_price=start_price,
        checkpoint_phase=checkpoint_phase,
    )
