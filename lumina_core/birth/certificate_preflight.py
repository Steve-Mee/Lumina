"""Holdout preflight expansion for birth certificate pipeline."""
from __future__ import annotations

from lumina_core.birth.certificate_patch_bridge import cp_attr

from typing import Any

from lumina_core.birth.certificate_preflight_window import (
    apply_training_window_sla,
    finalize_preflight_manifest,
)
from lumina_core.birth.data_expansion import clamp_expansion_steps, expand_birth_data
from lumina_core.birth.foundation_history import history_window_meets_sla, sla_requested_days
from lumina_core.birth.history_loader import actual_calendar_days_from_ticks
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.preflight import assess_split_preflight, data_manifest_from_split
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.remediation import manifest_train_hash_matches
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.certificate_preflight")


def ensure_holdout_preflight(
    pipeline,
    *,
    ticks: list[dict[str, Any]],
    split: Any,
    max_days: int,
    prefer_real: bool,
    start_price: float,
    training_mode: str,
    reuse_manifest: bool = False,
    saved_manifest: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], Any, dict[str, Any]] | dict[str, Any]:
    """Expand history until holdout preflight passes or fail closed."""
    cur_cfg = pipeline._host.birth_config.curriculum
    news_cfg = pipeline._host.birth_config.news
    active_ticks = list(ticks)
    active_split = split
    current_hash = pipeline._host._train_hash(active_split.train)
    if reuse_manifest and manifest_train_hash_matches(
        current_hash=current_hash,
        saved_manifest=saved_manifest,
    ):
        preflight = cp_attr("assess_split_preflight", assess_split_preflight)(
            active_split,
            thresholds=pipeline._host.birth_config.certificate_thresholds,
        )
        if preflight.ok:
            actual_days = actual_calendar_days_from_ticks(active_ticks)
            if not history_window_meets_sla(
                actual_days=actual_days,
                manifest=saved_manifest,
            ):
                logger.warning(
                    "birth.preflight.reuse_rejected_thin_window actual=%s requested=%s",
                    actual_days,
                    sla_requested_days(saved_manifest),
                )
            else:
                manifest = dict(saved_manifest or {})
                manifest.update(
                    data_manifest_from_split(
                        active_split,
                        days_loaded=max(1, actual_days),
                        real_data_pct=pipeline._host._real_data_pct,
                        train_hash=current_hash,
                        actual_calendar_days=actual_days,
                        requested_days=sla_requested_days(saved_manifest),
                        stitched=bool(manifest.get("stitched")),
                        instruments=manifest.get("instruments"),
                        stitched_from=manifest.get("stitched_from"),
                    )
                )
                manifest["preflight_ok"] = True
                manifest["holdout_regimes"] = list(preflight.holdout_regimes)
                manifest["reused_manifest"] = True
                return active_ticks, active_split, manifest
    expansion_step = 0
    preflight = cp_attr("assess_split_preflight", assess_split_preflight)(
        active_split,
        thresholds=pipeline._host.birth_config.certificate_thresholds,
    )
    max_days = int(pipeline._host.birth_config.max_real_days)
    expansion_steps = clamp_expansion_steps(
        list(cur_cfg.data_expansion_steps),
        max_real_days=max_days,
    )
    max_attempts = max(1, len(expansion_steps))
    attempts = 0
    while not preflight.ok and attempts < max_attempts:
        attempts += 1
        prev_regimes = len(preflight.holdout_regimes)
        expanded = cp_attr("expand_birth_data", expand_birth_data)(
            market_data_service=pipeline._host.market_data_service,
            runtime=pipeline._host.runtime,
            current_step=expansion_step + 1,
            expansion_steps=expansion_steps,
            holdout_pct=pipeline._host.birth_config.holdout_pct,
            enrich_news_fn=lambda rows: cp_attr("enrich_ticks_with_news", enrich_ticks_with_news)(
                rows,
                workspace_root=pipeline._host.workspace_root,
                primary=news_cfg.primary,
                enable_cache=news_cfg.enable_cache,
                cache_path=news_cfg.cache_path,
            ),
            synthetic_fallback_fn=(
                None
                if prefer_real
                else lambda n, p: pipeline._host._generate_synthetic_ticks(n, start_price=p or start_price)
            ),
            start_price=start_price,
            max_real_days=max_days,
        )
        expansion_step = expanded.step_index
        load_failed = bool(getattr(expanded, "load_failed", False)) or not expanded.train_ticks
        # Never clobber a non-empty split with an empty expansion result.
        if load_failed or not expanded.train_ticks:
            if expanded.exhausted or attempts >= max_attempts:
                write_birth_progress(
                    pipeline._host.workspace_root,
                    stage="history_unavailable",
                    phase="holdout_preflight_failed",
                    message=(
                        preflight.message
                        or (
                            "History load failed during holdout preflight expansion "
                            f"(0 bars for {int(expanded.requested_days or expanded.days_back or 0)}d)."
                        )
                    ),
                    progress_pct=100.0,
                    cumulative_trades=0,
                    target_trades=pipeline._host.birth_config.trade_budget_cap,
                    birth_start_time=pipeline._host.birth_start_time,
                    preflight_report={
                        "ok": False,
                        "failure_reasons": list(preflight.failure_reasons)
                        or ["history_load_failed"],
                        "holdout_regimes": list(preflight.holdout_regimes),
                    },
                    retryable=True,
                    attention_recommended_actions=[
                        "check_fabric_nt8",
                        "check_mds_connection",
                        "resume_from_checkpoint",
                        "wipe_and_retry",
                    ],
                )
                pipeline._host._notify_history_unavailable(
                    preflight.message or "Holdout preflight failed (history load empty)."
                )
                return {
                    "status": "history_unavailable",
                    "total_trades": 0,
                    "ppo_steps": 0,
                    "training_mode": training_mode,
                    "preflight": preflight.failure_reasons or ["history_load_failed"],
                }
            # Intermediate rung failed empty — try next without wiping active_*.
            continue
        if expanded.exhausted and len(expanded.train_ticks) <= len(active_split.train):
            write_birth_progress(
                pipeline._host.workspace_root,
                stage="history_unavailable",
                phase="holdout_preflight_failed",
                message=preflight.message,
                progress_pct=100.0,
                cumulative_trades=0,
                target_trades=pipeline._host.birth_config.trade_budget_cap,
                birth_start_time=pipeline._host.birth_start_time,
                preflight_report={
                    "ok": False,
                    "failure_reasons": list(preflight.failure_reasons),
                    "holdout_regimes": list(preflight.holdout_regimes),
                },
                retryable=True,
            )
            pipeline._host._notify_history_unavailable(preflight.message or "Holdout preflight failed.")
            return {
                "status": "history_unavailable",
                "total_trades": 0,
                "ppo_steps": 0,
                "training_mode": training_mode,
                "preflight": preflight.failure_reasons,
            }
        active_ticks = list(expanded.all_ticks)
        active_split = expanded.split
        pipeline._host._real_data_pct = expanded.real_data_pct
        preflight = cp_attr("assess_split_preflight", assess_split_preflight)(
            active_split,
            thresholds=pipeline._host.birth_config.certificate_thresholds,
        )
        write_birth_progress(
            pipeline._host.workspace_root,
            stage="historical_loaded",
            phase="holdout_preflight_expansion",
            message=(
                f"Holdout preflight expansion: {len(preflight.holdout_regimes)} regimes, "
                f"{preflight.holdout_tick_count:,} holdout ticks"
            ),
            progress_pct=min(24.0, 21.0 + float(attempts)),
            cumulative_trades=0,
            target_trades=pipeline._host.birth_config.trade_budget_cap,
            birth_start_time=pipeline._host.birth_start_time,
            preflight_report={
                "ok": preflight.ok,
                "failure_reasons": list(preflight.failure_reasons),
                "holdout_regimes": list(preflight.holdout_regimes),
            },
        )
        if preflight.ok:
            break
        if len(preflight.holdout_regimes) <= prev_regimes and expanded.exhausted:
            break

    if not preflight.ok:
        write_birth_progress(
            pipeline._host.workspace_root,
            stage="history_unavailable",
            phase="holdout_preflight_failed",
            message=preflight.message,
            progress_pct=100.0,
            cumulative_trades=0,
            target_trades=pipeline._host.birth_config.trade_budget_cap,
            birth_start_time=pipeline._host.birth_start_time,
            preflight_report={
                "ok": False,
                "failure_reasons": list(preflight.failure_reasons),
                "holdout_regimes": list(preflight.holdout_regimes),
            },
            retryable=True,
        )
        pipeline._host._notify_history_unavailable(preflight.message or "Holdout preflight exhausted.")
        return {
            "status": "history_unavailable",
            "total_trades": 0,
            "ppo_steps": 0,
            "training_mode": training_mode,
            "preflight": preflight.failure_reasons,
        }

    actual_days = actual_calendar_days_from_ticks(active_ticks)
    requested_days = sla_requested_days(getattr(pipeline._host, "_data_manifest", None))
    mds = pipeline._host.market_data_service
    req_inst = str(getattr(mds, "last_requested_instrument", "") or "")
    res_inst = str(getattr(mds, "last_resolved_instrument", "") or "")
    rolled = bool(req_inst and res_inst and req_inst != res_inst)
    host_m = dict(getattr(pipeline._host, "_data_manifest", {}) or {})
    manifest = data_manifest_from_split(
        active_split,
        days_loaded=max(1, actual_days),
        real_data_pct=pipeline._host._real_data_pct,
        train_hash=pipeline._host._train_hash(active_split.train),
        requested_days=requested_days,
        actual_calendar_days=actual_days,
        requested_instrument=req_inst,
        resolved_instrument=res_inst,
        rolled=rolled,
        stitched=bool(host_m.get("stitched")),
        instruments=host_m.get("instruments"),
        stitched_from=host_m.get("stitched_from"),
    )
    if actual_days > 0 and actual_days < max(7, int(requested_days * 0.5)):
        logger.warning(
            "birth.preflight.depth_thin requested=%s actual=%s",
            requested_days,
            actual_days,
        )
        manifest["depth_thin_warning"] = True

    sla_result = apply_training_window_sla(
        pipeline,
        active_ticks=active_ticks,
        active_split=active_split,
        actual_days=actual_days,
        requested_days=requested_days,
        expansion_step=expansion_step,
        expansion_steps=expansion_steps,
        max_attempts=max_attempts,
        attempts=attempts,
        prefer_real=prefer_real,
        start_price=start_price,
        training_mode=training_mode,
        max_days=max_days,
        req_inst=req_inst,
        res_inst=res_inst,
        rolled=rolled,
        manifest=manifest,
    )
    if isinstance(sla_result, dict):
        return sla_result
    active_ticks, active_split, manifest, actual_days = sla_result
    manifest = finalize_preflight_manifest(
        pipeline,
        active_ticks=active_ticks,
        active_split=active_split,
        manifest=manifest,
        requested_days=requested_days,
        actual_days=actual_days,
        preflight=preflight,
    )
    return active_ticks, active_split, manifest
