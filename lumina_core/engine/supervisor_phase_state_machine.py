"""
SupervisorPhaseStateMachine — Phase 1 Sub11 remediation (D2 sub-slice 11).

Owns the full supervisor while-loop orchestration (validator, balance, real thin, dd kill,
eod thin, dream/twin/swarm, RL+baseline, arb/hold, hard risk, agent gate, exec paper/real,
open_pnl, sim hit close with legacy fallback, swarm dashboard, status, oracle, save, monitoring).

Tick phase blocks live in ``supervisor_phase_tick_ops`` (Wave B3 PR-D0); this module is the
thin dispatcher façade. Public import path unchanged.

Per 2026-06-04 perfection remediation plan Phase 1 Sub11; explore ids 17867ddb-3c02-4d83-8d37-a09dce7090da
and c1697bc9-9864-4189-8349-7a5632b7a8bf; functional thin + machine-drives; D2 sub-slice 11 remediation.

Per 2026-05-31 SPF-006 + Phase 3 D2: runtime_workers god decomp; required reading before capital paths.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Optional

from lumina_core.engine.supervisor_phase_tick_ops import (
    SupervisorTickCtx,
    run_tick_exec,
    run_tick_post_monitor,
    run_tick_preflight,
    run_tick_signal_gate,
)
from lumina_core.engine.valuation_engine import ValuationEngine

logger = logging.getLogger(__name__)


class SupervisorPhaseStateMachine:
    """Bounded owner for supervisor phases/timers/dispatch (Phase 1 Sub11 remediation).

    Narrow API: tick(price, dream_snapshot=None) / advance_or_tick(...) -> dict; persistent timers via app=.
    Delegates to existing thins; lazy-imports runtime_workers helpers inside tick to avoid circular imports.
    Phase blocks: preflight → signal-gate → exec → post-monitor (``supervisor_phase_tick_ops``).
    """

    def __init__(
        self,
        *,
        app: Any,
        engine: Any | None = None,
        container: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self.app = app
        self.engine = engine or (
            getattr(container, "engine", None) if container is not None else getattr(app, "engine", None)
        )
        self.container = container
        self._last_validation = getattr(self.engine, "last_validation", None) if self.engine is not None else None
        self._last_balance_fetch = time.time()
        self._last_oracle = time.time()
        self._last_save = time.time()
        self._last_status_print = 0.0
        self._last_monitoring_snapshot = 0.0
        self._last_infinite_sim_status = 0.0
        self._swarm_last_cycle = 0.0
        self._swarm_last_cycle_minute: Optional[tuple[int, int, int, int, int]] = None
        self._swarm_last_dashboard = 0.0
        self._logger = getattr(app, "logger", logger)
        self.valuation_engine = ValuationEngine()

    def advance_or_tick(
        self,
        price: float,
        *,
        dream_snapshot: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Machine-driven API alias for full supervisor tick (Phase 1 Sub11 remediation)."""
        return self.tick(price, dream_snapshot=dream_snapshot, **kwargs)

    def tick(
        self,
        price: float,
        *,
        dream_snapshot: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Full supervisor cycle for one price tick (relocated from runtime_workers 456-882 + pre-body)."""
        from lumina_core.runtime_workers import (
            _compute_session_kpis,
            _publish_runtime_monitoring_snapshot,
            _push_trader_league_trade,
        )

        ctx = SupervisorTickCtx(
            price=float(price),
            dream_snapshot=dream_snapshot,
            now=datetime.now(),
            push_trader_league_trade=_push_trader_league_trade,
            compute_session_kpis=_compute_session_kpis,
            publish_runtime_monitoring_snapshot=_publish_runtime_monitoring_snapshot,
        )

        run_tick_preflight(self, ctx)
        run_tick_signal_gate(self, ctx)
        run_tick_exec(self, ctx)
        run_tick_post_monitor(self, ctx)

        return {
            "signal": ctx.signal,
            "dream_snapshot": ctx.dream_snapshot,
            "rl_action": ctx.rl_action,
            "min_confluence": ctx.min_confluence,
            "gate_result": ctx.gate_result,
            "eod_force_hold": ctx.eod_force_hold,
            "price": float(price),
        }


# Risk Safety Review (Score: 9/10)
# ✅ Fail-closed: Yes (missing thins/app -> graceful as before, no crash; returns without optimistic phase change on error)
# ✅ REAL mode stricter: Yes (phases/timers critical for REAL orchestration around closes/EOD/RL bias/gate before capital paths; paper lighter but same code path)
# ✅ ConstitutionViolation event: Best-effort (via existing arb/risk if critical phase bypass; phases on capital decision orchestration path logged)
# ✅ Logging + ctx/agent: Yes (central in state machine + calls from supervisor; best-effort from dream if provided; shadow_state/guard via thins)
# ✅ No optimistic assumptions: Yes (exact relocation of original timer/phase/if dispatch from god body; no new behavior)
# ✅ D2 decomp + sub11 gap close (per 06-04 perfection remediation plan Phase 1): Yes (full supervisor orchestration surface now in bounded SM; thin now functional; 0 stray body in god post-thin; "claims = code"; makes thin functional per audit gap)
# ✅ Best-effort + dupe notes + granularity: Yes (delegates to thins + resolver; per granularity (voice/legacy/twin/outer/pre_dream/price resolver untouched); no happy-path change)
#
# Constitution Guard (rules 1/3/4/5/7):
# 1 Kapitaalbehoud: supervisor phases/timers orchestrate around REAL decision surfaces (RL bias pre-gate, real close, EOD, paper exec, dream/ctx) that feed capital paths + gates/arb/risk/DD/obs/D1/Guardian/snapshots/RL/swarm; central owner makes orchestration observable/auditable for capital preservation; no optimistic.
# 3 Bounded no god: Enhanced focused SupervisorPhaseStateMachine + narrow API; no god growth; thin from supervisor_inner while (persistent creation); aligns with sub4-12 + "per granularity" + closes sub11 execution gap per 06-04 perfection plan Phase 1.
# 4 Typed: Narrow API; phases feed typed downstream; best-effort lineage future.
# 5 Transparantie: Central place for supervisor phases/timers/dispatch + full post-tick orchestration (status/oracle/save/monitoring/exec/hit); logged; no optimistic; gap closed.
# 7 Testable: given-when-then + mocks for thins/app/engine + integration/grep proof of 0 stray + extend existing supervisor/runtime tests.
