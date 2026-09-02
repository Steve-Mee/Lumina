"""S3 skill/settlement SSOT persist + restore + HUD + rollout plumbing.

WHY: Resume restored ``stage_trades`` then zeroed policy/plant/close cums, so a
legal S3 resume emitted ``settlement_share=0.00`` plus ``policy_sample 0 < 150``
even when 524 plant closes already existed. Persist and reload — never invent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lumina_core.birth.stage3_inband_idle import S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS


def s3_inband_progress_fields(host: Any) -> dict[str, Any]:
    """HUD: a live exam cannot hide PASSTHROUGH + HOLD + tax off."""
    return {
        "s3_inband_idle_armed": bool(getattr(host, "s3_inband_idle_armed", False)),
        "s3_inband_explore": int(getattr(host, "s3_inband_explore", 0) or 0),
        "s3_inband_hold_tax_steps": int(getattr(host, "s3_inband_hold_tax_steps", 0) or 0),
        "participation_inband_explore": int(
            getattr(host, "s3_inband_explore", 0) or 0
        ),
    }


def persist_skill_settlement_fields(host: Any) -> dict[str, Any]:
    """Checkpoint SSOT: policy/plant + close cums (never zeros on a live stage)."""
    from lumina_core.birth.starship_edgescore_core import settlement_progress_fields

    payload = settlement_progress_fields(
        closes_stop=int(getattr(host, "stage_closes_stop_cum", 0) or 0),
        closes_target=int(getattr(host, "stage_closes_target_cum", 0) or 0),
        closes_time_stop=int(getattr(host, "stage_closes_time_stop_cum", 0) or 0),
        closes_flatten=int(getattr(host, "stage_closes_flatten_cum", 0) or 0),
        closes_unknown=int(getattr(host, "stage_closes_unknown_cum", 0) or 0),
    )
    payload["stage_policy_trades"] = int(getattr(host, "stage_policy_trades", 0) or 0)
    payload["stage_policy_wins"] = int(getattr(host, "stage_policy_wins", 0) or 0)
    payload["stage_plant_trades"] = int(getattr(host, "stage_plant_trades", 0) or 0)
    payload["stage_plant_wins"] = int(getattr(host, "stage_plant_wins", 0) or 0)
    payload["settlement_ssot_pending"] = bool(
        getattr(host, "_settlement_ssot_pending", False)
    )
    payload.update(s3_inband_progress_fields(host))
    return payload


@dataclass(frozen=True, slots=True)
class SkillSettlementSnapshot:
    stage_trades: int
    policy_trades: int
    plant_trades: int
    policy_wins: int
    plant_wins: int
    closes_stop: int
    closes_target: int
    closes_flatten: int
    closes_time_stop: int
    closes_unknown: int
    settlement_ssot_pending: bool

    @property
    def close_total(self) -> int:
        return (
            int(self.closes_stop)
            + int(self.closes_target)
            + int(self.closes_flatten)
            + int(self.closes_time_stop)
            + int(self.closes_unknown)
        )


def snapshot_from_checkpoint_metrics(
    metrics: dict[str, Any] | None,
    *,
    stage_trades: int = 0,
) -> SkillSettlementSnapshot:
    """Rebuild skill/settlement SSOT from persisted fields. Never invent closes."""
    raw = metrics if isinstance(metrics, dict) else {}
    trades = max(0, int(raw.get("stage_trades", stage_trades) or stage_trades or 0))
    policy_raw = raw.get("stage_policy_trades", raw.get("policy_trades"))
    plant_raw = raw.get("stage_plant_trades", raw.get("plant_trades"))
    policy_n = int(policy_raw) if policy_raw is not None else None
    plant_n = int(plant_raw) if plant_raw is not None else None
    if policy_n is None and plant_n is None:
        policy_n, plant_n = 0, 0
    elif policy_n is None:
        policy_n = max(0, trades - int(plant_n or 0))
    elif plant_n is None:
        plant_n = max(0, trades - int(policy_n or 0))
    policy_n = max(0, int(policy_n))
    plant_n = max(0, int(plant_n))
    stop_n = int(raw.get("stage_closes_stop_cum", raw.get("closes_stop", 0)) or 0)
    tgt_n = int(raw.get("stage_closes_target_cum", raw.get("closes_target", 0)) or 0)
    flat_n = int(raw.get("stage_closes_flatten_cum", raw.get("closes_flatten", 0)) or 0)
    time_n = int(
        raw.get("stage_closes_time_stop_cum", raw.get("closes_time_stop", 0)) or 0
    )
    unk_n = int(raw.get("stage_closes_unknown_cum", raw.get("closes_unknown", 0)) or 0)
    close_total = stop_n + tgt_n + flat_n + time_n + unk_n
    pending = bool(raw.get("settlement_ssot_pending", False)) or (
        close_total <= 0 and trades > 0
    )
    return SkillSettlementSnapshot(
        stage_trades=trades,
        policy_trades=policy_n,
        plant_trades=plant_n,
        policy_wins=max(0, int(raw.get("stage_policy_wins", raw.get("policy_wins", 0)) or 0)),
        plant_wins=max(0, int(raw.get("stage_plant_wins", raw.get("plant_wins", 0)) or 0)),
        closes_stop=max(0, stop_n),
        closes_target=max(0, tgt_n),
        closes_flatten=max(0, flat_n),
        closes_time_stop=max(0, time_n),
        closes_unknown=max(0, unk_n),
        settlement_ssot_pending=bool(pending),
    )


def apply_skill_settlement_snapshot(host: Any, snap: SkillSettlementSnapshot) -> None:
    host.stage_policy_trades = int(snap.policy_trades)
    host.stage_policy_wins = int(snap.policy_wins)
    host.stage_plant_trades = int(snap.plant_trades)
    host.stage_plant_wins = int(snap.plant_wins)
    host.stage_closes_stop_cum = int(snap.closes_stop)
    host.stage_closes_target_cum = int(snap.closes_target)
    host.stage_closes_flatten_cum = int(snap.closes_flatten)
    host.stage_closes_time_stop_cum = int(snap.closes_time_stop)
    host.stage_closes_unknown_cum = int(snap.closes_unknown)
    host._settlement_ssot_pending = bool(snap.settlement_ssot_pending)
    host.s3_inband_explore = int(getattr(host, "s3_inband_explore", 0) or 0)
    host.s3_inband_hold_tax_steps = int(getattr(host, "s3_inband_hold_tax_steps", 0) or 0)


def restore_skill_settlement_from_metrics(host: Any, metrics: dict[str, Any] | None) -> None:
    trades = int(getattr(host, "stage_trades", 0) or 0)
    snap = snapshot_from_checkpoint_metrics(metrics, stage_trades=trades)
    apply_skill_settlement_snapshot(host, snap)
    raw = metrics if isinstance(metrics, dict) else {}
    host.s3_inband_explore = int(raw.get("s3_inband_explore", 0) or 0)
    host.s3_inband_hold_tax_steps = int(raw.get("s3_inband_hold_tax_steps", 0) or 0)
    host.s3_inband_idle_armed = bool(raw.get("s3_inband_idle_armed", False))


def reset_skill_settlement_if_fresh_stage(host: Any) -> None:
    """Zero skill/settlement clocks only on a fresh stage, never mid-stage resume."""
    resume_keep = bool(getattr(host, "metrics_match_stage", False)) and int(
        getattr(host, "stage_trades", 0) or 0
    ) > 0
    host.closes_stop = 0
    host.closes_target = 0
    host.closes_flatten = 0
    host.closes_time_stop = 0
    host.closes_unknown = 0
    if resume_keep:
        return
    host.stage_closes_stop_cum = 0
    host.stage_closes_target_cum = 0
    host.stage_closes_flatten_cum = 0
    host.stage_closes_time_stop_cum = 0
    host.stage_closes_unknown_cum = 0
    host.stage_policy_trades = 0
    host.stage_policy_wins = 0
    host.stage_plant_trades = 0
    host.stage_plant_wins = 0
    host._settlement_ssot_pending = False
    host.s3_inband_explore = 0
    host.s3_inband_hold_tax_steps = 0
    host.s3_inband_idle_armed = False


def s3_inband_rollout_kwargs(loop: Any) -> dict[str, Any]:
    min_idle = S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS
    try:
        reward = getattr(getattr(loop, "host", None), "birth_config", None)
        reward = getattr(reward, "reward", None) if reward is not None else None
        if reward is not None:
            min_idle = int(
                getattr(reward, "s3_inband_min_idle_hold_bars", min_idle) or min_idle
            )
    except (TypeError, ValueError, AttributeError):
        min_idle = S3_INBAND_DEFAULT_MIN_IDLE_HOLD_BARS
    return {
        "stage_policy_trades_prior": int(getattr(loop, "stage_policy_trades", 0) or 0),
        "s3_inband_min_idle_hold_bars": int(min_idle),
    }


def apply_s3_inband_rollout_metrics(loop: Any, rollout: Any) -> None:
    loop.s3_inband_explore = int(getattr(loop, "s3_inband_explore", 0) or 0) + int(
        getattr(rollout, "s3_inband_explore", 0) or 0
    )
    loop.s3_inband_hold_tax_steps = int(
        getattr(loop, "s3_inband_hold_tax_steps", 0) or 0
    ) + int(getattr(rollout, "s3_inband_hold_tax_steps", 0) or 0)
    loop.s3_inband_idle_armed = bool(getattr(rollout, "s3_inband_idle_armed", False))
    if int(getattr(loop, "stage_closes_stop_cum", 0) or 0) + int(
        getattr(loop, "stage_closes_target_cum", 0) or 0
    ) + int(getattr(loop, "stage_closes_flatten_cum", 0) or 0) + int(
        getattr(loop, "stage_closes_time_stop_cum", 0) or 0
    ) + int(getattr(loop, "stage_closes_unknown_cum", 0) or 0) > 0:
        loop._settlement_ssot_pending = False


__all__ = [
    "SkillSettlementSnapshot",
    "apply_s3_inband_rollout_metrics",
    "apply_skill_settlement_snapshot",
    "persist_skill_settlement_fields",
    "reset_skill_settlement_if_fresh_stage",
    "restore_skill_settlement_from_metrics",
    "s3_inband_progress_fields",
    "s3_inband_rollout_kwargs",
    "snapshot_from_checkpoint_metrics",
]
