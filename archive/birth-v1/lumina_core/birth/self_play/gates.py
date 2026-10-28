"""Fail-closed gates for self-play lab (ADR-0037).

Order:
1. lab enabled
2. not REAL-like capital
3. champion freeze not active (or champion accepted)
4. frozen windows present when required
5. apply forbidden in Phase 0
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from lumina_core.birth.self_play.types import SelfPlayLabConfig

_REAL_LIKE = frozenset(
    {"real", "live", "prod", "production", "sim_real_guard"}
)


@dataclass(frozen=True)
class SelfPlayGateResult:
    allowed: bool
    reason: str
    detail: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "detail": self.detail,
        }


def _norm(mode: str | None) -> str:
    return str(mode or "").strip().lower()


def is_real_like_capital(mode: str | None) -> bool:
    m = _norm(mode)
    return m in _REAL_LIKE or m.startswith("real")


def is_champion_freeze_active(
    progress: Mapping[str, Any] | None = None,
    *,
    swarm_rejected_no_lift: bool | None = None,
    swarm_champion_accepted: bool | None = None,
) -> bool:
    """True when freeze blocks training / self-play apply paths."""
    p = dict(progress or {})
    rejected = (
        swarm_rejected_no_lift
        if swarm_rejected_no_lift is not None
        else bool(
            p.get("swarm_rejected_no_lift")
            or p.get("policy_swarm_rejected_no_lift")
        )
    )
    accepted = (
        swarm_champion_accepted
        if swarm_champion_accepted is not None
        else bool(
            p.get("swarm_champion_accepted")
            or p.get("policy_swarm_champion_accepted")
        )
    )
    return bool(rejected) and not bool(accepted)


def evaluate_self_play_gate(
    *,
    config: SelfPlayLabConfig | None = None,
    capital_mode: str | None = None,
    progress: Mapping[str, Any] | None = None,
    frozen_windows: list[Any] | None = None,
    require_windows: bool = False,
    for_apply: bool = False,
) -> SelfPlayGateResult:
    """Evaluate whether self-play lab may run (shadow) or apply (future)."""
    cfg = config or SelfPlayLabConfig()
    if not bool(cfg.enabled):
        return SelfPlayGateResult(
            allowed=False,
            reason="lab_disabled",
            detail="self_play_lab_enabled=false (default) — opt-in only",
        )

    cap = capital_mode if capital_mode is not None else cfg.capital_mode_hint
    if is_real_like_capital(cap):
        return SelfPlayGateResult(
            allowed=False,
            reason="real_capital_forbidden",
            detail=f"capital_mode={cap!r} — self-play never on REAL path",
        )

    if is_champion_freeze_active(progress):
        return SelfPlayGateResult(
            allowed=False,
            reason="blocked_champion_freeze",
            detail="swarm no tournament lift — accept champion or wipe first",
        )

    if require_windows:
        windows = frozen_windows if frozen_windows is not None else []
        if not windows:
            return SelfPlayGateResult(
                allowed=False,
                reason="frozen_windows_missing",
                detail="self-play requires identical frozen tick windows",
            )

    if for_apply:
        if not bool(cfg.allow_apply):
            return SelfPlayGateResult(
                allowed=False,
                reason="apply_forbidden_phase0",
                detail="Phase 0 is shadow report only — no progress mutation",
            )
        # Future: Twin + constitution would gate here
        return SelfPlayGateResult(
            allowed=False,
            reason="apply_not_implemented",
            detail="SIM apply under Twin deferred (SP3)",
        )

    return SelfPlayGateResult(
        allowed=True,
        reason="ok",
        detail="shadow ranking allowed",
    )


def assert_self_play_allowed(
    *,
    config: SelfPlayLabConfig | None = None,
    capital_mode: str | None = None,
    progress: Mapping[str, Any] | None = None,
    frozen_windows: list[Any] | None = None,
    require_windows: bool = False,
    for_apply: bool = False,
) -> SelfPlayGateResult:
    """Same as evaluate; raises ValueError when blocked (strict call sites)."""
    result = evaluate_self_play_gate(
        config=config,
        capital_mode=capital_mode,
        progress=progress,
        frozen_windows=frozen_windows,
        require_windows=require_windows,
        for_apply=for_apply,
    )
    if not result.allowed:
        raise ValueError(f"self_play_blocked:{result.reason}:{result.detail}")
    return result
