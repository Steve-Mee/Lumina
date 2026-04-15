from __future__ import annotations

from typing import Any


class StressSuiteRunner:
    """Deterministic stress overlay runner for financial quality reporting."""

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
        ready_for_real = worst_var_breach <= 2 and worst_drawdown <= max(500.0, base_dd * 2.0)

        return {
            "method": "deterministic_overlay_v1",
            "scenarios": scenarios,
            "worst_case_drawdown": round(worst_drawdown, 2),
            "worst_case_var_breach_count": int(worst_var_breach),
            "stress_ready_for_real_gate": bool(ready_for_real),
        }
