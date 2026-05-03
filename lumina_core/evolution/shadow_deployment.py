"""ShadowDeploymentTracker — persistent shadow run management for Lumina v53.

A DNA candidate is placed in "shadow mode" before REAL promotion: it runs
alongside the live strategy in PAPER/SIM, and its PnL is tracked.  Only after
the shadow run meets the minimum duration, trade count, and Welch t-test
significance criteria is the candidate eligible for promotion.

State is persisted in ``state/evolution_shadow_runs.json`` (append-safe JSON).

Promotion criteria by mode:
  - REAL:   enforced via PromotionPolicy + PromotionGate (non-negotiable gate)
  - PAPER:  shadow PASS + twin_confidence >= 0.82
  - SIM:    no shadow gate (aggressive_evolution allowed)

Note:
  `compute_shadow_verdict()` is a local tracker heuristic used by legacy and
  experiment flows. REAL promotion authority lives in
  `PromotionPolicy.run_shadow_validation_gate()` and `PromotionGate.evaluate()`.
"""

from __future__ import annotations

import json
import logging
import math
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from lumina_core.config_loader import ConfigLoader

logger = logging.getLogger(__name__)

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


class ShadowDeploymentTracker:
    """Tracks shadow runs for DNA candidates and computes promotion verdicts.

    State is persisted as a JSON file so it survives restarts.
    Thread-safe for concurrent reads.
    """

    def __init__(
        self,
        *,
        state_path: Path | None = None,
        min_days: float | None = None,
        min_trades: int | None = None,
        pvalue_threshold: float = 0.1,
        effect_size_threshold: float = 0.2,
    ) -> None:
        self._path = state_path or _DEFAULT_SHADOW_PATH
        self._lock = threading.Lock()

        evo_cfg = ConfigLoader.section("evolution", default={}) or {}
        shadow_cfg = evo_cfg.get("shadow_validation", {}) if isinstance(evo_cfg, dict) else {}
        if not isinstance(shadow_cfg, dict):
            shadow_cfg = {}

        self._min_days = float(min_days if min_days is not None else shadow_cfg.get("min_days", 3))
        self._min_trades = int(min_trades if min_trades is not None else shadow_cfg.get("min_trades", 20))
        self._pvalue_threshold = float(pvalue_threshold)
        self._effect_size_threshold = float(effect_size_threshold)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, ShadowRun]:
        try:
            if not self._path.exists():
                return {}
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return {}
            return {k: ShadowRun.from_dict(v) for k, v in raw.items() if isinstance(v, dict)}
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("ShadowDeploymentTracker: failed to load state: %s", exc)
            return {}

    def _save(self, runs: dict[str, ShadowRun]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps({k: v.to_dict() for k, v in runs.items()}, indent=2),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("ShadowDeploymentTracker: failed to save state: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_shadow(self, dna_hash: str) -> ShadowRun:
        """Register a new shadow run for *dna_hash*.

        Idempotent — if the hash is already tracked and still running,
        the existing run is returned.
        """
        with self._lock:
            runs = self._load()
            existing = runs.get(dna_hash)
            if existing and existing.status == "running":
                logger.info("Shadow run already active for dna_hash=%s", dna_hash[:12])
                return existing

            run = ShadowRun(dna_hash=dna_hash)
            runs[dna_hash] = run
            self._save(runs)
            logger.info(
                "Shadow run started for dna_hash=%s (min_days=%.1f, min_trades=%d)",
                dna_hash[:12],
                self._min_days,
                self._min_trades,
            )
            return run

    def record_pnl(
        self,
        dna_hash: str,
        *,
        sim_pnl: float | None = None,
        paper_pnl: float | None = None,
    ) -> None:
        """Append a PnL observation to the shadow run."""
        with self._lock:
            runs = self._load()
            run = runs.get(dna_hash)
            if run is None or run.status != "running":
                return
            if sim_pnl is not None:
                run.sim_pnl_history.append(float(sim_pnl))
                run.total_sim_pnl += float(sim_pnl)
            if paper_pnl is not None:
                run.paper_pnl_history.append(float(paper_pnl))
                run.total_paper_pnl += float(paper_pnl)
            run.trade_count += 1
            self._save(runs)

    def is_shadow_complete(self, dna_hash: str) -> bool:
        """True when the minimum duration and trade count have been reached."""
        with self._lock:
            runs = self._load()
            run = runs.get(dna_hash)
        if run is None:
            return False
        return run.days_elapsed >= self._min_days and run.trade_count >= self._min_trades

    def compute_shadow_verdict(self, dna_hash: str) -> ShadowVerdict:
        """Return 'pass', 'fail', or 'pending' for the shadow run.

        Verdict logic:
          - pending:  not enough data (days or trades below minimum)
          - pass:     SIM PnL > 0 OR paper t-test shows significant improvement
          - fail:     candidate underperforms (negative expected PnL)

        This method is not the authoritative REAL promotion gate. REAL promotion
        is fail-closed through PromotionPolicy + PromotionGate before approval.
        """
        with self._lock:
            runs = self._load()
            run = runs.get(dna_hash)

        if run is None:
            return "pending"

        if not self.is_shadow_complete(dna_hash):
            return "pending"

        sim_pnl = list(run.sim_pnl_history)
        paper_pnl = list(run.paper_pnl_history)

        # Strict path: compare paper variant vs sim control with statistical gate.
        if len(sim_pnl) >= self._min_trades and len(paper_pnl) >= self._min_trades:
            ab = self.run_shadow_ab(sim_pnl, paper_pnl, n_min=self._min_trades)
            verdict = str(ab.get("verdict", "inconclusive"))
            paper_sharpe = _sample_sharpe(paper_pnl)
            if verdict == "variant_wins" and paper_sharpe >= 0.3:
                logger.info(
                    "Shadow PASS for dna_hash=%s via AB gate: pvalue=%.4f d=%.4f sharpe=%.3f",
                    dna_hash[:12],
                    float(ab.get("pvalue", 1.0) or 1.0),
                    float(ab.get("cohens_d", 0.0) or 0.0),
                    paper_sharpe,
                )
                return "pass"
            if verdict == "control_wins" or (verdict == "inconclusive" and paper_sharpe < 0.0):
                logger.info(
                    "Shadow FAIL for dna_hash=%s via AB gate: verdict=%s sharpe=%.3f",
                    dna_hash[:12],
                    verdict,
                    paper_sharpe,
                )
                return "fail"
            return "pending"

        # Fallback path when only one stream has enough samples.
        pnl_history = paper_pnl if len(paper_pnl) >= len(sim_pnl) else sim_pnl
        if len(pnl_history) < self._min_trades:
            return "pending"
        mean_pnl = sum(pnl_history) / len(pnl_history)
        sharpe_like = _sample_sharpe(pnl_history)
        if mean_pnl > 0.0 and sharpe_like >= 0.3:
            logger.info(
                "Shadow PASS for dna_hash=%s via single-stream gate: mean=%.2f sharpe=%.3f",
                dna_hash[:12],
                mean_pnl,
                sharpe_like,
            )
            return "pass"
        logger.info(
            "Shadow FAIL for dna_hash=%s via single-stream gate: mean=%.2f sharpe=%.3f",
            dna_hash[:12],
            mean_pnl,
            sharpe_like,
        )
        return "fail"

    def mark_promoted(self, dna_hash: str) -> None:
        """Mark the shadow run as promoted."""
        with self._lock:
            runs = self._load()
            if dna_hash in runs:
                runs[dna_hash].status = "promoted"
                runs[dna_hash].end_ts = _utcnow()
                self._save(runs)

    def run_shadow_ab(
        self,
        control_pnl: list[float],
        variant_pnl: list[float],
        *,
        n_min: int = 30,
    ) -> dict[str, Any]:
        """Statistical A/B test between two PnL distributions.

        Uses Welch t-test for significance and Cohen's d for effect size.
        The variant is promoted over control if:
          - Both have >= n_min observations
          - Welch p-value < pvalue_threshold
          - Cohen's d > effect_size_threshold
          - Variant mean PnL > control mean PnL

        Returns a dict with verdict ('variant_wins', 'control_wins', 'inconclusive').
        """
        n_ctrl = len(control_pnl)
        n_var = len(variant_pnl)

        if n_ctrl < n_min or n_var < n_min:
            return {
                "verdict": "inconclusive",
                "reason": f"insufficient_samples (control={n_ctrl}, variant={n_var}, min={n_min})",
                "n_control": n_ctrl,
                "n_variant": n_var,
            }

        mean_ctrl = sum(control_pnl) / n_ctrl
        mean_var = sum(variant_pnl) / n_var
        pvalue = _welch_t_pvalue(variant_pnl, control_pnl)
        d = _cohens_d(variant_pnl, control_pnl)

        significant = pvalue < self._pvalue_threshold
        large_enough = d > self._effect_size_threshold
        variant_better = mean_var > mean_ctrl

        if significant and large_enough and variant_better:
            verdict = "variant_wins"
        elif significant and large_enough and not variant_better:
            verdict = "control_wins"
        else:
            verdict = "inconclusive"

        return {
            "verdict": verdict,
            "n_control": n_ctrl,
            "n_variant": n_var,
            "mean_control_pnl": float(mean_ctrl),
            "mean_variant_pnl": float(mean_var),
            "pvalue": float(pvalue),
            "cohens_d": float(d),
            "significant": bool(significant),
            "effect_large_enough": bool(large_enough),
        }

    def get_all_runs(self) -> dict[str, ShadowRun]:
        with self._lock:
            return self._load()
