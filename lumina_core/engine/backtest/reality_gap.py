"""Reality Gap Tracker — rolling SIM vs REAL performance divergence monitor.

The Reality Gap measures how much the backtested (SIM) Sharpe ratio exceeds
the live (REAL) Sharpe ratio.  A large positive gap is a red flag for
over-optimised strategies that "paper-trade" well but degrade in production.

Key outputs:
  - penalty       : current penalty to subtract from fitness (≥ 0)
  - rolling_mean  : rolling mean gap over the last *window* observations
  - rolling_std   : rolling std dev of gap (high std = unstable regime)
  - band_status   : 'GREEN' / 'YELLOW' / 'RED' alert based on thresholds
  - gap_trend     : 'WIDENING' / 'STABLE' / 'NARROWING' based on slope

Integration:
  Call ``tracker.observe(sim_sharpe, real_sharpe)`` after each live trade batch.
  Pass ``tracker.penalty()`` to ``calculate_fitness(reality_gap_penalty=...)``.
"""

from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Band thresholds for gap size (mean_gap).
_BAND_GREEN: float = 0.30  # gap ≤ 0.30 → GREEN
_BAND_YELLOW: float = 0.70  # 0.30 < gap ≤ 0.70 → YELLOW
# gap > 0.70 → RED


@dataclass(slots=True)
class RealityGapObservation:
    """Single SIM/REAL Sharpe observation."""

    ts: str
    sim_sharpe: float
    real_sharpe: float
    gap: float  # sim_sharpe - real_sharpe
    penalty: float  # gap × coeff


@dataclass
class RealityGapTracker:
    """Rolling reality gap tracker.

    Parameters
    ----------
    penalty_coeff : float
        Multiplier applied to the raw gap to compute the fitness penalty.
        Larger coeff = harsher penalty for over-optimised strategies.
    window : int
        Number of recent observations used for rolling stats.
    history_path : Path | None
        File path for appending JSONL observations.  None = in-memory only.
    yellow_threshold : float
        Gap at which band transitions from GREEN to YELLOW.
    red_threshold : float
        Gap at which band transitions from YELLOW to RED.
    """

    penalty_coeff: float = 0.15
    window: int = 20
    history_path: Path | None = None
    yellow_threshold: float = _BAND_GREEN
    red_threshold: float = _BAND_YELLOW

    _observations: list[RealityGapObservation] = field(default_factory=list, repr=False)

    def observe(self, sim_sharpe: float, real_sharpe: float) -> float:
        """Record a new SIM/REAL observation and return the instantaneous penalty.

        The observation is appended to the in-memory buffer and persisted to
        history_path (if set).

        Returns
        -------
        float  — penalty value for this observation (≥ 0.0).
        """
        sim = float(sim_sharpe)
        real = float(real_sharpe)
        gap = sim - real
        inst_penalty = max(0.0, gap) * self.penalty_coeff

        obs = RealityGapObservation(
            ts=datetime.now(timezone.utc).isoformat(),
            sim_sharpe=sim,
            real_sharpe=real,
            gap=gap,
            penalty=inst_penalty,
        )
        self._observations.append(obs)
        self._persist(obs)
        return inst_penalty

    def penalty(self) -> float:
        """Return a smoothed penalty based on the rolling window.

        Uses the rolling mean gap × coeff so that a single outlier
        observation does not immediately spike the fitness score.
        """
        stats = self.rolling_stats()
        mean_gap = stats.get("mean_gap", 0.0)
        return max(0.0, float(mean_gap)) * self.penalty_coeff

    def rolling_stats(self) -> dict[str, Any]:
        """Compute rolling statistics over the last *window* observations."""
        recent = self._observations[-self.window :]
        if not recent:
            return {
                "window": 0,
                "mean_gap": 0.0,
                "std_gap": 0.0,
                "mean_penalty": 0.0,
                "max_gap": 0.0,
                "p95_gap": 0.0,
                "band_status": "GREEN",
                "gap_trend": "STABLE",
            }

        gaps = [o.gap for o in recent]
        penalties = [o.penalty for o in recent]
        sorted_gaps = sorted(gaps)

        mean_gap = statistics.mean(gaps)
        std_gap = statistics.pstdev(gaps) if len(gaps) > 1 else 0.0
        band = self._classify_band(mean_gap)
        trend = self._classify_trend(gaps)

        p95_idx = (len(sorted_gaps) - 1) * 0.95
        lo = int(math.floor(p95_idx))
        hi = int(math.ceil(p95_idx))
        p95_gap = (
            float(sorted_gaps[lo] * (1.0 - (p95_idx - lo)) + sorted_gaps[hi] * (p95_idx - lo))
            if lo != hi
            else float(sorted_gaps[lo])
        )

        return {
            "window": len(recent),
            "mean_gap": float(mean_gap),
            "std_gap": float(std_gap),
            "mean_penalty": float(statistics.mean(penalties)),
            "max_gap": float(max(gaps)),
            "p95_gap": float(p95_gap),
            "band_status": band,
            "gap_trend": trend,
        }

    def dynamic_penalty(self, *, base_coeff: float | None = None) -> float:
        """Compute a regime-adaptive penalty.

        When band is RED, the coefficient is doubled.
        When band is YELLOW, it is increased by 50%.
        When trend is WIDENING, add an extra 25% surcharge.

        This ensures the fitness function immediately discourages strategies
        that are transitioning into large-gap territory.
        """
        stats = self.rolling_stats()
        coeff = base_coeff if base_coeff is not None else self.penalty_coeff
        band = stats.get("band_status", "GREEN")
        trend = stats.get("gap_trend", "STABLE")
        mean_gap = float(stats.get("mean_gap", 0.0))

        if band == "RED":
            coeff *= 2.0
        elif band == "YELLOW":
            coeff *= 1.5

        if trend == "WIDENING":
            coeff *= 1.25

        return max(0.0, mean_gap) * coeff

    def load_history(self, path: Path | None = None) -> int:
        """Load observations from a JSONL file into the in-memory buffer.

        Returns number of records loaded.
        """
        target = path or self.history_path
        if target is None or not target.exists():
            return 0
        loaded = 0
        try:
            with target.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        self._observations.append(
                            RealityGapObservation(
                                ts=str(entry.get("ts", "")),
                                sim_sharpe=float(entry.get("sim_sharpe", 0.0)),
                                real_sharpe=float(entry.get("real_sharpe", 0.0)),
                                gap=float(entry.get("gap", 0.0)),
                                penalty=float(entry.get("penalty", 0.0)),
                            )
                        )
                        loaded += 1
                    except (json.JSONDecodeError, KeyError, TypeError):
                        pass
        except OSError:
            pass
        return loaded

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _persist(self, obs: RealityGapObservation) -> None:
        if self.history_path is None:
            return
        try:
            self.history_path.parent.mkdir(parents=True, exist_ok=True)
            with self.history_path.open("a", encoding="utf-8") as fh:
                fh.write(
                    json.dumps(
                        {
                            "ts": obs.ts,
                            "sim_sharpe": obs.sim_sharpe,
                            "real_sharpe": obs.real_sharpe,
                            "gap": obs.gap,
                            "penalty": obs.penalty,
                        }
                    )
                    + "\n"
                )
        except OSError:
            pass

    def _classify_band(self, mean_gap: float) -> str:
        if mean_gap <= self.yellow_threshold:
            return "GREEN"
        if mean_gap <= self.red_threshold:
            return "YELLOW"
        return "RED"

    @staticmethod
    def _classify_trend(gaps: list[float]) -> str:
        """Classify gap trend using the slope of the last N observations."""
        if len(gaps) < 4:
            return "STABLE"
        first_half = statistics.mean(gaps[: len(gaps) // 2])
        second_half = statistics.mean(gaps[len(gaps) // 2 :])
        delta = second_half - first_half
        if delta > 0.10:
            return "WIDENING"
        if delta < -0.10:
            return "NARROWING"
        return "STABLE"
