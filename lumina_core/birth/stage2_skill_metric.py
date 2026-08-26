"""Stage-2 skill metric SSOT — plant (FORCE_*) ≠ pilot grade.

Elon: the instructor's hand on the stick is not the pilot's exam score.
FORCE_OPEN/HOLD keep occupancy physics learnable; expectancy pass uses
**policy-initiated** trades only (when sample is large enough).

Never lowers floors. Never invents wins.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Stage2SkillCounts:
    """Total vs policy-only trade accounting."""

    total_trades: int
    total_wins: int
    policy_trades: int
    policy_wins: int
    plant_trades: int
    plant_wins: int
    skill_only: bool
    skill_min_trades: int
    skill_eligible: bool
    skill_trades: int
    skill_wins: int
    skill_winrate: float
    skill_expectancy: float
    total_winrate: float
    total_expectancy: float

    def as_progress_fields(self) -> dict[str, Any]:
        return {
            "stage_policy_trades": int(self.policy_trades),
            "stage_policy_wins": int(self.policy_wins),
            "stage_plant_trades": int(self.plant_trades),
            "stage_plant_wins": int(self.plant_wins),
            "skill_metric_policy_only": bool(self.skill_only),
            "skill_metric_eligible": bool(self.skill_eligible),
            "skill_metric_trades": int(self.skill_trades),
            "skill_metric_wins": int(self.skill_wins),
            "skill_metric_winrate": round(float(self.skill_winrate), 4),
            "skill_metric_expectancy": round(float(self.skill_expectancy), 4),
            "total_metric_winrate": round(float(self.total_winrate), 4),
            "total_metric_expectancy": round(float(self.total_expectancy), 4),
        }


def resolve_stage2_skill_counts(
    *,
    total_trades: int,
    total_wins: int,
    policy_trades: int | None = None,
    policy_wins: int | None = None,
    plant_trades: int | None = None,
    plant_wins: int | None = None,
    skill_only: bool = True,
    required: int = 300,
    skill_min_trades: int | None = None,
) -> Stage2SkillCounts:
    """Resolve which trades grade the pilot for expectancy."""
    tt = max(0, int(total_trades))
    tw = max(0, int(total_wins))
    pt = int(policy_trades) if policy_trades is not None else tt
    pw = int(policy_wins) if policy_wins is not None else tw
    plt = int(plant_trades) if plant_trades is not None else max(0, tt - pt)
    plw = int(plant_wins) if plant_wins is not None else max(0, tw - pw)
    pt = max(0, pt)
    pw = max(0, min(pw, pt))
    plt = max(0, plt)
    plw = max(0, min(plw, plt))

    req = max(1, int(required))
    # Need a real pilot sample: half the gate, floor 50.
    smin = (
        int(skill_min_trades)
        if skill_min_trades is not None
        else max(50, min(req, req // 2))
    )
    smin = max(20, smin)
    only = bool(skill_only)
    eligible = (not only) or (pt >= smin)

    if only and eligible:
        st, sw = pt, pw
    elif only and not eligible:
        # Fail-closed: thin pilot sample → skill exp uses pilot if any, else 0 trades.
        st, sw = pt, pw
    else:
        st, sw = tt, tw

    total_wr = float(tw) / float(max(1, tt)) if tt > 0 else 0.0
    skill_wr = float(sw) / float(max(1, st)) if st > 0 else 0.0
    return Stage2SkillCounts(
        total_trades=tt,
        total_wins=tw,
        policy_trades=pt,
        policy_wins=pw,
        plant_trades=plt,
        plant_wins=plw,
        skill_only=only,
        skill_min_trades=smin,
        skill_eligible=bool(eligible),
        skill_trades=st,
        skill_wins=sw,
        skill_winrate=skill_wr,
        skill_expectancy=skill_wr - 0.50,
        total_winrate=total_wr,
        total_expectancy=total_wr - 0.50,
    )


def skill_expectancy_for_pass(
    counts: Stage2SkillCounts,
    *,
    rolling_winrate: float | None = None,
) -> tuple[float, bool, str]:
    """Return (expectancy, sample_ok, source) for EdgeScore expectancy leg.

    When skill_only and not eligible, sample_ok=False → expectancy_ok fails
    (honest: not enough pilot trades to grade).
    source: skill | rolling | skill_lifted_by_rolling
    """
    if counts.skill_only and not counts.skill_eligible:
        return float(counts.skill_expectancy), False, "skill_ineligible"
    exp = float(counts.skill_expectancy)
    source = "skill"
    if rolling_winrate is not None and counts.skill_trades > 0:
        roll_exp = float(rolling_winrate) - 0.50
        if roll_exp > exp + 1e-12:
            source = "rolling_hud_only"
        elif abs(roll_exp - exp) <= 1e-12:
            source = "skill"
    return exp, True, source


__all__ = [
    "Stage2SkillCounts",
    "resolve_stage2_skill_counts",
    "skill_expectancy_for_pass",
]
