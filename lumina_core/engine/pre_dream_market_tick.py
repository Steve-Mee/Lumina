"""
PreDreamMarketTickService — D2 sub-slice 24: price/regime/RL/fast-path tick from PreDreamDaemon.

Pre-gate surface; fast-path skip returns should_continue for daemon sleep+continue.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from lumina_core.engine.price_dupe_resolver import PriceDupeResolver
from lumina_core.engine.rl_bias_applier import RlBiasApplier

logger = logging.getLogger(__name__)

_live_feed_fastpath_last_mono = 0.0
_LIVE_FEED_FASTPATH_LOG_INTERVAL_S = 90.0


@dataclass(slots=True)
class PreDreamMarketTickResult:
    should_continue: bool
    price: float | None = None
    df: Any | None = None
    regime: str | None = None
    structure: Any | None = None
    rl_signal: str | None = None
    rl_action: dict[str, Any] | None = None


class PreDreamMarketTickService:
    """Bounded owner for pre-dream market tick + fast-path gate (D2 sub-slice 24)."""

    def __init__(self, *, app: Any) -> None:
        self.app = app
        self._logger = getattr(app, "logger", logger)

    @staticmethod
    def _apply_rl_bias(rl_signal: str, fast_result: dict[str, Any]) -> dict[str, Any]:
        if rl_signal in {"BUY", "SELL"} and not fast_result.get("used_llm", False):
            fast_result = dict(fast_result)
            fast_result["used_llm"] = True
            fast_result["pass_to_llm"] = True
        return fast_result

    def run_tick(self) -> PreDreamMarketTickResult:
        """Price/regime/RL/fast-path tick (verbatim from PreDreamDaemon.run loop head)."""
        global _live_feed_fastpath_last_mono
        app = self.app

        price, df = PriceDupeResolver(app=app).fetch_locked_price_and_ohlc()

        regime = app.detect_market_regime(df)
        app.regime_history.append({"ts": datetime.now().isoformat(), "regime": regime})
        structure = app.detect_market_structure(df)

        rl_signal, rl_action = RlBiasApplier(app=app).predict_cycle_signal()

        fast_result = app.engine.fast_path.run(df, price, regime)
        fast_result = self._apply_rl_bias(rl_signal, fast_result)
        if not fast_result["used_llm"]:
            now_mono = time.monotonic()
            if now_mono - _live_feed_fastpath_last_mono >= _LIVE_FEED_FASTPATH_LOG_INTERVAL_S:
                _live_feed_fastpath_last_mono = now_mono
                (self._logger or logger).info(
                    "LIVE_FEED_DAEMON_IDLE,worker=pre_dream,reason=fast_path_no_llm_branch,"
                    "ohlc_bars=%s,note=no_chart_until_used_llm_true",
                    len(df),
                )
            return PreDreamMarketTickResult(should_continue=True)

        (self._logger or logger).info(
            "LIVE_FEED_DAEMON_STEP,worker=pre_dream,stage=llm_branch_entered,used_llm=true,ohlc_bars=%s",
            len(df),
        )

        return PreDreamMarketTickResult(
            should_continue=False,
            price=float(price),
            df=df,
            regime=regime,
            structure=structure,
            rl_signal=rl_signal,
            rl_action=rl_action,
        )
