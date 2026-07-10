"""Strategy probe self-evaluation for prolonged birth learning stalls."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from lumina_core.birth.config import BirthCurriculumConfig
from lumina_core.birth.curriculum import CurriculumStage

DEFAULT_PROBE_STRATEGIES: tuple[str, ...] = (
    "pattern_inject_aggressive",
    "explore_boost",
    "reward_shaping_tweak",
    "data_expansion",
    "intra_ease",
    "explore_reduce",
)


class SelfEvalPhase(str, Enum):
    IDLE = "idle"
    PROBING = "probing"
    COMMITTED = "committed"
    EXHAUSTED = "exhausted"


@dataclass(frozen=True, slots=True)
class StrategyProbeResult:
    strategy: str
    rollouts: int
    velocity_start: float
    velocity_end: float
    velocity_delta: float
    combined_at_end: float


@dataclass(frozen=True, slots=True)
class ProvisionalFallbackResult:
    should_grant: bool
    reason: str
    blocked_reason: str | None
    safeguards: dict[str, bool]


@dataclass(slots=True)
class SelfEvalState:
    phase: SelfEvalPhase = SelfEvalPhase.IDLE
    probe_queue: list[str] = field(default_factory=list)
    current_strategy: str | None = None
    rollouts_in_probe: int = 0
    probe_results: list[StrategyProbeResult] = field(default_factory=list)
    committed_strategy: str | None = None
    cooldown_until_attempt: int = 0
    velocity_at_probe_start: float = 0.0
    pending_provisional: bool = False

    def to_metrics(self) -> dict[str, Any]:
        best_delta = 0.0
        if self.probe_results:
            best_delta = max(r.velocity_delta for r in self.probe_results)
        return {
            "meta_self_eval_phase": self.phase.value,
            "meta_self_eval_current_strategy": str(self.current_strategy or ""),
            "meta_self_eval_committed_strategy": str(self.committed_strategy or ""),
            "meta_self_eval_best_velocity_delta": round(best_delta, 6),
            "meta_self_eval_probes_completed": len(self.probe_results),
            "meta_self_eval_cooldown_until_attempt": int(self.cooldown_until_attempt),
            "meta_self_eval_probe_results": [
                {
                    "strategy": r.strategy,
                    "rollouts": r.rollouts,
                    "velocity_start": round(r.velocity_start, 6),
                    "velocity_end": round(r.velocity_end, 6),
                    "velocity_delta": round(r.velocity_delta, 6),
                    "combined_at_end": round(r.combined_at_end, 6),
                }
                for r in self.probe_results
            ],
        }

    @classmethod
    def from_metrics(cls, metrics: dict[str, Any] | None) -> SelfEvalState:
        if not isinstance(metrics, dict):
            return cls()
        phase_raw = str(metrics.get("meta_self_eval_phase", "") or "").strip().lower()
        phase = SelfEvalPhase.IDLE
        for item in SelfEvalPhase:
            if item.value == phase_raw:
                phase = item
                break
        committed = str(metrics.get("meta_self_eval_committed_strategy", "") or "") or None
        current = str(metrics.get("meta_self_eval_current_strategy", "") or "") or None
        results: list[StrategyProbeResult] = []
        raw_results = metrics.get("meta_self_eval_probe_results")
        if isinstance(raw_results, list):
            for row in raw_results:
                if not isinstance(row, dict):
                    continue
                strat_val = str(row.get("strategy", "") or "")
                if not strat_val:
                    continue
                results.append(
                    StrategyProbeResult(
                        strategy=strat_val,
                        rollouts=int(row.get("rollouts", 0) or 0),
                        velocity_start=float(row.get("velocity_start", 0.0) or 0.0),
                        velocity_end=float(row.get("velocity_end", 0.0) or 0.0),
                        velocity_delta=float(row.get("velocity_delta", 0.0) or 0.0),
                        combined_at_end=float(row.get("combined_at_end", 0.0) or 0.0),
                    )
                )
        queue: list[str] = []
        if phase == SelfEvalPhase.PROBING and current:
            queue = [current]
        return cls(
            phase=phase,
            probe_queue=queue,
            current_strategy=current,
            rollouts_in_probe=0,
            probe_results=results,
            committed_strategy=committed,
            cooldown_until_attempt=max(
                0, int(metrics.get("meta_self_eval_cooldown_until_attempt", 0) or 0)
            ),
            velocity_at_probe_start=0.0,
            pending_provisional=phase == SelfEvalPhase.EXHAUSTED,
        )


def build_probe_queue(snap: Any, cfg: BirthCurriculumConfig) -> list[str]:
    queue: list[str] = []
    stage = getattr(snap, "stage", None)
    for strategy in DEFAULT_PROBE_STRATEGIES:
        if strategy == "data_expansion" and bool(getattr(snap, "data_exhausted", False)):
            continue
        if strategy == "intra_ease":
            if stage != CurriculumStage.STAGE1_TREND:
                continue
            intra_hard = getattr(snap, "intra_hard_pct", None)
            if intra_hard is None or float(intra_hard) <= cfg.intra_initial_hard_pct:
                continue
        queue.append(strategy)
    return queue


def should_start_self_eval(
    snap: Any,
    state: SelfEvalState,
    cfg: BirthCurriculumConfig,
    *,
    strong_recovery_attempts: int,
    attempt: int,
) -> bool:
    if not cfg.meta_self_eval_enabled:
        return False
    if state.phase != SelfEvalPhase.IDLE:
        return False
    if attempt < state.cooldown_until_attempt:
        return False
    return (
        bool(getattr(snap, "is_stalled", False))
        and bool(getattr(snap, "volume_gate_passed", False))
        and strong_recovery_attempts >= cfg.meta_self_eval_min_recovery_attempts
        and int(getattr(snap, "low_velocity_attempts", 0) or 0)
        >= cfg.meta_self_eval_min_stall_attempts
    )


def score_probe_result(*, velocity_start: float, velocity_end: float) -> float:
    return float(velocity_end) - float(velocity_start)


def select_winner(
    results: list[StrategyProbeResult],
    cfg: BirthCurriculumConfig,
) -> str | None:
    floor = float(cfg.meta_self_eval_velocity_floor)
    min_gain = float(cfg.meta_self_eval_min_velocity_gain)
    candidates = [
        r
        for r in results
        if r.combined_at_end > floor and r.velocity_delta >= min_gain
    ]
    if not candidates:
        positive = [r for r in results if r.velocity_delta >= min_gain and r.velocity_delta > 0.0]
        if not positive:
            return None
        positive.sort(key=lambda r: (r.velocity_delta, r.combined_at_end), reverse=True)
        return positive[0].strategy
    candidates.sort(key=lambda r: (r.velocity_delta, r.combined_at_end), reverse=True)
    return candidates[0].strategy
