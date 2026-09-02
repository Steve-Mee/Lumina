"""Birth Foundation AND-gates (ADR-0046). Fail-closed. No WR 20/35/40 pass."""

from __future__ import annotations

from dataclasses import dataclass

from lumina_core.birth.curriculum_types import CurriculumStage
from lumina_core.birth.foundation_metrics import (
    MEDIAN_LOSS_R_MAX,
    NET_RR_MIN,
    POLICY_EDGE_MIN_TRADES,
    S1_MIN_TRADES,
    S2_MIN_TRADES,
    S2_OCCUPANCY_MAX,
    S2_OCCUPANCY_MIN,
    S3_EDGE_MIN,
    S3_MIN_TRADES,
    S3_OCCUPANCY_MAX,
    S3_OCCUPANCY_MIN,
    S4_EDGE_MIN,
    S4_MEAN_R_SLACK,
    S4_MIN_TRADES,
    S5_DD_MAX_PCT,
    S5_EDGE_MIN,
    S5_MIN_TRADES,
    S5_SHARPE_FLOOR,
    FoundationSnapshot,
    process_r_ok,
)


@dataclass(frozen=True, slots=True)
class FoundationPassDecision:
    passed: bool
    blockers: tuple[str, ...]
    message: str

    @property
    def stage_pass_now(self) -> bool:
        return bool(self.passed)


def _occupancy_in_band(value: float | None, *, lo: float, hi: float) -> bool:
    if value is None:
        return False
    return float(lo) - 1e-12 <= float(value) <= float(hi) + 1e-12


def _common_body(
    snap: FoundationSnapshot,
    *,
    min_trades: int,
    require_occupancy: bool,
    occ_lo: float,
    occ_hi: float,
    require_replay: bool,
) -> list[str]:
    blockers: list[str] = []
    if int(snap.trades) < int(min_trades):
        blockers.append(f"trades {snap.trades} < {min_trades}")
    if int(snap.constitution_violations) > 0:
        blockers.append(f"constitution {snap.constitution_violations} > 0")
    if not snap.entropy_alive:
        blockers.append("entropy_dead")
    if not snap.settlement_ok:
        blockers.append(f"settlement_share={snap.settlement_share:.2f}")
    if not process_r_ok(snap.median_loss_r, max_r=MEDIAN_LOSS_R_MAX):
        blockers.append(
            f"median_loss_r={snap.median_loss_r} missing_or_gt_{MEDIAN_LOSS_R_MAX}"
        )
    if require_occupancy and not _occupancy_in_band(snap.occupancy, lo=occ_lo, hi=occ_hi):
        blockers.append(
            f"occupancy={snap.occupancy} not_in_{occ_lo:.0%}-{occ_hi:.0%}"
        )
    if require_replay and not snap.replay_ok:
        blockers.append(
            f"replay_cap trades={snap.trades} days={snap.unique_calendar_days}"
        )
    return blockers


def _policy_edge_blockers(
    snap: FoundationSnapshot,
    *,
    floor: float,
    prefix: str,
    suffix: str = "",
) -> list[str]:
    """Grade edge only when the pilot sample is large enough. Thin sample ≠ 0 − p_ft."""
    skill_n = int(getattr(snap, "skill_trades", 0) or 0)
    if skill_n < POLICY_EDGE_MIN_TRADES:
        return [f"policy_sample {skill_n} < {POLICY_EDGE_MIN_TRADES}"]
    if snap.edge is None or float(snap.edge) + 1e-12 < float(floor):
        return [f"{prefix}{snap.edge} < {floor}{suffix}"]
    return []


def evaluate_foundation_pass(
    stage: CurriculumStage,
    snap: FoundationSnapshot,
    *,
    round_trips: int = 0,
    required_round_trips: int = 0,
) -> FoundationPassDecision:
    """AND-gates for sequential Birth Foundation stages 1–5."""
    blockers: list[str] = []
    if stage == CurriculumStage.STAGE1_TREND:
        blockers = _common_body(
            snap,
            min_trades=S1_MIN_TRADES,
            require_occupancy=False,
            occ_lo=0.0,
            occ_hi=1.0,
            require_replay=True,
        )
        rr = snap.net_rr
        if rr is None or float(rr) + 1e-12 < NET_RR_MIN:
            blockers.append(f"net_rr={rr} < {NET_RR_MIN}")
    elif stage == CurriculumStage.STAGE2_RANGE:
        blockers = _common_body(
            snap,
            min_trades=S2_MIN_TRADES,
            require_occupancy=True,
            occ_lo=S2_OCCUPANCY_MIN,
            occ_hi=S2_OCCUPANCY_MAX,
            require_replay=True,
        )
        need_rt = max(3, int(required_round_trips) or max(3, S2_MIN_TRADES // 10))
        if int(round_trips) < need_rt:
            blockers.append(f"round_trips {round_trips} < {need_rt}")
    elif stage == CurriculumStage.STAGE3_MIXED:
        blockers = _common_body(
            snap,
            min_trades=S3_MIN_TRADES,
            require_occupancy=True,
            occ_lo=S3_OCCUPANCY_MIN,
            occ_hi=S3_OCCUPANCY_MAX,
            require_replay=True,
        )
        blockers.extend(_policy_edge_blockers(snap, floor=S3_EDGE_MIN, prefix="edge="))
    elif stage == CurriculumStage.STAGE4_VIABLE_PLANT:
        blockers = _common_body(
            snap,
            min_trades=S4_MIN_TRADES,
            require_occupancy=True,
            occ_lo=S3_OCCUPANCY_MIN,
            occ_hi=S3_OCCUPANCY_MAX,
            require_replay=True,
        )
        blockers.extend(
            _policy_edge_blockers(
                snap,
                floor=S4_EDGE_MIN,
                prefix="edge=",
                suffix=" (must beat first-touch)",
            )
        )
        if snap.mean_r is None or snap.e_mech is None:
            blockers.append("mean_r_or_e_mech_missing")
        elif float(snap.mean_r) + 1e-12 < float(snap.e_mech) - S4_MEAN_R_SLACK:
            blockers.append(
                f"mean_r={snap.mean_r:.4f} < e_mech-slack "
                f"{float(snap.e_mech) - S4_MEAN_R_SLACK:.4f}"
            )
    elif stage == CurriculumStage.STAGE5_PROBE_HANDOFF:
        blockers = _common_body(
            snap,
            min_trades=S5_MIN_TRADES,
            require_occupancy=True,
            occ_lo=S3_OCCUPANCY_MIN,
            occ_hi=S3_OCCUPANCY_MAX,
            require_replay=True,
        )
        blockers.extend(
            _policy_edge_blockers(snap, floor=S5_EDGE_MIN, prefix="oos_edge=")
        )
        if int(snap.trades) >= S5_MIN_TRADES:
            if snap.oos_sharpe is None or float(snap.oos_sharpe) <= S5_SHARPE_FLOOR:
                blockers.append(f"oos_sharpe={snap.oos_sharpe} <= {S5_SHARPE_FLOOR}")
            if snap.oos_dd_pct is None or float(snap.oos_dd_pct) > S5_DD_MAX_PCT + 1e-12:
                blockers.append(f"oos_dd={snap.oos_dd_pct} > {S5_DD_MAX_PCT}")
    else:
        blockers.append(f"not_foundation_stage:{stage.value}")

    passed = len(blockers) == 0
    message = "foundation_pass" if passed else "foundation_fail:" + ";".join(blockers)
    return FoundationPassDecision(passed=passed, blockers=tuple(blockers), message=message)


__all__ = ["FoundationPassDecision", "evaluate_foundation_pass"]
