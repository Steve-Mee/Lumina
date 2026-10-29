"""P3 SIM plan only. This module does not start SIM, place orders, or open a session."""

from __future__ import annotations

from pathlib import Path

SIM_MIN_SURVIVORS = 3
SIM_MIN_TRADING_DAYS = 60
SIM_MIN_TRADES = 100
SIM_SHARPE_FLOOR_FRAC = 0.70
SIM_DD_MULT = 1.50


def sim_plan_markdown() -> str:
    return "\n".join(
        [
            "# Phase 5 P3 SIM plan (do not start in this PR)",
            "",
            "This is a plan. No SIM session, paper order, or live order is opened here.",
            "",
            "## Entry conditions (all required)",
            "",
            f"- At least {SIM_MIN_SURVIVORS} independent, low-correlation Validation Gate survivors.",
            "- Correlation is measured on OOS net returns; a cluster of MES+ES clones does not count as independent.",
            "- Survivors still carry a valid sealed gate passage. Risk Core is untouched.",
            "",
            "## Duration",
            "",
            f"- Run until **both** clocks are satisfied: >= {SIM_MIN_TRADING_DAYS} trading days **or**",
            f"  >= {SIM_MIN_TRADES} trades, **whichever is later**.",
            "- Live is not discussed until that clock completes and the band below holds.",
            "",
            "## Acceptable band",
            "",
            f"- Realized Sharpe not structurally below {SIM_SHARPE_FLOOR_FRAC:.0%} of median expected OOS.",
            f"- Drawdown not greater than {SIM_DD_MULT:.1f}x expected (same 1.5x material-break definition).",
            "- Structural underperformance over multiple windows → de-weight and return the name to research.",
            "- Capital-preservation violations must remain 0.",
            "",
            "## Fills and costs",
            "",
            "- Use the existing four-leg CostModel. Calibrate slippage/impact on SIM fills; do not retune gate floors.",
            "- Limit orders use trade-through plus a volume condition (or a probabilistic fill rate). No zero-slippage.",
            "- ES/NQ briefed average 0.5-1.5 ticks plus impact; MES/MNQ 1-2.5 ticks, modelled separately.",
            "",
            "## Forbidden in this PR",
            "",
            "- Starting a SIM session.",
            "- Placing, sizing, or cancelling orders.",
            "- Writing live Risk Core, PromotionGate, or Fabric state.",
            "",
        ]
    )


def write_sim_plan(directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "phase5_sim_plan.md"
    path.write_text(sim_plan_markdown() + "\n", encoding="utf-8")
    return path
