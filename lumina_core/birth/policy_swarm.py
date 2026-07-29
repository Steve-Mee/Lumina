"""Parallel policy variants at plateau entry (PR-4)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig, BirthRewardConfig
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.birth.policy_swarm")


@dataclass(slots=True)
class PolicySwarmVariant:
    variant_id: str
    label: str
    reward: BirthRewardConfig
    explore_multiplier: float = 1.0
    policy_path: str = ""


@dataclass(slots=True)
class PolicySwarmVariantResult:
    variant_id: str
    rollouts: int = 0
    trades: int = 0
    wins: int = 0
    total_pnl: float = 0.0

    @property
    def winrate(self) -> float:
        return float(self.wins) / float(max(1, self.trades))


def _reward_from_dict(raw: Any) -> BirthRewardConfig:
    if isinstance(raw, BirthRewardConfig):
        return raw
    if not isinstance(raw, dict):
        return BirthRewardConfig()
    allowed = {f.name for f in fields(BirthRewardConfig)}
    payload = {k: v for k, v in raw.items() if k in allowed}
    try:
        return BirthRewardConfig(**payload)
    except TypeError:
        return BirthRewardConfig()


@dataclass
class PolicySwarmState:
    active: bool = False
    variant_index: int = 0
    rollouts_this_variant: int = 0
    variants: list[PolicySwarmVariant] = field(default_factory=list)
    results: dict[str, PolicySwarmVariantResult] = field(default_factory=dict)
    committed_variant_id: str = ""
    rejected_no_lift: bool = False
    pre_swarm_policy_path: str = ""
    # Equal-window champion probe before variant evaluation.
    champion_probe_active: bool = False
    champion_probe_rollouts: int = 0
    champion_probe_trades: int = 0
    champion_probe_wins: int = 0
    champion_probe_pnl: float = 0.0
    champion_accepted: bool = False
    # Identical-window tournament: frozen tick slices (memory; not checkpointed).
    frozen_tick_windows: list[list[dict[str, Any]]] = field(default_factory=list)
    frozen_window_cursor: int = 0
    frozen_window_count: int = 0

    def current_variant(self) -> PolicySwarmVariant | None:
        if not self.active or self.champion_probe_active or not self.variants:
            return None
        idx = int(self.variant_index)
        if idx < 0 or idx >= len(self.variants):
            return None
        return self.variants[idx]

    def to_metrics(self) -> dict[str, Any]:
        return {
            "policy_swarm_active": bool(self.active),
            "policy_swarm_variant_index": int(self.variant_index),
            "policy_swarm_rollouts_this_variant": int(self.rollouts_this_variant),
            "policy_swarm_variant_count": len(self.variants),
            "policy_swarm_committed_variant": str(self.committed_variant_id or ""),
            "policy_swarm_rejected_no_lift": bool(self.rejected_no_lift),
            "policy_swarm_pre_policy_path": str(self.pre_swarm_policy_path or ""),
            "policy_swarm_champion_probe_active": bool(self.champion_probe_active),
            "policy_swarm_champion_probe_rollouts": int(self.champion_probe_rollouts),
            "policy_swarm_champion_probe_trades": int(self.champion_probe_trades),
            "policy_swarm_champion_probe_wins": int(self.champion_probe_wins),
            "policy_swarm_champion_probe_pnl": round(float(self.champion_probe_pnl), 4),
            "policy_swarm_champion_accepted": bool(self.champion_accepted),
            "policy_swarm_frozen_window_count": int(
                self.frozen_window_count or len(self.frozen_tick_windows)
            ),
            "policy_swarm_frozen_window_cursor": int(self.frozen_window_cursor),
            "policy_swarm_variants": [
                {
                    "variant_id": v.variant_id,
                    "label": v.label,
                    "explore_multiplier": float(v.explore_multiplier),
                    "policy_path": str(v.policy_path or ""),
                    "reward": asdict(v.reward),
                }
                for v in self.variants
            ],
            "policy_swarm_results": {
                key: {
                    "rollouts": value.rollouts,
                    "trades": value.trades,
                    "wins": value.wins,
                    "winrate": round(value.winrate, 4),
                    "total_pnl": round(value.total_pnl, 4),
                }
                for key, value in self.results.items()
            },
        }

    @classmethod
    def from_metrics(cls, payload: dict[str, Any] | None) -> PolicySwarmState:
        if not isinstance(payload, dict):
            return cls()
        raw_results = payload.get("policy_swarm_results")
        results: dict[str, PolicySwarmVariantResult] = {}
        if isinstance(raw_results, dict):
            for key, row in raw_results.items():
                if not isinstance(row, dict):
                    continue
                results[str(key)] = PolicySwarmVariantResult(
                    variant_id=str(key),
                    rollouts=int(row.get("rollouts", 0) or 0),
                    trades=int(row.get("trades", 0) or 0),
                    wins=int(row.get("wins", 0) or 0),
                    total_pnl=float(row.get("total_pnl", 0.0) or 0.0),
                )
        variants: list[PolicySwarmVariant] = []
        raw_variants = payload.get("policy_swarm_variants")
        if isinstance(raw_variants, list):
            for row in raw_variants:
                if not isinstance(row, dict):
                    continue
                vid = str(row.get("variant_id", "") or "").strip()
                if not vid:
                    continue
                variants.append(
                    PolicySwarmVariant(
                        variant_id=vid,
                        label=str(row.get("label", vid) or vid),
                        reward=_reward_from_dict(row.get("reward")),
                        explore_multiplier=float(row.get("explore_multiplier", 1.0) or 1.0),
                        policy_path=str(row.get("policy_path", "") or ""),
                    )
                )
        return cls(
            active=bool(payload.get("policy_swarm_active", False)),
            variant_index=int(payload.get("policy_swarm_variant_index", 0) or 0),
            rollouts_this_variant=int(
                payload.get("policy_swarm_rollouts_this_variant", 0) or 0
            ),
            variants=variants,
            committed_variant_id=str(payload.get("policy_swarm_committed_variant", "") or ""),
            rejected_no_lift=bool(payload.get("policy_swarm_rejected_no_lift", False)),
            pre_swarm_policy_path=str(payload.get("policy_swarm_pre_policy_path", "") or ""),
            champion_probe_active=bool(payload.get("policy_swarm_champion_probe_active", False)),
            champion_probe_rollouts=int(payload.get("policy_swarm_champion_probe_rollouts", 0) or 0),
            champion_probe_trades=int(payload.get("policy_swarm_champion_probe_trades", 0) or 0),
            champion_probe_wins=int(payload.get("policy_swarm_champion_probe_wins", 0) or 0),
            champion_probe_pnl=float(payload.get("policy_swarm_champion_probe_pnl", 0.0) or 0.0),
            champion_accepted=bool(payload.get("policy_swarm_champion_accepted", False)),
            frozen_tick_windows=[],  # never restore tick payloads from disk
            frozen_window_cursor=int(payload.get("policy_swarm_frozen_window_cursor", 0) or 0),
            frozen_window_count=int(payload.get("policy_swarm_frozen_window_count", 0) or 0),
            results=results,
        )

    def next_frozen_window(self) -> list[dict[str, Any]] | None:
        if not self.frozen_tick_windows:
            return None
        idx = int(self.frozen_window_cursor) % len(self.frozen_tick_windows)
        self.frozen_window_cursor = idx + 1
        return list(self.frozen_tick_windows[idx])

    def reset_frozen_window_cursor(self) -> None:
        self.frozen_window_cursor = 0


def build_swarm_variants(
    baseline: BirthRewardConfig,
    *,
    cfg: BirthCurriculumConfig,
) -> list[PolicySwarmVariant]:
    count = max(2, min(5, int(cfg.policy_swarm_variants)))
    variants: list[PolicySwarmVariant] = [
        PolicySwarmVariant(
            variant_id="swarm_expectancy",
            label="Expectancy focus",
            reward=replace(
                baseline,
                expectancy_coeff=min(0.85, baseline.expectancy_coeff + 0.15),
                loss_asymmetry_coeff=max(0.9, baseline.loss_asymmetry_coeff - 0.1),
            ),
            explore_multiplier=2.0,
        ),
        PolicySwarmVariant(
            variant_id="swarm_trend",
            label="Trend alignment",
            reward=replace(
                baseline,
                trend_align_bonus_coeff=min(0.25, baseline.trend_align_bonus_coeff + 0.08),
                quality_win_bonus_coeff=min(0.45, baseline.quality_win_bonus_coeff + 0.1),
            ),
            explore_multiplier=1.5,
        ),
        PolicySwarmVariant(
            variant_id="swarm_range",
            label="Range patience",
            reward=replace(
                baseline,
                range_flat_bonus_coeff=min(0.01, baseline.range_flat_bonus_coeff + 0.004),
                range_churn_penalty_coeff=min(0.02, baseline.range_churn_penalty_coeff + 0.006),
                volatility_penalty_coeff=max(0.05, baseline.volatility_penalty_coeff - 0.05),
            ),
            explore_multiplier=1.25,
        ),
    ]
    return variants[:count]


def record_swarm_rollout(
    state: PolicySwarmState,
    *,
    variant_id: str,
    trades: int,
    wins: int,
    total_pnl: float,
) -> None:
    result = state.results.get(variant_id)
    if result is None:
        result = PolicySwarmVariantResult(variant_id=variant_id)
        state.results[variant_id] = result
    result.rollouts += 1
    result.trades += max(0, int(trades))
    result.wins += max(0, int(wins))
    result.total_pnl += float(total_pnl)


def select_swarm_winner(
    state: PolicySwarmState,
    *,
    prefer_expectancy: bool = False,
    prefer_tournament_score: bool = False,
) -> PolicySwarmVariant | None:
    if not state.variants or not state.results:
        return state.variants[0] if state.variants else None

    def _score(variant: PolicySwarmVariant) -> tuple[float, float, float]:
        row = state.results.get(variant.variant_id)
        if row is None or row.trades <= 0:
            return (-1.0, -1.0, -1.0)
        expectancy = float(row.total_pnl) / float(max(1, row.trades))
        if prefer_tournament_score:
            from lumina_core.birth.starship_birth import tournament_score

            # Same physics as swarm lift gate — one ranking contract.
            tscore = tournament_score(
                trades=int(row.trades),
                wins=int(row.wins),
                total_pnl=float(row.total_pnl),
            )
            return (tscore, expectancy, float(row.trades))
        if prefer_expectancy:
            # Legacy Starship: champion by expectancy, then winrate, then volume.
            return (expectancy, row.winrate, float(row.trades))
        return (row.winrate, row.total_pnl, float(row.trades))

    ranked = sorted(state.variants, key=_score, reverse=True)
    winner = ranked[0]
    row = state.results.get(winner.variant_id, PolicySwarmVariantResult(winner.variant_id))
    logger.info(
        "birth.policy_swarm.winner id=%s winrate=%.2f%% expectancy=%.4f trades=%s "
        "prefer_tournament=%s prefer_exp=%s",
        winner.variant_id,
        row.winrate * 100.0,
        float(row.total_pnl) / float(max(1, row.trades)),
        row.trades,
        prefer_tournament_score,
        prefer_expectancy,
    )
    return winner


def swarm_rollout_target(cfg: BirthCurriculumConfig) -> int:
    return max(1, int(cfg.policy_swarm_rollouts_per_variant))


def swarm_probe_complete(state: PolicySwarmState, *, cfg: BirthCurriculumConfig) -> bool:
    if not state.active:
        return True
    per_variant = swarm_rollout_target(cfg)
    return state.variant_index >= len(state.variants) and all(
        state.results.get(variant.variant_id, PolicySwarmVariantResult(variant.variant_id)).rollouts
        >= per_variant
        for variant in state.variants
    )
