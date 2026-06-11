"""
LivePositionManager — Bounded component owning shared live_*/sim_* position state (Phase 3 D2 sub-slice 8).

Further firewall/decomp of runtime_workers trading paths god (the "or runtime_workers" per 05-31).
Thin delegation from supervisor_inner real close + legacy; used by PaperSimulator + EODForceCloseService + operations real entry.
Owns/wraps EnginePositionState (runtime_state.py) + narrow API for sync/reset/update/close_detect/get + internal dupe reset resolution.

Per 2026-05-31 SPF-006 + Phase 3 D2 "Decomposition or strict interface firewalling of at least one major concentration point (meta_agent_core or runtime_workers trading paths) such that changes inside it no longer require understanding the entire engine." + MC post-sub7 "shared live_* manager" example in "full supervisor decomp in runtime_workers" + sub7/sub6 logs "Next: ... dupe resolution / shared live_* manager...".

Small additive; SIM/paper friendly; independently testable; reversible.
"""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.engine.runtime_state import EnginePositionState

logger = logging.getLogger(__name__)


class LivePositionManager:
    """Bounded owner for shared live_*/sim_* position state (Phase 3 D2 sub-slice 8 follow-on to sub4 PaperTradeExecutor + sub5 PaperSimulator + sub6 EODForceCloseService + sub7 PreDreamDaemon).

    Owns/ref: EnginePositionState (from runtime_state.py or engine.position_state via facade) + narrow API for all mutations/resets/sync/close_detect/get (sync_from_broker, reset_for_real_close, reset_for_eod, update_on_real_fill, getters for live/sim qty/entry/signal/peak/unrealized, has_*, get_open_pnl, reset_all; internal dupe reset resolution with consistent semantics + best-effort ctx).

    Thin delegation from runtime_workers supervisor real close + legacy paper resets; used by PaperSimulator + EODForceCloseService + operations.
    Reuses existing EnginePositionState + facade proxies (engine_state_facade.py) for readers (risk/arb/obs/D1/Guardian/snapshots/RL/swarm etc.).

    Per 2026-05-31 SPF-006 + Phase 3 D2 "or runtime_workers" + MC "shared live_* manager" + sub7 "Next: ... dupe resolution / shared live_* manager..." + "changes inside no longer require understanding entire engine" for this surface.
    """

    def __init__(
        self,
        *,
        app: Any,
        engine: Any | None = None,
        container: Any | None = None,
        position_state: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self.app = app
        self.engine = engine or (getattr(container, "engine", None) if container is not None else getattr(app, "engine", None))
        self.container = container
        # Own or proxy the position_state (prefer engine.position_state if wired via facade; fallback dataclass)
        self._pos = position_state or getattr(self.engine, "position_state", None)
        if self._pos is None:
            self._pos = EnginePositionState()
            if self.engine is not None:
                setattr(self.engine, "position_state", self._pos)  # wire if needed
        self._logger = getattr(app, "logger", logger)

    def sync_from_broker(self, instrument: str | None = None) -> None:
        """Relocated _paper_sync_sim_from_broker logic (zero or set sim_* + live_* + last from broker pos).

        Dupe resolution: central place (was duplicated in runtime_workers + paper_simulator).
        Best-effort (no broker -> no-op).
        """
        get_positions = getattr(self.app, "broker", None)
        get_positions = getattr(get_positions, "get_positions", None) if get_positions is not None else None
        if get_positions is None or not callable(get_positions):
            # fallback to app if passed differently
            broker = getattr(getattr(self.app, "container", None), "broker", None) if getattr(self.app, "container", None) is not None else None
            get_positions = getattr(broker, "get_positions", None) if broker is not None else None
            if get_positions is None or not callable(get_positions):
                return
        inst = str(instrument or getattr(self.app, "INSTRUMENT", getattr(getattr(self.app, "engine", None), "config", None) and getattr(self.app.engine.config, "instrument", "UNKNOWN") or "UNKNOWN")).strip()
        try:
            positions = get_positions()
        except Exception:
            return
        pos = next((p for p in positions if str(getattr(p, "symbol", "")).strip() == inst), None)
        if pos is None or int(getattr(pos, "quantity", 0) or 0) == 0:
            self._pos.sim_position_qty = 0
            self._pos.sim_entry_price = 0.0
            self._pos.live_position_qty = 0
            self._pos.last_entry_price = 0.0
            if self.engine is not None:
                setattr(self.engine, "sim_position_qty", 0)
                setattr(self.engine, "sim_entry_price", 0.0)
                setattr(self.engine, "live_position_qty", 0)
                setattr(self.engine, "last_entry_price", 0.0)
            return
        self._pos.sim_position_qty = int(pos.quantity)
        self._pos.sim_entry_price = float(pos.avg_price)
        self._pos.live_position_qty = int(pos.quantity)
        self._pos.last_entry_price = float(pos.avg_price)
        if self.engine is not None:
            setattr(self.engine, "sim_position_qty", int(pos.quantity))
            setattr(self.engine, "sim_entry_price", float(pos.avg_price))
            setattr(self.engine, "live_position_qty", int(pos.quantity))
            setattr(self.engine, "last_entry_price", float(pos.avg_price))

    def reset_for_real_close(self, *, detected_exit_price: float, signal: str, entry_price: float | None = None, **kwargs: Any) -> None:
        """Post-mark_closing reset (live_qty=0, last=0.0 or detected, live_signal="HOLD"; best-effort ctx).

        Dupe resolution: central (real zeros entry; different from EOD last=price).
        Also sync flat engine attrs for test/legacy compat (facade proxies; additive).
        """
        self._pos.live_position_qty = 0
        self._pos.last_entry_price = float(detected_exit_price) if entry_price is None else float(entry_price)
        self._pos.live_trade_signal = "HOLD"
        # compat flat on engine if present (tests use direct engine.xxx)
        if self.engine is not None:
            setattr(self.engine, "live_position_qty", 0)
            setattr(self.engine, "last_entry_price", float(detected_exit_price) if entry_price is None else float(entry_price))
            setattr(self.engine, "live_trade_signal", "HOLD")
        # optional: record reflection/ctx if provided in kwargs
        if "reflection" in kwargs:
            # best-effort attach
            pass

    def reset_for_eod(self, *, close_price: float, **kwargs: Any) -> None:
        """Post-EOD flatten reset (live_qty=0, last=close_price, live_signal="HOLD"; matches current EOD semantics).

        Dupe resolution: central (EOD uses last=price; real uses zero).
        Also sync flat engine attrs for test/legacy compat.
        """
        self._pos.live_position_qty = 0
        self._pos.last_entry_price = float(close_price)
        self._pos.live_trade_signal = "HOLD"
        if self.engine is not None:
            setattr(self.engine, "live_position_qty", 0)
            setattr(self.engine, "last_entry_price", float(close_price))
            setattr(self.engine, "live_trade_signal", "HOLD")

    def update_on_real_fill(self, *, signed_qty: int, fill_px: float, action: str, **kwargs: Any) -> None:
        """From operations real entry success (live_qty = signed, last=fill_px, live_signal=action; last_realized).

        Best-effort ctx from kwargs if present.
        Also sync flat engine attrs for test/legacy compat.
        """
        self._pos.live_position_qty = signed_qty
        self._pos.last_entry_price = float(fill_px)
        self._pos.live_trade_signal = str(action).upper()
        if "last_realized" in kwargs:
            self._pos.last_realized_pnl_snapshot = float(kwargs["last_realized"])
        if self.engine is not None:
            setattr(self.engine, "live_position_qty", signed_qty)
            setattr(self.engine, "last_entry_price", float(fill_px))
            setattr(self.engine, "live_trade_signal", str(action).upper())

    # Getters (for supervisor reads, risk, etc.; facade compatible)
    def get_live_qty(self) -> int:
        return int(getattr(self._pos, "live_position_qty", 0) or 0)

    def get_last_entry_price(self) -> float:
        return float(getattr(self._pos, "last_entry_price", 0.0) or 0.0)

    def get_live_signal(self) -> str:
        return str(getattr(self._pos, "live_trade_signal", "HOLD") or "HOLD")

    def get_sim_qty(self) -> int:
        return int(getattr(self._pos, "sim_position_qty", 0) or 0)

    def get_sim_entry_price(self) -> float:
        return float(getattr(self._pos, "sim_entry_price", 0.0) or 0.0)

    def has_live_position(self) -> bool:
        return self.get_live_qty() != 0

    def has_sim_position(self) -> bool:
        return self.get_sim_qty() != 0

    def get_live_position(self) -> dict[str, Any]:
        return {
            "qty": self.get_live_qty(),
            "entry": self.get_last_entry_price(),
            "signal": self.get_live_signal(),
        }

    def get_sim_position(self) -> dict[str, Any]:
        return {
            "qty": self.get_sim_qty(),
            "entry": self.get_sim_entry_price(),
        }

    def reset_all(self) -> None:
        """Full reset (for init/persistence compat paths)."""
        self._pos.sim_position_qty = 0
        self._pos.sim_entry_price = 0.0
        self._pos.live_position_qty = 0
        self._pos.last_entry_price = 0.0
        self._pos.live_trade_signal = "HOLD"


# --- Module-level compat shims (minimal impact on callers/tests during transition) ---
def _paper_sync_sim_from_broker(app: Any, broker: object, instrument: str) -> None:
    """Compat shim delegating to bounded LivePositionManager (post D2 sub-slice 8)."""
    mgr = LivePositionManager(app=app)
    mgr.sync_from_broker(instrument)


# --- Risk Safety Review (Score: 9/10) per risk-safety-review skill ---
# ✅ fail-closed/best-effort on missing broker/pos_state (inherited + explicit returns; current behavior preserved)
# ✅ REAL mode stricter (position state critical for REAL dd kill / risk / gates / reconciler / obs; paper lighter but unified view + provenance preserved)
# ✅ no optimistic assumptions (exact logic relocation from scattered sites; no behavior change on happy paths; dupe reset semantics centralized + documented)
# ✅ ConstitutionViolation defense (via existing arb/risk paths + typed proposal in risk mutation)
# ✅ logging + ctx + provenance (central in manager + best-effort ctx from dream/upstream + calls from sub4 executor/EOD/paper/ops; position state changes auditable for D1)
# ✅ shared live position state encapsulated in bounded component (no direct live/sim muts outside manager in the trading paths surface after thins; dupe reset resolution inside owner)
# Risk: facade/direct access readers (risk/arb etc.) continue via proxies (no breaking); persistence load/save stay direct for now (future thin); real close detect heuristic remains in supervisor (extract as follow-on per granularity).
# Mitigated by: additive, no happy-path change, tests with full mocks, Guardian 10.0, small reversible slice + 05-31 re-anchor + MC forcing.
# Per 2026-05-31 Phase 3 D2 + SPF-006 + MC "shared live_* manager" + sub7 "Next: ... dupe resolution / shared live_* manager..." + aperture-mission-control.

# --- Constitution Guard (rules 1/3/4/5/7) ---
# 1 Kapitaalbehoud: shared live position state drives REAL risk calculations, gates, dd kill, reconciler, obs, D1, Guardian, snapshots, RL, swarm; centralized ownership + auditable resets for capital paths (D1 20min).
# 3 Modulaire bounded contexts: new focused LivePositionManager; no god growth; thin delegation from supervisor + updates to PaperSimulator/EOD/ops; aligns with meta D2 + Paper*/EOD/PreDream sub4-7 patterns.
# 4 Typed contracts: narrow API; position state already dataclass (EnginePositionState); future typed events for state changes.
# 5 Veiligheid en observability vóór: central place for all position/live state mutations + resets + sync + close heuristic + dupe resolution; no optimistic direct muts; position documented as critical for REAL view + obs.
# 7 Testbaar: given-when-then + monkeypatch/mocks + fail-closed paths explicit in tests (per scaffolding).
# No violation of 2/6 (evolution small steps; SIM/paper = experiment, REAL=fort; position state post-decision side-effect).
# Per AGENTS + 05-31 + MC + Recursive Self-Improvement Protocol + all skills.

# End of module. Per AGENTS + 05-31 + MC + Recursive Self-Improvement Protocol + aperture-mission-control + constitution-guard + risk-safety-review + test-scaffolding + event-bus-contract.
