"""ShadowDeploymentTracker verdict / A-B methods."""
from __future__ import annotations

from typing import Any

from lumina_core.logging_utils import get_logger, log_shadow_verdict
from lumina_core.evolution.shadow_helpers import (
    ShadowVerdict,
    _cohens_d,
    _sample_sharpe,
    _welch_t_pvalue,
)

logger = get_logger("lumina.evolution.shadow")

class ShadowTrackerVerdictMixin:
    """compute_shadow_verdict + run_shadow_ab."""

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
            if run.days_elapsed >= self._min_days and run.trade_count < self._min_trades:
                try:
                    logger.warning(
                        "shadow.expired_insufficient_trades",
                        extra={
                            "event_data": {
                                "event": "shadow.expired_insufficient_trades",
                                "dna_hash": dna_hash[:12],
                                "shadow_run_id": dna_hash[:12],
                                "days_elapsed": run.days_elapsed,
                                "trade_count": run.trade_count,
                                "min_trades": self._min_trades,
                            }
                        },
                    )
                except Exception:
                    pass
            return "pending"

        sim_pnl = list(run.sim_pnl_history)
        paper_pnl = list(run.paper_pnl_history)

        # Strict path: compare paper variant vs sim control with statistical gate.
        if len(sim_pnl) >= self._min_trades and len(paper_pnl) >= self._min_trades:
            ab = self.run_shadow_ab(sim_pnl, paper_pnl, n_min=self._min_trades)
            verdict = str(ab.get("verdict", "inconclusive"))
            paper_sharpe = _sample_sharpe(paper_pnl)
            if verdict == "variant_wins" and paper_sharpe >= 0.3:
                try:
                    log_shadow_verdict(
                        logger,
                        dna_hash[:12],
                        {
                            "decision": "pass",
                            "pvalue": float(ab.get("pvalue", 1.0) or 1.0),
                            "cohen_d": float(ab.get("cohens_d", 0.0) or 0.0),
                            "sharpe": paper_sharpe,
                        },
                    )
                except Exception:
                    pass
                return "pass"
            if verdict == "control_wins" or (verdict == "inconclusive" and paper_sharpe < 0.0):
                try:
                    logger.warning(
                        "shadow.verdict.fail",
                        extra={
                            "event_data": {
                                "event": "shadow.verdict.fail",
                                "dna_hash": dna_hash[:12],
                                "shadow_run_id": dna_hash[:12],
                                "verdict": verdict,
                                "sharpe": paper_sharpe,
                                "pvalue": float(ab.get("pvalue", 1.0) or 1.0),
                                "cohen_d": float(ab.get("cohens_d", 0.0) or 0.0),
                            }
                        },
                    )
                except Exception:
                    pass
                return "fail"
            return "pending"

        # Fallback path when only one stream has enough samples.
        pnl_history = paper_pnl if len(paper_pnl) >= len(sim_pnl) else sim_pnl
        if len(pnl_history) < self._min_trades:
            return "pending"
        mean_pnl = sum(pnl_history) / len(pnl_history)
        sharpe_like = _sample_sharpe(pnl_history)
        if mean_pnl > 0.0 and sharpe_like >= 0.3:
            try:
                log_shadow_verdict(
                    logger,
                    dna_hash[:12],
                    {"decision": "pass", "mean_pnl": mean_pnl, "sharpe": sharpe_like},
                )
            except Exception:
                pass
            return "pass"
        try:
            logger.warning(
                "shadow.verdict.fail",
                extra={
                    "event_data": {
                        "event": "shadow.verdict.fail",
                        "dna_hash": dna_hash[:12],
                        "shadow_run_id": dna_hash[:12],
                        "mean_pnl": mean_pnl,
                        "sharpe": sharpe_like,
                    }
                },
            )
        except Exception:
            pass
        return "fail"
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
        try:
            logger.debug(
                "shadow.ab_test",
                extra={
                    "event_data": {
                        "event": "shadow.ab_test",
                        "n_control": n_ctrl,
                        "n_variant": n_var,
                        "mean_control": mean_ctrl,
                        "mean_variant": mean_var,
                        "pvalue": pvalue,
                        "cohens_d": d,
                    }
                },
            )
        except Exception:
            pass

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
