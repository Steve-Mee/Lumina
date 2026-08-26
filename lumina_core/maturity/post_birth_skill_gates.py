"""Post-Birth skill gates relocated from intra-Birth runway (ADR-0046).

These were numbered S5–S7 / cert OOS inside Birth. They belong on the
maturation ladder with the same physics — not deleted, not Birth pass.

| Gate                         | Former Birth slot      | Home now            |
| Economic viability (WR≥BE, mean R≥0) | runway S5 profit | Playground          |
| Risk discipline Sharpe/DD    | runway S6              | Apprenticeship      |
| Evolution Proof / holdout 0.45 | S7 + ADR-0026        | Awakening           |
| Certificate OOS 0.48/0.35/8% | cert pipeline          | Proving Ground      |
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lumina_core.birth.fitness_vector import load_fitness_vector
from lumina_core.birth.foundation_metrics import skill_winrate
from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.maturity.post_birth_skill_gates")

# Former runway S5 profit — economic skill, not Birth.
ECONOMIC_MEAN_R_MIN = 0.0
# Former runway S6.
RISK_SHARPE_MIN = 0.20
RISK_DD_MAX_PCT = 12.0
# Former S7 / Evolution Proof polish OOS.
EVOLUTION_PROOF_OOS_WR_MIN = 0.45
EVOLUTION_PROOF_LIFT_MIN = 0.05
# Certificate / Proving Ground (ADR-0013 / ADR-0036). Never Birth exit.
CERT_OOS_WR_MIN = 0.48
CERT_OOS_SHARPE_MIN = 0.35
CERT_OOS_DD_MAX_PCT = 8.0


@dataclass(frozen=True, slots=True)
class PostBirthGateResult:
    passed: bool
    gate_id: str
    home_phase: str
    blockers: tuple[str, ...]
    detail: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "gate_id": self.gate_id,
            "home_phase": self.home_phase,
            "blockers": list(self.blockers),
            "detail": dict(self.detail),
        }


def economic_viability(
    *,
    mean_r: float | None,
    skill_wr: float | None,
    breakeven_wr: float | None,
) -> PostBirthGateResult:
    """Playground: profitability vs geometry BE. Not a Birth pass gate."""
    blockers: list[str] = []
    if mean_r is None:
        blockers.append("mean_r_missing")
    elif float(mean_r) + 1e-12 < ECONOMIC_MEAN_R_MIN:
        blockers.append(f"mean_r={mean_r:.4f} < 0")
    if skill_wr is None or breakeven_wr is None:
        blockers.append("wr_or_be_missing")
    elif float(skill_wr) + 1e-12 < float(breakeven_wr):
        blockers.append(f"skill_wr={skill_wr:.4f} < BE={breakeven_wr:.4f}")
    return PostBirthGateResult(
        passed=not blockers,
        gate_id="economic_viability",
        home_phase="playground",
        blockers=tuple(blockers),
        detail={
            "mean_r": mean_r,
            "skill_wr": skill_wr,
            "breakeven_wr": breakeven_wr,
            "relocated_from": "birth_runway_stage5_profit_val",
        },
    )


def risk_discipline(*, sharpe: float | None, max_dd_pct: float | None) -> PostBirthGateResult:
    """Apprenticeship: former Birth S6 Sharpe/DD."""
    blockers: list[str] = []
    if sharpe is None or float(sharpe) + 1e-12 < RISK_SHARPE_MIN:
        blockers.append(f"sharpe={sharpe} < {RISK_SHARPE_MIN}")
    if max_dd_pct is None or float(max_dd_pct) > RISK_DD_MAX_PCT + 1e-12:
        blockers.append(f"dd={max_dd_pct} > {RISK_DD_MAX_PCT}")
    return PostBirthGateResult(
        passed=not blockers,
        gate_id="risk_discipline",
        home_phase="apprenticeship",
        blockers=tuple(blockers),
        detail={
            "sharpe": sharpe,
            "max_dd_pct": max_dd_pct,
            "relocated_from": "birth_runway_stage6_risk_discipline",
        },
    )


def certificate_oos_walls(
    *,
    oos_wr: float | None,
    oos_sharpe: float | None,
    max_dd_pct: float | None,
) -> PostBirthGateResult:
    """Proving Ground / cert pipeline. Not Birth exit (ADR-0036)."""
    blockers: list[str] = []
    if oos_wr is None or float(oos_wr) + 1e-12 < CERT_OOS_WR_MIN:
        blockers.append(f"oos_wr={oos_wr} < {CERT_OOS_WR_MIN}")
    if oos_sharpe is None or float(oos_sharpe) + 1e-12 < CERT_OOS_SHARPE_MIN:
        blockers.append(f"oos_sharpe={oos_sharpe} < {CERT_OOS_SHARPE_MIN}")
    if max_dd_pct is None or float(max_dd_pct) > CERT_OOS_DD_MAX_PCT + 1e-12:
        blockers.append(f"dd={max_dd_pct} > {CERT_OOS_DD_MAX_PCT}")
    return PostBirthGateResult(
        passed=not blockers,
        gate_id="certificate_oos_walls",
        home_phase="proving_ground",
        blockers=tuple(blockers),
        detail={
            "oos_wr": oos_wr,
            "oos_sharpe": oos_sharpe,
            "max_dd_pct": max_dd_pct,
            "relocated_from": "birth_certificate_oos",
        },
    )


def awakening_evolution_proof_from_fitness(
    workspace_root: Path | str,
    *,
    polish_oos_winrate: float | None,
    holdout_trades: int,
) -> PostBirthGateResult:
    """Awakening: Evolution Proof vs Stage-5 fitness vector baseline."""
    from lumina_core.birth.evolution_proof_gate import (
        EvolutionProofConfig,
        evaluate_evolution_proof,
        evolution_proof_passed,
    )

    vector = load_fitness_vector(workspace_root)
    blockers: list[str] = []
    detail: dict[str, Any] = {"relocated_from": "birth_runway_stage7_holdout_profile"}
    if vector is None:
        blockers.append("fitness_vector_missing")
        return PostBirthGateResult(
            passed=False,
            gate_id="evolution_proof",
            home_phase="awakening",
            blockers=tuple(blockers),
            detail=detail,
        )
    baseline = float(vector.oos_wr)
    probe = float(polish_oos_winrate) if polish_oos_winrate is not None else baseline
    result = evaluate_evolution_proof(
        birth_exit_winrate=baseline,
        polish_oos_winrate=probe,
        holdout_trades=int(holdout_trades) if holdout_trades > 0 else int(vector.trades),
        cfg=EvolutionProofConfig(
            min_winrate_lift=EVOLUTION_PROOF_LIFT_MIN,
            polish_oos_winrate_min=EVOLUTION_PROOF_OOS_WR_MIN,
        ),
    )
    detail.update(
        {
            "baseline_oos_wr": baseline,
            "probe_oos_wr": probe,
            "holdout_trades": holdout_trades,
            "fitness_mean_r": vector.mean_r,
            "fitness_edge": vector.edge,
            "ep_passed": result.passed,
            "ep_reasons": list(result.reasons),
            "record_ok": bool(evolution_proof_passed(workspace_root)),
        }
    )
    if not result.passed:
        blockers.extend(result.reasons or ["evolution_proof_failed"])
    return PostBirthGateResult(
        passed=result.passed,
        gate_id="evolution_proof",
        home_phase="awakening",
        blockers=tuple(blockers),
        detail=detail,
    )


def load_certificate_oos_fields(workspace_root: Path | str) -> dict[str, Any]:
    root = Path(workspace_root)
    for name in ("lumina_birth_certificate.json", "birth_certificate.json"):
        path = root / "state" / name
        if not path.is_file():
            continue
        try:
            import json

            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(raw, dict):
            continue
        return {
            "oos_wr": raw.get("oos_winrate"),
            "oos_sharpe": raw.get("oos_sharpe"),
            "max_dd_pct": raw.get("max_drawdown_pct") or raw.get("oos_max_drawdown_pct"),
        }
    return {}


def skill_wr_from_counts(*, trades: int, wins: int) -> float:
    return skill_winrate(trades=trades, wins=wins)


__all__ = [
    "CERT_OOS_DD_MAX_PCT",
    "CERT_OOS_SHARPE_MIN",
    "CERT_OOS_WR_MIN",
    "ECONOMIC_MEAN_R_MIN",
    "EVOLUTION_PROOF_LIFT_MIN",
    "EVOLUTION_PROOF_OOS_WR_MIN",
    "PostBirthGateResult",
    "RISK_DD_MAX_PCT",
    "RISK_SHARPE_MIN",
    "awakening_evolution_proof_from_fitness",
    "certificate_oos_walls",
    "economic_viability",
    "load_certificate_oos_fields",
    "risk_discipline",
]
