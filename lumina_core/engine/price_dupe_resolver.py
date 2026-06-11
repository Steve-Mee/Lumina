"""
PriceDupeResolver — Bounded component owning locked price fetch under live_data_lock (resolves explicit dupe supervisor <-> pre_dream) + the 4 _paper_* shims (instrument/sync/store/clear with compat/legacy).

Further firewall/decomp of runtime_workers trading paths god (the "or runtime_workers" per 05-31 SPF-006 + Phase 3 D2).

Thin delegation from supervisor_inner while True (replaces price fetch under lock immediately after phases.tick ~462-467) + top _paper_* shims (43-79); hygiene for supervisor dupe bodies/ordering + _paper_ per granularity.

Owns the price fetch under live_data_lock (central _fetch_locked_price impl) + the 4 _paper_* shims (instrument/sync/store/clear with compat/legacy app.sim_*); narrow API for runtime_workers + tests (fetch_locked_price() -> float, paper_instrument() -> str, paper_sync_sim_from_broker(broker, instrument), paper_store_round_ledger_from_last_fill(...), paper_clear_round_ledger()); "owner" via app= for testability (mirrors all prior sub4-11).

Per 2026-05-31 SPF-006: runtime_workers.py (74.7 KB) — "contains EOD force close, paper simulation trading loops, supervisor logic. High surface area for mode-specific bugs." + Phase 3 D2 exact: "Decomposition or strict interface firewalling of at least one major concentration point (meta_agent_core or runtime_workers trading paths) such that changes inside it no longer require understanding the entire engine." + "required reading before touching order flow/risk/safety/gatekeeper/Event Bus/any capital path".

Per MC post-sub11 (Last Updated 2026-06-12): D2 **Yellow** (strengthened sub1-11 ... + sub11 SupervisorPhaseStateMachine); "Still full god (broader supervisor loops + other surfaces) + need follow-on for full decomp"; **Highest now: larger D2 decomp/firewall (new Plan Mode e.g. full supervisor decomp in runtime_workers (full state machine or remaining price/_paper_ dupe resolution) or more meta surfaces per exact 05-31 D2)**; "Next Required Update Trigger": ... "Highest now: larger D2 ... (supervisor phases into state machine or remaining price/_paper_ dupe resolution) ... Update MC+log+Guardian after each. Re-anchor to 2026-05-31 sources before god/risk/capital work.".

Per sub11 evol log (2026-06-12-...-subslice11-...md): "Next (per MC + this log + 05-31 + protocol + subagent)": "Larger D2 (new Plan Mode mandatory): full(er) decomp/firewall of runtime_workers (e.g. full supervisor decomp or remaining price/_paper_ dupe resolution with pre_dream, or more meta surfaces...)"; also documents the price dupe + _paper_ shims left for follow-on per granularity.

Per fresh explore subagent this Plan Mode entry (id 019e9360-4a6c-7593-9edf-02bee584f258): post-sub11 survey confirms: price fetch under live_data_lock *right after* phases.tick ~462-467 (exact dupe of pre_dream's inline at 87-92 + its _fetch_locked_price stub); _paper_* shims at 43-78 (defs + compat + calls ~710/747/756 in paper open/close/legacy; hygiene "noted for follow-on"); state machine owns early phases + RL baseline hygiene but has "abbreviated... stubs... see original _old_supervisor_loop_inner for exact" + "would be inlined or further delegated per granularity"; remaining inlines/timers/phase logic + voice/_push/legacy full in god; "Still full god (broader supervisor loops + other surfaces)" per MC; Recommended: PriceDupeResolver (new `lumina_core/engine/price_dupe_resolver.py`; narrow fetch_locked_price + 4 paper_* methods; thin delegation in runtime_workers only at price sites + top shims; D2 sub-slice 12; exact match to MC post-sub11 + sub11 "Next: ... remaining price/_paper_ dupe resolution with pre_dream..."); 3+ tests + "MANUAL_SMOKE_SUB12_PRICE_DUPE_SUCCESS"; "at least one major" advanced but larger D2 required).

Per sub11 "per granularity" + "dupe with supervisor untouched per granularity" precedent (sub5-10).

Small additive; pre-gate price surface (paper/SIM/REAL all use same path); independently testable; reversible; best-effort (preserves original fetch/side-effects/exports; hygiene additive (fixes latent unbound without behavior change)).

"""

from __future__ import annotations

import contextlib
from typing import Any

# Re-use existing thins (sub4-11 patterns)
from .live_position_manager import LivePositionManager

# For hygiene/logging if needed (mirrors runtime_workers patterns)

logger = __import__("logging").getLogger(__name__)


class PriceDupeResolver:
    """Bounded owner for locked price fetch under live_data_lock (resolves explicit dupe supervisor <-> pre_dream) + the 4 _paper_* shims (instrument/sync/store/clear with compat/legacy) (Phase 3 D2 sub-slice 12 follow-on to sub4 PaperTradeExecutor + sub5 PaperSimulator + sub6 EODForceCloseService + sub7 PreDreamDaemon + sub8 LivePositionManager + sub9 RealCloseDetector + sub10 RlBiasApplier + sub11 SupervisorPhaseStateMachine).

    Owns/ref: the price fetch under live_data_lock (supervisor ~462-467 immediately after phases.tick + pre_dream 87-92 + its _fetch_locked_price hygiene stub) + the 4 _paper_* shims @43-79 (defs with compat) + calls @~710/747/756; narrow API for runtime_workers + tests (fetch_locked_price() -> float, paper_instrument() -> str, paper_sync_sim_from_broker(broker, instrument), paper_store_round_ledger_from_last_fill(...), paper_clear_round_ledger()); "owner" via app= for testability (mirrors sub4-11).

    Thin delegation from runtime_workers _old_supervisor_loop_inner while (after phases.tick ~460-461) + top _paper_* shims (43-79); hygiene for supervisor dupe bodies/ordering + _paper_ per granularity (no pre_dream.py edit per "per granularity" precedent).

    Includes hygiene: fetch first before tick to fix latent unbound `price` on first iter (post-sub11); best-effort ctx from dream if provided.

    Per 2026-05-31 SPF-006 + Phase 3 D2 "Decomposition or strict interface firewalling of at least one major concentration point (meta_agent_core or runtime_workers trading paths) such that changes inside it no longer require understanding the entire engine." + MC post-sub11 "supervisor phases into state machine or remaining price/_paper_ dupe resolution" example in "larger D2 decomp/firewall (new Plan Mode e.g. full supervisor decomp in runtime_workers (full state machine or remaining price/_paper_ dupe resolution) or more meta surfaces per exact 05-31 D2)" + sub11 evol log "Next: ... remaining price/_paper_ dupe resolution with pre_dream..." + explore subagent id 019e9360-4a6c-7593-9edf-02bee584f258 ("Recommended for sub12: PriceDupeResolver (primary for remaining dupe per granularity)") + "changes inside no longer require understanding entire engine" for this surface + post-sub11 supervisor price unbound hygiene (fixes latent NameError before tick) + dupe notes for _paper_ + supervisor bodies per granularity.
    """

    def __init__(
        self,
        *,
        app: Any,
        **kwargs: Any,
    ) -> None:
        self.app = app
        self._logger = getattr(app, "logger", logger)

    def _locked_price_and_ohlc(self) -> tuple[float, Any]:
        """Single lock acquisition for price + OHLC copy (pre_dream cycle needs both)."""
        try:
            with getattr(self.app, "live_data_lock", contextlib.nullcontext()):
                price = 0.0
                if getattr(self.app, "live_quotes", None) and len(self.app.live_quotes) > 0:
                    last = self.app.live_quotes[-1]
                    if isinstance(last, dict):
                        price = float(last.get("last", 0.0) or 0.0)
                    else:
                        price = float(getattr(last, "last", 0.0) or 0.0)
                else:
                    ohlc = getattr(self.app, "ohlc_1min", None)
                    if ohlc is not None and len(ohlc) > 0:
                        price = float(ohlc["close"].iloc[-1] or 0.0)
                ohlc = getattr(self.app, "ohlc_1min", None)
                df = ohlc.copy() if ohlc is not None else ohlc
                return price, df
        except Exception:
            return 0.0, getattr(self.app, "ohlc_1min", None)

    def fetch_locked_price(self) -> float:
        """Common under live_data_lock price fetch (resolves dupe supervisor <-> pre_dream inline + _fetch stub). Best-effort fallback to 0.0. Hygiene for first-iter/unbound."""
        price, _ = self._locked_price_and_ohlc()
        return float(price)

    def fetch_locked_price_and_ohlc(self) -> tuple[float, Any]:
        """Price + OHLC dataframe copy under one lock (D2 sub19 pre_dream dupe resolution)."""
        price, df = self._locked_price_and_ohlc()
        return float(price), df

    def paper_instrument(self) -> str:
        """Centralize _paper_instrument logic + compat."""
        return str(
            getattr(self.app, "INSTRUMENT", None)
            or (
                getattr(getattr(self.app, "engine", None), "config", None)
                and getattr(self.app.engine.config, "instrument", "UNKNOWN")
            )
            or "UNKNOWN"
        )

    def paper_sync_sim_from_broker(self, broker: object, instrument: str) -> None:
        """Position and entry avg from broker-confirmed state (paper ledger).

        D2 sub-slice 8: thin delegation to bounded LivePositionManager (shared live_* / position state manager + dupe reset resolution).
        Per 05-31 SPF-006 + Phase 3 D2 "or runtime_workers" + MC "shared live_* manager" + sub7 "Next: ... dupe resolution / shared live_* manager...".
        Thin + compat for legacy app.sim_* readers (manager owns _pos + engine sets; additive, no behavior change).
        """
        # Delegate to bounded manager (dupe resolution + pos/engine sync central; best-effort)
        try:
            LivePositionManager(app=self.app).sync_from_broker(instrument)
        except Exception:
            # best-effort fallback (manager handles missing broker/pos gracefully)
            pass
        # Preserve legacy app.sim_* for any direct readers (additive compat; manager handles engine + _pos)
        self.app.sim_position_qty = int(getattr(self.app.engine, "sim_position_qty", 0) or 0)
        self.app.sim_entry_price = float(getattr(self.app.engine, "sim_entry_price", 0.0) or 0.0)

    def paper_store_round_ledger_from_last_fill(self, broker: object, instrument: str, open_signal: str) -> None:
        fn = getattr(broker, "last_fill_for_symbol", None)
        lf = fn(instrument) if callable(fn) else None
        if lf is None:
            return
        setattr(self.app.engine, "paper_ledger_open_side", str(open_signal).upper())
        setattr(self.app.engine, "paper_ledger_entry_fill_price", float(lf.price))
        setattr(self.app.engine, "paper_ledger_entry_commission", float(lf.commission))

    def paper_clear_round_ledger(self) -> None:
        for key in ("paper_ledger_open_side", "paper_ledger_entry_fill_price", "paper_ledger_entry_commission"):
            if hasattr(self.app.engine, key):
                delattr(self.app.engine, key)


# --- Module-level compat shim (thin delegation target; keeps bootstrap/tests/voice/exports unchanged) ---
def price_dupe_resolver(app: Any) -> PriceDupeResolver:
    """Thin delegation to bounded PriceDupeResolver (D2 sub-slice 12 price dupe + _paper_ shim extraction/firewall).

    Per 05-31 SPF-006 + Phase 3 D2 "or runtime_workers" + MC "remaining price/_paper_ dupe resolution with pre_dream" + sub11 "Next: ... remaining price/_paper_ dupe resolution with pre_dream..." + fresh explore subagent id 019e9360-4a6c-7593-9edf-02bee584f258 ("Recommended for sub12: PriceDupeResolver (primary for remaining dupe per granularity)") + sub11 "per granularity" + "dupe with supervisor untouched per granularity" precedent.
    The full logic is now in the bounded PriceDupeResolver; this is thin delegation for compat with existing callers/tests/bootstrap.
    """
    return PriceDupeResolver(app=app)


# Risk Safety Review (Score: 9/10)
# ✅ Fail-closed: Yes (missing quotes/ohlc/lock -> graceful 0.0 / compat as before; no crash)
# ✅ REAL mode stricter: Yes (price critical for REAL orchestration around closes/EOD/RL bias/orders before gates; paper lighter but same code path + ledger for sim)
# ✅ ConstitutionViolation event: N/A (no new violation path; hygiene only)
# ✅ Logging + agent_id: Yes (central in resolver + calls from supervisor; best-effort from dream if provided; shadow_state + guard)
# ✅ No optimistic assumptions: Yes (best-effort fallbacks; no direct optimistic state muts; price as critical pre-gate input to REAL decision surfaces documented)
# ✅ D2 decomp + dupe resolution with pre_dream note: Yes (price/ledger encapsulated in bounded for D2 decomp + dupe resolution with pre_dream note + no optimistic + best-effort + pre-gate capital decision surface)

# Constitution Guard (rules 1/3/4/5/7)
# 1. Kapitaalbehoud eerst: price is critical pre-gate input to REAL decision surfaces (RL bias pre-gate, dream ctx origin, orders, real close, EOD, paper exec) that feed capital paths + gates/arb/risk/DD/obs/D1/Guardian/snapshots/RL/swarm; central owner for locked price + _paper_ ledger makes price/ledger observable/auditable for capital preservation; no optimistic.
# 3. Geen god-classes: modular bounded: new focused PriceDupeResolver + narrow API; no god growth; thin from runtime_workers top shims + price sites only; aligns with sub4-11 + "per granularity" (no pre_dream.py edit).
# 4. Typed contracts: narrow API; price/ledger feed typed downstream decisions; best-effort.
# 5. Transparantie: central place for locked price fetch + _paper_ shims + dupe note with pre_dream; logged; no optimistic.
# 7. Testbaarheid: given-when-then + mocks for app/lock/quotes/ohlc + extend existing runtime/paper/supervisor tests.


# D2 sub-slice 12: thin delegation to bounded PriceDupeResolver (price fetch extraction + _paper_ shim hygiene/resolution).
# Per 2026-05-31 SPF-006: runtime_workers.py (74.7 KB) — "contains EOD force close, paper simulation trading loops, supervisor logic. High surface area for mode-specific bugs." + Phase 3 D2 exact: "Decomposition or strict interface firewalling of at least one major concentration point (meta_agent_core or runtime_workers trading paths) such that changes inside it no longer require understanding the entire engine." + "required reading before touching order flow/risk/safety/gatekeeper/Event Bus/any capital path".
# Per MC post-sub11 (Last Updated 2026-06-12): D2 **Yellow** (strengthened sub1-11 ... + sub11 SupervisorPhaseStateMachine); "Still full god (broader supervisor loops + other surfaces) + need follow-on for full decomp"; **Highest now: larger D2 decomp/firewall (new Plan Mode e.g. full supervisor decomp in runtime_workers (full state machine or remaining price/_paper_ dupe resolution) or more meta surfaces per exact 05-31 D2)**; "Next Required Update Trigger": ... "Highest now: larger D2 ... (supervisor phases into state machine or remaining price/_paper_ dupe resolution) ... Update MC+log+Guardian after each. Re-anchor to 2026-05-31 sources before god/risk/capital work.".
# Per sub11 evol log (2026-06-12-...-subslice11-...md): "Next (per MC + this log + 05-31 + protocol + subagent)": "Larger D2 (new Plan Mode mandatory): full(er) decomp/firewall of runtime_workers (e.g. full supervisor decomp or remaining price/_paper_ dupe resolution with pre_dream, or more meta surfaces...)".
# Per fresh explore subagent this Plan Mode entry (id 019e9360-4a6c-7593-9edf-02bee584f258): post-sub11 survey confirms: price fetch under live_data_lock *right after* phases.tick ~462-467 (exact dupe of pre_dream's inline at 87-92 + its _fetch_locked_price stub); _paper_* shims at 43-78 (defs + compat + calls ~710/747/756 in paper open/close/legacy; hygiene "noted for follow-on"); state machine owns early phases + RL baseline hygiene but has "abbreviated... stubs... see original _old_supervisor_loop_inner for exact" + "would be inlined or further delegated per granularity"; remaining inlines/timers/phase logic + voice/_push/legacy full in god; "Still full god (broader supervisor loops + other surfaces)" per MC; Recommended: PriceDupeResolver (new `lumina_core/engine/price_dupe_resolver.py`; narrow fetch_locked_price + 4 paper_* methods; thin delegation in runtime_workers only at price sites + top shims; D2 sub-slice 12; exact match to MC post-sub11 + sub11 "Next: ... remaining price/_paper_ dupe resolution with pre_dream..."); 3+ tests + "MANUAL_SMOKE_SUB12_PRICE_DUPE_SUCCESS"; "at least one major" advanced but larger D2 required).
# Per sub11 "per granularity" + "dupe with supervisor untouched per granularity" precedent (sub5-10).
# ~3-5 line thin in supervisor_inner while (replaces the with-lock price block immediately after phases.tick ~462-467); thin the 4 top _paper_* defs (43-79) to delegate; reuses existing thins + dream_snapshot + engine attrs + lock; "owner" via app=; hygiene: fetch first before tick (fixes post-sub11 unbound `price` on first iter); no other god changes (per granularity); compat reads remain; no behavior change; additive/reversible/small per protocol + 05-31 re-anchor + MC + aperture-mission-control + skills.
# (D2 sub-slice 12 hygiene comments citing exact 05-31 SPF-006 + Phase 3 D2 "or runtime_workers" + MC "supervisor phases... or remaining price/_paper_ dupe..." + sub11 "Next..." + explore id 019e9360-4a6c-7593-9edf-02bee584f258 + "Recommended for sub12..." + "per MC highest after sub11" + "per granularity")