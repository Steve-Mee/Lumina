from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RegimeThreshold:
    min_trades: int
    min_winrate: float
    min_sharpe: float
    max_drawdown: float


class StressSuiteRunner:
    """Deterministic stress overlay runner for financial quality reporting."""

    _REGIME_THRESHOLDS: dict[str, RegimeThreshold] = {
        "TRENDING": RegimeThreshold(min_trades=20, min_winrate=0.40, min_sharpe=0.30, max_drawdown=1800.0),
        "RANGING": RegimeThreshold(min_trades=20, min_winrate=0.38, min_sharpe=0.20, max_drawdown=1700.0),
        "HIGH_VOLATILITY": RegimeThreshold(min_trades=15, min_winrate=0.33, min_sharpe=0.05, max_drawdown=2200.0),
        "ROLLOVER": RegimeThreshold(min_trades=10, min_winrate=0.30, min_sharpe=-0.10, max_drawdown=2400.0),
    }

    _ALIASES: dict[str, str] = {
        "VOLATILE": "HIGH_VOLATILITY",
        "HIGH_VOL": "HIGH_VOLATILITY",
        "BREAKOUT": "TRENDING",
    }

    def build_report(self, metrics_realism: dict[str, Any]) -> dict[str, Any]:
        base_pnl = float(metrics_realism.get("pnl_realized", 0.0) or 0.0)
        base_dd = float(metrics_realism.get("max_drawdown", 0.0) or 0.0)
        base_var_breach = int(metrics_realism.get("var_breach_count", 0) or 0)

        scenarios = {
            "volatility_spike": {
                "pnl_realized": round(base_pnl * 0.55, 2),
                "max_drawdown": round(base_dd * 1.45, 2),
                "var_breach_count": base_var_breach + 2,
            },
            "liquidity_shock": {
                "pnl_realized": round(base_pnl * 0.62, 2),
                "max_drawdown": round(base_dd * 1.32, 2),
                "var_breach_count": base_var_breach + 1,
            },
            "correlation_breakdown": {
                "pnl_realized": round(base_pnl * 0.48, 2),
                "max_drawdown": round(base_dd * 1.58, 2),
                "var_breach_count": base_var_breach + 3,
            },
        }

        worst_drawdown = max(float(v["max_drawdown"]) for v in scenarios.values())
        worst_var_breach = max(int(v["var_breach_count"]) for v in scenarios.values())
        var_breach_limit = 2
        drawdown_limit = max(500.0, base_dd * 2.0)
        gate_checks = {
            "var_breach_limit": worst_var_breach <= var_breach_limit,
            "drawdown_limit": worst_drawdown <= drawdown_limit,
        }
        gate_fail_reasons: list[str] = []
        if not gate_checks["var_breach_limit"]:
            gate_fail_reasons.append(f"VAR_BREACH_LIMIT_EXCEEDED(actual={worst_var_breach},limit={var_breach_limit})")
        if not gate_checks["drawdown_limit"]:
            gate_fail_reasons.append(
                f"DRAWDOWN_LIMIT_EXCEEDED(actual={round(worst_drawdown, 2)},limit={round(drawdown_limit, 2)})"
            )
        ready_for_real = all(gate_checks.values())

        return {
            "method": "deterministic_overlay_v1",
            "scenarios": scenarios,
            "worst_case_drawdown": round(worst_drawdown, 2),
            "worst_case_var_breach_count": int(worst_var_breach),
            "gate_checks": gate_checks,
            "gate_thresholds": {
                "var_breach_limit": int(var_breach_limit),
                "drawdown_limit": round(float(drawdown_limit), 2),
            },
            "gate_fail_reasons": gate_fail_reasons,
            "stress_ready_for_real_gate": bool(ready_for_real),
        }

    def build_regime_scorecard(self, regime_results: dict[str, Any], stress_report: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, dict[str, Any]] = {}
        for raw_name, values in dict(regime_results or {}).items():
            canonical = self._canonical_regime(raw_name)
            if canonical not in self._REGIME_THRESHOLDS or not isinstance(values, dict):
                continue
            normalized[canonical] = values

        scorecard: dict[str, Any] = {}
        missing_regimes: list[str] = []
        for regime, thresholds in self._REGIME_THRESHOLDS.items():
            data = normalized.get(regime)
            if data is None:
                missing_regimes.append(regime)
                scorecard[regime] = {
                    "status": "missing",
                    "reason": "no_oos_results",
                }
                continue

            trades = int(data.get("trades", 0) or 0)
            winrate = float(data.get("winrate", 0.0) or 0.0)
            sharpe = float(data.get("sharpe", 0.0) or 0.0)
            maxdd = float(data.get("maxdd", 0.0) or 0.0)

            checks = {
                "trades": trades >= thresholds.min_trades,
                "winrate": winrate >= thresholds.min_winrate,
                "sharpe": sharpe >= thresholds.min_sharpe,
                "drawdown": maxdd <= thresholds.max_drawdown,
            }
            passed = all(checks.values())
            scorecard[regime] = {
                "status": "pass" if passed else "fail",
                "checks": checks,
                "metrics": {
                    "trades": trades,
                    "winrate": round(winrate, 4),
                    "sharpe": round(sharpe, 4),
                    "maxdd": round(maxdd, 2),
                },
                "thresholds": {
                    "min_trades": thresholds.min_trades,
                    "min_winrate": thresholds.min_winrate,
                    "min_sharpe": thresholds.min_sharpe,
                    "max_drawdown": thresholds.max_drawdown,
                },
            }

        regimes_passed = all(scorecard.get(k, {}).get("status") == "pass" for k in self._REGIME_THRESHOLDS)
        stress_gate = bool(stress_report.get("stress_ready_for_real_gate", False))
        overall_pass = regimes_passed and stress_gate and not missing_regimes
        failure_reasons: list[str] = []
        if missing_regimes:
            failure_reasons.append("MISSING_REGIME_COVERAGE")
        if not regimes_passed:
            failure_reasons.append("REGIME_THRESHOLD_FAILURE")
        if not stress_gate:
            stress_reasons = stress_report.get("gate_fail_reasons")
            if isinstance(stress_reasons, list) and stress_reasons:
                failure_reasons.extend(str(item) for item in stress_reasons)
            else:
                failure_reasons.append("STRESS_GATE_FAILED")

        return {
            "required_regimes": list(self._REGIME_THRESHOLDS.keys()),
            "scorecard": scorecard,
            "missing_regimes": missing_regimes,
            "stress_ready_for_real_gate": stress_gate,
            "overall_pass": overall_pass,
            "gate_failure_reasons": failure_reasons,
            "promotion_advice": "promote_candidate" if overall_pass else "hold_and_retrain",
        }

    def build_validation_pack(self, metrics_realism: dict[str, Any], regime_results: dict[str, Any]) -> dict[str, Any]:
        stress_report = self.build_report(metrics_realism)
        regime_scorecard = self.build_regime_scorecard(regime_results, stress_report)
        return {
            "method": "regime_validation_pack_v1",
            "stress_report": stress_report,
            "regime_scorecard": regime_scorecard,
            "ready_for_real": bool(regime_scorecard.get("overall_pass", False)),
        }

    def _canonical_regime(self, regime: str) -> str:
        key = str(regime or "").strip().upper()
        return self._ALIASES.get(key, key)
