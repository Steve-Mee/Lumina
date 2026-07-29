"""PlateauEvolutionMixin — StageLoopSession mixin.

Bounded modules: ``plateau_evolution_actions``, ``plateau_evolution_loop``.
Dispatches over ``plateau_evolution_ladder`` / ``plateau_escalator``.
"""
from __future__ import annotations

from lumina_core.birth.plateau_escalator import rolling_winrate_last_n_trades
from lumina_core.birth.plateau_evolution_actions import PlateauEvolutionActionsMixin
from lumina_core.birth.plateau_evolution_loop import PlateauEvolutionLoopMixin
from lumina_core.birth.stage_loop_mixin_base import StageLoopMixinBase


class PlateauEvolutionMixin(
    PlateauEvolutionActionsMixin,
    PlateauEvolutionLoopMixin,
    StageLoopMixinBase,
):
    """See StageLoopSession for attributes."""

    def _rolling_winrate_500(self) -> float:
        chunks = getattr(self, "rolling_trade_chunks", None)
        result = rolling_winrate_last_n_trades(
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            wins_at_trade=getattr(self, "wins_at_trade_milestones", {}) or {},
            chunks=chunks if isinstance(chunks, list) else None,
            return_meta=True,
        )
        if isinstance(result, tuple):
            wr, source, covered = result
            self._rolling_winrate_source = str(source)
            self._rolling_window_trades_covered = int(covered)
            return float(wr)
        return float(result)

    def _rolling_winrate_meta(self) -> tuple[float, str, int]:
        chunks = getattr(self, "rolling_trade_chunks", None)
        result = rolling_winrate_last_n_trades(
            stage_trades=self.stage_trades,
            stage_wins=self.stage_wins,
            wins_at_trade=getattr(self, "wins_at_trade_milestones", {}) or {},
            chunks=chunks if isinstance(chunks, list) else None,
            return_meta=True,
        )
        if isinstance(result, tuple):
            return float(result[0]), str(result[1]), int(result[2])
        return float(result), "lifetime_fallback", 0

    def _ppo_steps_since_evolution_step(self) -> int:
        return max(0, int(self.host.ppo_steps) - int(self.ppo_steps_at_plateau_evolution_step))


__all__ = ["PlateauEvolutionMixin"]
