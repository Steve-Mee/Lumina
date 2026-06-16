"""Reason-specific certificate remediation planning (BRO v2 PR-O)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


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
