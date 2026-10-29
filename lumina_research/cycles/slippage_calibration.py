"""Slippage calibration: SIM fills if present, else a documented assumption.

The tape never uses a fixed ``volatility_price=2.0``. Bar true-range is the vol
term. Coefficient 0.10 is the ADR-0055 starting point and is not retuned on
holdout. No SIM fill archive ships in this repo, so the assumption is explicit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from lumina_research.validation.contracts import ContractSpec
from lumina_research.validation.cost_model import (
    DEFAULT_IMPACT_COEFFICIENT,
    DEFAULT_SLIPPAGE_COEFFICIENT,
    MarketSnapshot,
)

SLIPPAGE_COEFFICIENT = DEFAULT_SLIPPAGE_COEFFICIENT
IMPACT_COEFFICIENT = DEFAULT_IMPACT_COEFFICIENT
ASSUMPTION = (
    "No SIM fill archive in-repo. Slippage = 0.10 * (bar true-range / tick) * "
    "(causal ADV21 / bar volume). Impact = 0.10 * (bar true-range / tick) * "
    "sqrt(qty / ADV21). Coefficient is the ADR-0055 default, not fit on holdout."
)
SIM_FILL_GLOBS: tuple[str, ...] = (
    "reports/playground_bar_archive/**/*fill*.jsonl",
    "state/**/sim*fill*.jsonl",
    "data/research/**/sim_fills*.jsonl",
)


@dataclass(frozen=True, slots=True)
class SlippageCalibration:
    coefficient: float
    impact_coefficient: float
    source: str
    n_fills: int
    note: str


def load_slippage_calibration(repo_root: Path | None = None) -> SlippageCalibration:
    root = repo_root if repo_root is not None else Path(__file__).resolve().parents[2]
    found = _find_sim_fills(root)
    if not found:
        return SlippageCalibration(
            coefficient=SLIPPAGE_COEFFICIENT,
            impact_coefficient=IMPACT_COEFFICIENT,
            source="documented_assumption",
            n_fills=0,
            note=ASSUMPTION,
        )
    return SlippageCalibration(
        coefficient=SLIPPAGE_COEFFICIENT,
        impact_coefficient=IMPACT_COEFFICIENT,
        source="sim_fills_present_coefficient_not_retuned",
        n_fills=len(found),
        note=ASSUMPTION + f" Found {len(found)} SIM fill file(s); coefficient left at 0.10.",
    )


def reference_market(spec: ContractSpec) -> MarketSnapshot:
    """Reference snapshot for BE tables only. Tape costs use per-bar true range."""
    del spec
    return MarketSnapshot(volume=10_000.0, average_volume=10_000.0, volatility_price=1.0)


def _find_sim_fills(root: Path) -> tuple[Path, ...]:
    hits: list[Path] = []
    for pattern in SIM_FILL_GLOBS:
        hits.extend(path for path in root.glob(pattern) if path.is_file())
    return tuple(hits)


def calibration_note(rows: Sequence[SlippageCalibration] | None = None) -> str:
    del rows
    loaded = load_slippage_calibration()
    return f"{loaded.source}: {loaded.note}"
