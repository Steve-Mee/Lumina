"""
PreDreamConsensusPreambleService — D2 sub-slice 23: chart/consensus/meta preamble from PreDreamDaemon.

Pre-gate surface: multi-agent consensus + meta reasoning + cycle decision_context_id origin (Slice 12).
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PreDreamConsensusPreambleResult:
    should_continue: bool
    consensus: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    rl_context: str | None = None
    past_experiences: Any | None = None
    chart_base64: str | None = None
    min_conf: float | None = None
    cycle_decision_context_id: str | None = None
    blackboard: Any | None = None


class PreDreamConsensusPreambleService:
    """Bounded owner for chart gen + consensus + meta + ctx origin (D2 sub-slice 23)."""

    def __init__(self, *, app: Any) -> None:
        self.app = app
        self._logger = getattr(app, "logger", logger)

    def run_preamble(
        self,
        *,
        price: float,
        df: Any,
        regime: str,
        structure: Any,
        rl_signal: str,
        rl_action: dict[str, Any] | None,
    ) -> PreDreamConsensusPreambleResult:
        """Chart/consensus/meta preamble (verbatim from PreDreamDaemon.run LLM branch)."""
        app = self.app

        recent_winrate = (
            float(app.np.mean(app.np.array(app.pnl_history[-15:]) > 0)) if len(app.pnl_history) > 10 else 0.5
        )
        min_conf = app.calculate_dynamic_confluence(regime, recent_winrate)

        mtf_data = app.get_mtf_snapshots()
        _, _, fib_levels = app.detect_swing_and_fibs()
        pa_summary = app.generate_price_action_summary()

        chart_base64 = app.generate_multi_tf_chart()
        if not chart_base64:
            (self._logger or logger).info(
                "LIVE_FEED_DAEMON_ABORT,worker=pre_dream,stage=after_chart_gen,result=null,sleep_s=12,"
                "hint=inspect_prior_LIVE_FEED_CHART_GEN_ABORT_or_ABORT_log_lines",
            )
            return PreDreamConsensusPreambleResult(should_continue=True)

        (self._logger or logger).info(
            "LIVE_FEED_DAEMON_STEP,worker=pre_dream,stage=after_chart_gen,result=ok,b64_chars=%s",
            len(chart_base64),
        )

        if chart_base64:
            app.update_live_chart(chart_base64, status_msg="AI Decision & Chart updated")

        log_structured(
            LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="INFO_PRINT_LEGACY",
                message="🤖 Multi-agent consensus started...",
                context={},
            )
        )
        consensus = asyncio.run(app.multi_agent_consensus(price, mtf_data, pa_summary, structure, fib_levels))

        rl_context = (
            f"RL signal {rl_signal} | qty {float(rl_action.get('qty_pct', 1.0)):.2f} | "
            f"stop x{float(rl_action.get('stop_mult', 1.0)):.2f} | "
            f"target x{float(rl_action.get('target_mult', 1.0)):.2f}"
            if isinstance(rl_action, dict)
            else "RL signal HOLD | qty 1.00 | stop x1.00 | target x1.00"
        )

        query = f"Prijs {price:.2f} | Regime {regime} | {rl_context} | {pa_summary[:100]}"
        past_experiences = app.retrieve_relevant_experiences(query, n_results=4)

        log_structured(
            LuminaError(
                severity=ErrorSeverity.RECOVERABLE_LEARNING,
                code="INFO_PRINT_LEGACY",
                message="🧠 Meta-reasoning and counterfactuals started...",
                context={},
            )
        )
        meta = asyncio.run(app.meta_reasoning_and_counterfactuals(consensus, price, pa_summary, past_experiences))

        app.world_model = app.update_world_model(df, regime, pa_summary)
        blackboard = getattr(app, "blackboard", None)

        cycle_decision_context_id = f"dream_cycle:{uuid.uuid4().hex[:12]}"

        return PreDreamConsensusPreambleResult(
            should_continue=False,
            consensus=consensus,
            meta=meta,
            rl_context=rl_context,
            past_experiences=past_experiences,
            chart_base64=chart_base64,
            min_conf=min_conf,
            cycle_decision_context_id=cycle_decision_context_id,
            blackboard=blackboard,
        )
