"""Birth tick-cache resume classification (T0–T4)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from lumina_core.birth.foundation_history import (
    FOUNDATION_HISTORY_MIN_RATIO,
    foundation_history_start_days,
)


def manifest_train_hash_matches(
    *,
    current_hash: str,
    saved_manifest: dict[str, Any] | None,
) -> bool:
    if not saved_manifest:
        return False
    saved = str(saved_manifest.get("train_hash", "") or "").strip()
    current = str(current_hash or "").strip()
    return bool(saved and current and saved == current)


class ResumeCacheTier(str, Enum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"
    T4 = "T4"


@dataclass(slots=True)
class ResumeCacheDecision:
    tier: ResumeCacheTier
    reason: str
    skip_load: bool = False
    skip_split: bool = False
    skip_enrich: bool = True
    repair_manifest: bool = False
    resume_message: str = ""


def _norm_symbol(raw: Any) -> str:
    return " ".join(str(raw or "").strip().upper().split())


def cache_instrument_chain_matches(
    cache_instruments: Any,
    current_instrument: str,
) -> bool:
    """True when the current front month is in the cached stitch chain."""
    chain = [_norm_symbol(item) for item in (cache_instruments or []) if _norm_symbol(item)]
    if not chain:
        return False
    current = _norm_symbol(current_instrument)
    if not current:
        return True
    return current in chain


def classify_cache_resume_tier(
    *,
    checkpoint_manifest: dict[str, Any],
    cache_manifest: dict[str, Any] | None,
    cached_ticks: list[dict[str, Any]],
    cached_split: Any | None,
    cached_train_hash: str,
    holdout_pct: float,
    enrich_version: str,
    current_instrument: str = "",
) -> ResumeCacheDecision:
    """Classify resume cache tier (T0–T4) for fail-closed data-prep decisions."""
    if not cached_ticks or cached_split is None:
        return ResumeCacheDecision(
            tier=ResumeCacheTier.T4,
            reason="missing_cache_files",
            resume_message="Checkpoint hervat — data opnieuw voorbereid (curriculum gaat verder, geen wipe).",
        )

    manifest = dict(cache_manifest or {})
    manifest_holdout = float(manifest.get("holdout_pct", holdout_pct) or holdout_pct)
    if abs(manifest_holdout - float(holdout_pct)) > 1e-6:
        return ResumeCacheDecision(
            tier=ResumeCacheTier.T4,
            reason="holdout_pct_changed",
            resume_message=(
                "Checkpoint hervat — holdout-config gewijzigd; data opnieuw voorbereid "
                "(curriculum gaat verder, geen wipe)."
            ),
        )

    try:
        cached_requested = int(manifest.get("requested_days") or 0)
    except (TypeError, ValueError):
        cached_requested = 0
    if cached_requested < foundation_history_start_days():
        return ResumeCacheDecision(
            tier=ResumeCacheTier.T4,
            reason="requested_days_mismatch",
            resume_message=(
                "Checkpoint hervat — history-venster te dun of verouderd; data opnieuw geladen "
                "(curriculum gaat verder, geen wipe)."
            ),
        )

    try:
        cached_actual = int(manifest.get("actual_calendar_days") or 0)
    except (TypeError, ValueError):
        cached_actual = 0
    need = max(1, int(round(cached_requested * FOUNDATION_HISTORY_MIN_RATIO)))
    if cached_actual < need:
        return ResumeCacheDecision(
            tier=ResumeCacheTier.T4,
            reason="history_depth_thin",
            resume_message=(
                "Checkpoint hervat — cached tape dunner dan de Foundation-sport; data opnieuw geladen "
                "(curriculum gaat verder, geen wipe)."
            ),
        )

    current = str(current_instrument or "").strip() or str(
        checkpoint_manifest.get("resolved_instrument")
        or checkpoint_manifest.get("requested_instrument")
        or ""
    )
    if not cache_instrument_chain_matches(manifest.get("instruments"), current):
        return ResumeCacheDecision(
            tier=ResumeCacheTier.T4,
            reason="instrument_chain_mismatch",
            resume_message=(
                "Checkpoint hervat — instrument-keten wijkt af van de huidige front month; "
                "data opnieuw geladen (curriculum gaat verder, geen wipe)."
            ),
        )

    cache_train_hash = str(manifest.get("train_hash", "") or cached_train_hash or "").strip()
    hash_matches_checkpoint = manifest_train_hash_matches(
        current_hash=cached_train_hash,
        saved_manifest=checkpoint_manifest,
    )
    hash_matches_cache_file = bool(
        cache_train_hash and cached_train_hash and cache_train_hash == cached_train_hash
    )
    cache_enrich_version = str(manifest.get("enrich_version", enrich_version) or enrich_version).strip()
    enrich_version_match = cache_enrich_version == str(enrich_version).strip()

    if hash_matches_checkpoint and enrich_version_match:
        return ResumeCacheDecision(
            tier=ResumeCacheTier.T0,
            reason="full_cache_hit",
            skip_load=True,
            skip_split=True,
            skip_enrich=True,
            resume_message="Checkpoint hervat — cached data geladen (curriculum gaat verder).",
        )

    if hash_matches_cache_file and not hash_matches_checkpoint:
        return ResumeCacheDecision(
            tier=ResumeCacheTier.T1,
            reason="manifest_repair",
            skip_load=True,
            skip_split=True,
            skip_enrich=True,
            repair_manifest=True,
            resume_message="Checkpoint hervat — cache hersteld (curriculum gaat verder).",
        )

    if hash_matches_checkpoint and not enrich_version_match:
        return ResumeCacheDecision(
            tier=ResumeCacheTier.T2,
            reason="enrich_version_mismatch",
            skip_load=True,
            skip_split=True,
            skip_enrich=False,
            resume_message=(
                "Checkpoint hervat — regime-map herberekend (algo update); "
                "curriculum gaat verder."
            ),
        )

    if hash_matches_checkpoint:
        return ResumeCacheDecision(
            tier=ResumeCacheTier.T3,
            reason="partial_cache_inconsistency",
            resume_message=(
                "Checkpoint hervat — data opnieuw voorbereid (curriculum gaat verder, geen wipe)."
            ),
        )

    checkpoint_count = int(checkpoint_manifest.get("train_tick_count", 0) or 0)
    cache_count = len(getattr(cached_split, "train", []) or [])
    if checkpoint_count > 0 and cache_count > 0 and checkpoint_count != cache_count:
        return ResumeCacheDecision(
            tier=ResumeCacheTier.T4,
            reason="train_cardinality_changed",
            resume_message=(
                "Checkpoint hervat — nieuwe marktdata gedetecteerd; holdout opnieuw berekend "
                "(curriculum gaat verder, geen wipe)."
            ),
        )

    return ResumeCacheDecision(
        tier=ResumeCacheTier.T4,
        reason="train_hash_mismatch",
        resume_message=(
            "Checkpoint hervat — nieuwe marktdata gedetecteerd; holdout opnieuw berekend "
            "(curriculum gaat verder, geen wipe)."
        ),
    )
