"""Reason-specific certificate remediation planning (BRO v2 PR-O)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.remediation")


class RemediationAction(str, Enum):
    REGIME_EXPAND = "regime_expand"
    HOLDOUT_ACTIVITY = "holdout_activity"
    SHARPE_POLISH = "sharpe_polish"
    GENERIC_EXPLORE = "generic_explore"


@dataclass(frozen=True, slots=True)
class RemediationPlan:
    action: RemediationAction
    label: str
    explore_multiplier: int = 2
    rollout_target_trades: int = 150
    ppo_timesteps: int = 3_000
    expand_data: bool = False


_REASON_PRIORITY: tuple[str, ...] = (
    "regimes_covered",
    "holdout_trades",
    "oos_sharpe",
    "oos_winrate",
    "oos_max_drawdown_pct",
    "real_data_pct",
    "constitution_violations",
)


def parse_failure_reason_keys(failure_reasons: list[str]) -> set[str]:
    keys: set[str] = set()
    for raw in failure_reasons:
        text = str(raw or "").strip()
        if not text:
            continue
        keys.add(text.split(":", 1)[0].strip().lower())
    return keys


def select_remediation_plan(
    failure_reasons: list[str],
    *,
    attempt: int,
    curriculum_ppo_timesteps: int,
    polish_ppo_timesteps: int,
    rollout_chunk_trades: int,
) -> RemediationPlan:
    keys = parse_failure_reason_keys(failure_reasons)
    primary = next((key for key in _REASON_PRIORITY if key in keys), "")

    if primary == "regimes_covered":
        return RemediationPlan(
            action=RemediationAction.REGIME_EXPAND,
            label="Expand train data + regime-diverse rollouts",
            explore_multiplier=3,
            rollout_target_trades=max(100, min(250, rollout_chunk_trades)),
            ppo_timesteps=max(1000, int(curriculum_ppo_timesteps)),
            expand_data=True,
        )
    if primary == "holdout_trades":
        return RemediationPlan(
            action=RemediationAction.HOLDOUT_ACTIVITY,
            label="High-explore rollouts on holdout-volatility train slice",
            explore_multiplier=4,
            rollout_target_trades=max(150, min(300, rollout_chunk_trades * 2)),
            ppo_timesteps=max(1000, int(curriculum_ppo_timesteps)),
        )
    if primary == "oos_sharpe":
        polish_batch = max(1000, int(polish_ppo_timesteps) // max(1, attempt))
        return RemediationPlan(
            action=RemediationAction.SHARPE_POLISH,
            label="Extra PPO polish batch on train trajectories",
            explore_multiplier=1,
            rollout_target_trades=max(80, min(150, rollout_chunk_trades // 2)),
            ppo_timesteps=polish_batch,
        )

    return RemediationPlan(
        action=RemediationAction.GENERIC_EXPLORE,
        label="Generic exploration rollout",
        explore_multiplier=2 + min(2, attempt - 1),
        rollout_target_trades=max(50, min(250, rollout_chunk_trades)),
        ppo_timesteps=max(1000, int(curriculum_ppo_timesteps)),
    )


def holdout_regime_profile(holdout_ticks: list[dict[str, Any]]) -> set[str]:
    out: set[str] = set()
    for tick in holdout_ticks:
        label = str(tick.get("regime", "NEUTRAL") or "NEUTRAL").strip().upper()
        if label:
            out.add(label)
    return out


def filter_train_ticks_for_holdout_profile(
    train_ticks: list[dict[str, Any]],
    holdout_ticks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    profile = holdout_regime_profile(holdout_ticks)
    if not profile:
        return list(train_ticks)
    matched = [
        t
        for t in train_ticks
        if str(t.get("regime", "NEUTRAL") or "NEUTRAL").strip().upper() in profile
    ]
    return matched if len(matched) >= 200 else list(train_ticks)


def select_regime_diverse_train_ticks(
    train_ticks: list[dict[str, Any]],
    *,
    min_regimes: int = 3,
) -> list[dict[str, Any]]:
    if not train_ticks:
        return []
    buckets: dict[str, list[dict[str, Any]]] = {}
    for tick in train_ticks:
        label = str(tick.get("regime", "NEUTRAL") or "NEUTRAL").strip().upper()
        buckets.setdefault(label, []).append(tick)
    if len(buckets) < min_regimes:
        return list(train_ticks)
    per_bucket = max(50, len(train_ticks) // max(min_regimes, len(buckets)))
    out: list[dict[str, Any]] = []
    for label in sorted(buckets.keys()):
        out.extend(buckets[label][:per_bucket])
    return out or list(train_ticks)


def curriculum_stages_complete(stages_passed: list[str]) -> bool:
    required = {"stage1_trend", "stage2_range", "stage3_mixed"}
    return required.issubset(set(stages_passed))


def should_fast_path_remediation(*, checkpoint_phase: str, stages_passed: list[str]) -> bool:
    phase = str(checkpoint_phase or "").strip().lower()
    if phase not in {"certificate_failed", "certificate_remediation"}:
        return False
    return curriculum_stages_complete(stages_passed)


def should_fast_path_from_progress(progress: dict[str, Any]) -> bool:
    """True when progress snapshot indicates cert-fail with completed curriculum."""
    return should_fast_path_remediation_from_state(progress, {})


def _resolve_fast_path_phase(
    progress: dict[str, Any] | None,
    checkpoint: dict[str, Any] | None,
) -> str:
    for source in (progress or {}, checkpoint or {}):
        phase = str(source.get("phase", "") or "").strip().lower()
        if phase in {"certificate_failed", "certificate_remediation"}:
            return phase
    return ""


def _resolve_fast_path_stages(
    progress: dict[str, Any] | None,
    checkpoint: dict[str, Any] | None,
) -> list[str]:
    progress_stages = list((progress or {}).get("stages_passed") or [])
    if curriculum_stages_complete(progress_stages):
        return progress_stages
    checkpoint_stages = list((checkpoint or {}).get("stages_passed") or [])
    if curriculum_stages_complete(checkpoint_stages):
        return checkpoint_stages
    merged = list(dict.fromkeys([*progress_stages, *checkpoint_stages]))
    return merged


def should_fast_path_remediation_from_state(
    progress: dict[str, Any] | None,
    checkpoint: dict[str, Any] | None,
) -> bool:
    """Unified SSOT: cert-fail/remediation phase + curriculum stages from progress or checkpoint."""
    phase = _resolve_fast_path_phase(progress, checkpoint)
    if phase not in {"certificate_failed", "certificate_remediation"}:
        return False
    stages = _resolve_fast_path_stages(progress, checkpoint)
    return curriculum_stages_complete(stages)


def reconstruct_checkpoint_from_progress(
    workspace_root: Path | str,
    progress: dict[str, Any],
    *,
    policy_path: str = "",
    checkpoint: dict[str, Any] | None = None,
) -> bool:
    """Persist minimal checkpoint from progress when cert-fail checkpoint was lost."""
    from lumina_core.birth.checkpoint import read_checkpoint_payload, save_checkpoint

    ckpt = dict(checkpoint or {})
    if not ckpt:
        legacy = read_checkpoint_payload(workspace_root)
        if isinstance(legacy, dict):
            ckpt = legacy

    if not should_fast_path_remediation_from_state(progress, ckpt):
        return False
    root = Path(workspace_root)
    default_policy = root / "lumina_agents" / "ppo" / "lumina_ppo_policy.zip"
    resolved_policy = str(
        policy_path
        or ckpt.get("policy_path")
        or progress.get("policy_path")
        or default_policy
    )
    if not Path(resolved_policy).is_file():
        logger.warning(
            "birth.reconstruct_checkpoint.policy_missing path=%s",
            resolved_policy,
        )
        return False

    buffer_path = str(ckpt.get("buffer_path", "") or progress.get("buffer_path", "") or "")
    stages = _resolve_fast_path_stages(progress, ckpt)
    save_checkpoint(
        root,
        cumulative_trades=max(
            0,
            int(progress.get("cumulative_trades", progress.get("trades_done", 0)) or 0),
        ),
        ppo_steps=max(0, int(progress.get("ppo_steps", ckpt.get("ppo_steps", 0)) or 0)),
        training_mode="certified",
        stages_passed=stages,
        curriculum_stage="stage4_polish",
        policy_path=resolved_policy,
        stage_metrics=dict(ckpt.get("stage_metrics") or {}),
        buffer_path=buffer_path or None,
        data_manifest=dict(progress.get("data_manifest") or ckpt.get("data_manifest") or {}),
        phase=str(
            _resolve_fast_path_phase(progress, ckpt) or progress.get("phase", "certificate_failed")
        ),
        remediation_attempt=max(
            0,
            int(progress.get("remediation_attempt", ckpt.get("remediation_attempt", 0)) or 0),
        ),
    )
    logger.info(
        "birth.reconstruct_checkpoint.ok stages=%s policy=%s buffer=%s",
        stages,
        resolved_policy,
        buffer_path or "none",
    )
    return True


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


def classify_cache_resume_tier(
    *,
    checkpoint_manifest: dict[str, Any],
    cache_manifest: dict[str, Any] | None,
    cached_ticks: list[dict[str, Any]],
    cached_split: Any | None,
    cached_train_hash: str,
    holdout_pct: float,
    enrich_version: str,
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
