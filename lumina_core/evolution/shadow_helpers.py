"""Shadow types, defaults, and statistical helpers."""
from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from lumina_core.logging_utils import get_logger

logger = get_logger("lumina.evolution.shadow")

ShadowStatus = Literal["running", "passed", "failed", "promoted", "expired"]
ShadowVerdict = Literal["pass", "fail", "pending"]

_DEFAULT_SHADOW_PATH = Path("state/evolution_shadow_runs.json")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_elapsed(start_ts: str) -> float:
    try:
        start = datetime.fromisoformat(start_ts)
        now = datetime.now(timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        return (now - start).total_seconds() / 86400.0
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class ShadowRun:
    dna_hash: str
    start_ts: str = field(default_factory=_utcnow)
    end_ts: str = ""
    status: ShadowStatus = "running"

    # Performance tracking
    sim_pnl_history: list[float] = field(default_factory=list)
    paper_pnl_history: list[float] = field(default_factory=list)
    trade_count: int = 0

    # Aggregate metrics (updated on each PnL append)
    total_sim_pnl: float = 0.0
    total_paper_pnl: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ShadowRun":
        run = cls(dna_hash=str(d.get("dna_hash", "")))
        run.start_ts = str(d.get("start_ts", _utcnow()))
        run.end_ts = str(d.get("end_ts", ""))
        run.status = str(d.get("status", "running"))  # type: ignore[assignment]
        run.sim_pnl_history = list(d.get("sim_pnl_history", []))
        run.paper_pnl_history = list(d.get("paper_pnl_history", []))
        run.trade_count = int(d.get("trade_count", 0))
        run.total_sim_pnl = float(d.get("total_sim_pnl", 0.0))
        run.total_paper_pnl = float(d.get("total_paper_pnl", 0.0))
        return run

    @property
    def days_elapsed(self) -> float:
        return _days_elapsed(self.start_ts)


# ---------------------------------------------------------------------------
# Statistical helpers
# ---------------------------------------------------------------------------


def _welch_t_pvalue(a: list[float], b: list[float]) -> float:
    """Two-sample Welch t-test p-value.  Returns 1.0 (not significant) for tiny samples."""
    na, nb = len(a), len(b)
    if na < 3 or nb < 3:
        return 1.0

    mean_a = sum(a) / na
    mean_b = sum(b) / nb
    var_a = sum((x - mean_a) ** 2 for x in a) / (na - 1) if na > 1 else 0.0
    var_b = sum((x - mean_b) ** 2 for x in b) / (nb - 1) if nb > 1 else 0.0

    se2 = var_a / na + var_b / nb
    if se2 <= 0:
        return 1.0 if mean_a == mean_b else 0.0

    t_stat = (mean_a - mean_b) / math.sqrt(se2)

    # Welch-Satterthwaite degrees of freedom (approximation)
    df_num = se2**2
    df_den = (var_a / na) ** 2 / max(na - 1, 1) + (var_b / nb) ** 2 / max(nb - 1, 1)
    df = df_num / df_den if df_den > 0 else 1.0

    # Two-tailed p-value approximation via survival function of t-distribution
    # Uses a simple numerical approximation for df > 3.
    x = df / (df + t_stat**2)
    # Regularized incomplete beta function approximation (Abramowitz & Stegun 26.5)
    # For our purposes, a conservative approximation is sufficient.
    try:
        half_p = 0.5 * _regularized_inc_beta(df / 2.0, 0.5, x)
        return float(min(1.0, 2.0 * half_p))
    except Exception:
        logging.exception("Unhandled broad exception fallback in lumina_core/evolution/shadow_deployment.py:132")
        return 1.0


def _regularized_inc_beta(a: float, b: float, x: float) -> float:
    """Continued-fraction approximation of I_x(a, b) for p-value calculation."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0

    # Use symmetry for better convergence
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - _regularized_inc_beta(b, a, 1.0 - x)

    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1.0 - x) * b - lbeta) / a

    # Lentz's continued fraction
    cf = 1.0
    d = 1.0 - (a + b) * x / (a + 1.0)
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    cf = d

    for m in range(1, 200):
        # Even step
        num = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + num / cf if abs(cf) > 1e-30 else 1.0 + num
        d = 1.0 / d
        cf *= c * d

        # Odd step
        num = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + num / cf if abs(cf) > 1e-30 else 1.0 + num
        d = 1.0 / d
        delta = c * d
        cf *= delta

        if abs(delta - 1.0) < 1e-10:
            break

    return front * cf


def _cohens_d(a: list[float], b: list[float]) -> float:
    """Cohen's d effect size between two samples."""
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 0.0
    mean_a = sum(a) / na
    mean_b = sum(b) / nb
    var_a = sum((x - mean_a) ** 2 for x in a) / (na - 1)
    var_b = sum((x - mean_b) ** 2 for x in b) / (nb - 1)
    pooled_std = math.sqrt(((na - 1) * var_a + (nb - 1) * var_b) / (na + nb - 2))
    if pooled_std <= 0:
        return 0.0
    return (mean_a - mean_b) / pooled_std


def _sample_sharpe(series: list[float]) -> float:
    n = len(series)
    if n < 5:
        return 0.0
    mean = sum(series) / n
    var = sum((x - mean) ** 2 for x in series) / max(1, n - 1)
    std = math.sqrt(max(var, 0.0))
    if std <= 1e-12:
        if mean > 0:
            return 10.0
        if mean < 0:
            return -10.0
        return 0.0
    return float(mean / std)


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------


