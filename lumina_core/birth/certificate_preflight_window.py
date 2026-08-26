"""Training-window SLA + cache finalize for certificate preflight."""
from __future__ import annotations

from typing import Any

from lumina_core.birth.certificate_patch_bridge import cp_attr
from lumina_core.birth.data_expansion import expand_birth_data
from lumina_core.birth.foundation_history import (
    apply_expansion_history_manifest,
    history_depth_fail_message,
)
from lumina_core.birth.history_loader import actual_calendar_days_from_ticks
from lumina_core.birth.news_enricher import enrich_ticks_with_news
from lumina_core.birth.preflight import data_manifest_from_split
from lumina_core.birth.progress import write_birth_progress
from lumina_core.birth.tick_cache_persist import compute_ticks_fingerprint, save_birth_data_cache
from lumina_core.birth.training_window_sla import training_window_sla_ok, training_window_sla_report
from lumina_core.logging_utils import get_logger
from lumina_core.rl.trend_features import ENRICH_VERSION

logger = get_logger("lumina.birth.certificate_preflight")


def apply_training_window_sla(
    pipeline: Any,
    *,
    active_ticks: list[dict[str, Any]],
    active_split: Any,
    actual_days: int,
    requested_days: int,
    expansion_step: int,
    expansion_steps: list[int],
    max_attempts: int,
    attempts: int,
    prefer_real: bool,
    start_price: float,
    training_mode: str,
    max_days: int,
    req_inst: str,
    res_inst: str,
    rolled: bool,
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], Any, dict[str, Any], int] | dict[str, Any]:
    """Expand until SLA vs this load's requested days, or fail-closed."""
    news_cfg = pipeline._host.birth_config.news
    min_ratio = float(getattr(pipeline._host.birth_config, "training_window_min_ratio", 0.95) or 0.95)
    allow_degraded = bool(getattr(pipeline._host.birth_config, "allow_degraded_data_mode", False))
    sla = training_window_sla_report(
        days_loaded=actual_days,
        requested_days=requested_days,
        min_ratio=min_ratio,
        degraded_data_mode=False,
    )
    manifest["training_window_sla"] = sla
    if training_window_sla_ok(
        days_loaded=actual_days,
        requested_days=requested_days,
        min_ratio=min_ratio,
        degraded_data_mode=False,
    ):
        return active_ticks, active_split, manifest, actual_days

    while attempts < max_attempts:
        attempts += 1
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
                else lambda n, p: pipeline._host._generate_synthetic_ticks(
                    n, start_price=p or start_price
                )
            ),
            start_price=start_price,
            max_real_days=max_days,
        )
        expansion_step = expanded.step_index
        load_failed = bool(getattr(expanded, "load_failed", False)) or not expanded.train_ticks
        if load_failed or not expanded.train_ticks:
            if expanded.exhausted:
                break
            continue
        if expanded.exhausted and len(expanded.train_ticks) <= len(active_split.train):
            break
        active_ticks = list(expanded.all_ticks)
        active_split = expanded.split
        pipeline._host._real_data_pct = expanded.real_data_pct
        actual_days = actual_calendar_days_from_ticks(active_ticks)
        apply_expansion_history_manifest(
            pipeline._host._data_manifest,
            expanded,
            days_loaded=actual_days,
        )
        requested_days = max(
            int(requested_days),
            int(getattr(expanded, "requested_days", 0) or 0),
        )
        if training_window_sla_ok(
            days_loaded=actual_days,
            requested_days=requested_days,
            min_ratio=min_ratio,
            degraded_data_mode=False,
        ):
            break
        if expanded.exhausted:
            break

    sla = training_window_sla_report(
        days_loaded=actual_days,
        requested_days=requested_days,
        min_ratio=min_ratio,
        degraded_data_mode=False,
    )
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
        stitched=bool(host_m.get("stitched", manifest.get("stitched"))),
        instruments=host_m.get("instruments", manifest.get("instruments")),
        stitched_from=host_m.get("stitched_from", manifest.get("stitched_from")),
    )
    manifest["training_window_sla"] = sla
    if sla["ok"]:
        return active_ticks, active_split, manifest, actual_days
    if allow_degraded:
        logger.warning(
            "birth.preflight.training_window_sla_degraded requested=%s actual=%s ratio=%.3f",
            requested_days,
            actual_days,
            float(sla.get("ratio") or 0.0),
        )
        manifest["degraded_data_mode"] = True
        manifest["depth_thin_warning"] = True
        manifest["stage2_entry_blocked"] = False
        write_birth_progress(
            pipeline._host.workspace_root,
            stage="historical_loaded",
            phase="data_window_degraded",
            message=(
                f"Training window degraded: {actual_days}/{requested_days} days "
                f"(min ratio {min_ratio:.0%}). Stage 2 on thin data is loud — expand preferred."
            ),
            progress_pct=24.0,
            cumulative_trades=0,
            target_trades=pipeline._host.birth_config.trade_budget_cap,
            birth_start_time=pipeline._host.birth_start_time,
            needs_attention=True,
            attention_reason_code="training_window_shortfall",
            attention_summary=(
                f"Loaded {actual_days}/{requested_days} calendar days "
                f"(ratio {float(sla.get('ratio') or 0):.1%}, SLA {min_ratio:.0%})."
            ),
            attention_recommended_actions=["expand_data", "wipe_and_retry"],
            data_manifest=manifest,
            retryable=True,
        )
        return active_ticks, active_split, manifest, actual_days

    msg = history_depth_fail_message(
        requested_days=requested_days,
        actual_days=actual_days,
        instruments=manifest.get("instruments"),
        stitched_from=manifest.get("stitched_from"),
        min_ratio=min_ratio,
    )
    logger.error("birth.preflight.training_window_sla_failed %s", msg)
    write_birth_progress(
        pipeline._host.workspace_root,
        stage="history_unavailable",
        phase="training_window_sla_failed",
        message=msg,
        progress_pct=100.0,
        cumulative_trades=0,
        target_trades=pipeline._host.birth_config.trade_budget_cap,
        birth_start_time=pipeline._host.birth_start_time,
        needs_attention=True,
        attention_reason_code="training_window_shortfall",
        attention_summary=msg,
        attention_recommended_actions=["expand_data", "wipe_and_retry", "human_review"],
        data_manifest=manifest,
        preflight_report={
            "ok": False,
            "failure_reasons": ["training_window_shortfall"],
            "training_window_sla": sla,
        },
        retryable=True,
    )
    pipeline._host._notify_history_unavailable(msg)
    return {
        "status": "history_unavailable",
        "total_trades": 0,
        "ppo_steps": 0,
        "training_mode": training_mode,
        "preflight": ["training_window_shortfall"],
        "training_window_sla": sla,
    }


def finalize_preflight_manifest(
    pipeline: Any,
    *,
    active_ticks: list[dict[str, Any]],
    active_split: Any,
    manifest: dict[str, Any],
    requested_days: int,
    actual_days: int,
    preflight: Any,
) -> dict[str, Any]:
    manifest["preflight_ok"] = True
    manifest["holdout_regimes"] = list(preflight.holdout_regimes)
    manifest["raw_ticks_hash"] = str(pipeline._host._last_raw_ticks_hash or "")
    manifest["enrich_version"] = ENRICH_VERSION
    manifest["holdout_pct"] = float(pipeline._host.birth_config.holdout_pct)
    host_m = dict(getattr(pipeline._host, "_data_manifest", {}) or {})
    for key in ("stitched", "instruments", "stitched_from"):
        if key in host_m:
            manifest[key] = host_m[key]
    cache_paths = save_birth_data_cache(
        pipeline._host.workspace_root,
        ticks=active_ticks,
        split=active_split,
        holdout_pct=pipeline._host.birth_config.holdout_pct,
        raw_ticks_hash=str(pipeline._host._last_raw_ticks_hash or compute_ticks_fingerprint(active_ticks)),
        train_hash=str(manifest.get("train_hash", "") or ""),
        enrich_version=ENRICH_VERSION,
        requested_days=requested_days,
        actual_calendar_days=actual_days,
        instruments=manifest.get("instruments"),
        stitched=bool(manifest.get("stitched")),
        stitched_from=manifest.get("stitched_from"),
    )
    manifest.update(cache_paths)
    return manifest
