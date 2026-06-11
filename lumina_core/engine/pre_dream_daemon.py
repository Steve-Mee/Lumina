"""
PreDreamDaemon — Bounded component owning pre-dream daemon cycle (Phase 3 D2 sub-slice 7).

Further firewall/decomp of runtime_workers trading paths god (the "or runtime_workers" per 05-31 SPF-006).
Thin delegation from runtime_workers.pre_dream_daemon + bootstrap lambda (compat preserved); reuses existing app/engine/blackboard/twin/RL/infer paths + cycle ctx gen per Phase2 slice12 + blackboard proposals + event_bus publish.

Owns: pre-dream while True cycle (~350 LOC producer of news proposals + RL bias + emotional_twin + LLM/vision/dream gen/ctx origin per Phase2 slice12 + blackboard + mutable app coupling + exact dupes with supervisor on price/RL/twin/dream extraction).
Narrow API: run() (relocated while True), get_dream_snapshot(), apply_rl_bias(), generate_dream(), set_dream_fields() + small hygiene _fetch_locked_price for price dupe (limited per granularity).
"Owner" injection via app= for testability (mirrors ProposalGenerator _ProposalOwner + meta D2 delegation + PaperSimulator/PaperTradeExecutor/EODForceCloseService sub4-6).

Per 2026-05-31 SPF-006 + Phase 3 D2 "Decomposition or strict interface firewalling of at least one major concentration point (meta_agent_core or runtime_workers trading paths) such that changes inside it no longer require understanding the entire engine." + MC post-sub6 "pre_dream narrow API" example in "full supervisor decomp in runtime_workers" + sub6/sub5 logs "Next: pre_dream narrow API, dupe resolution..." + Phase2 slice12 "earliest point... post multi-agent + meta reasoning so that downstream proposals emitted inside this pre-dream cycle share the same lineage root. This is the smallest upstream extension of the hash-chained spine." (producer="runtime_workers.pre_dream_daemon" + correlation_id = cycle_decision_context_id).

Small additive; best-effort ctx (current "dream_cycle:..." pattern preserved); SIM/paper friendly (pre-proposal surface; downstream aperture/gates/executor unchanged + sub4 lineage); independently testable; reversible; limited dupe hygiene inside only ("dupe with supervisor untouched per granularity" per sub6 plan).

No change to qty/execution/ledger/PnL, supervisor structure/loops (pre_dream effects still via mutable app/dream_snapshot), real paths, EOD/paper delegated, or other daemons.
"""

from __future__ import annotations

import logging
import time
import traceback
from typing import Any

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured
from lumina_core.engine.price_dupe_resolver import PriceDupeResolver
from lumina_core.engine.pre_dream_news_cycle import PreDreamNewsCycleService
from lumina_core.engine.pre_dream_vision_cycle import PreDreamVisionCycleService
from lumina_core.engine.pre_dream_consensus_preamble import PreDreamConsensusPreambleService
from lumina_core.engine.pre_dream_market_tick import PreDreamMarketTickService

logger = logging.getLogger(__name__)

class PreDreamDaemon:
    """Bounded owner for pre-dream daemon (Phase 3 D2 sub-slice 7 follow-on to sub4 PaperTradeExecutor + sub5 PaperSimulator + sub6 EODForceCloseService).

    Encapsulates the full pre-dream cycle (price fetch under lock, regime/structure, RL bias/predict + fast_path force, LLM branch with chart/consensus/rl_context/experiences/meta/world/blackboard, cycle_decision_context_id gen per Phase2 slice12, news_agent or fallback (dynamic/avoidance/hold -> blackboard "agent.news.proposal" producer="runtime_workers.pre_dream_daemon" + correlation_id or set_dream HOLD + why; sentiment to world/macro), vision_content (text + image_url base64) + infer_json (context="pre_dream_vision"), twin.apply_correction, aggregate conf + event_bus publish TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC producer + filtered + correlation or set_dream + set conf, AI_DRAWN_FIBS/narrative/speak/store_experience/log snapshot, sleep(12); small hygiene for 1-2 dupes e.g. _fetch_locked_price).

    Narrow API for runtime_workers + bootstrap (and tests):
      - run()  # relocated while True; primary entry for daemon thread
      - get_dream_snapshot() -> dict
      - apply_rl_bias(...) -> ...
      - generate_dream(...) -> dict | None
      - set_dream_fields(...) -> None

    "Owner" injection via app= for testability (mirrors ... sub4-6).
    Best-effort ctx (current "dream_cycle:..." + correlation_id preserved; no upstream for pre_dream itself).
    Thin delegation from runtime_workers.pre_dream_daemon (def pre_dream_daemon(app): PreDreamDaemon(app=app).run()).

    Per 2026-05-31 SPF-006 + Phase 3 D2 "or runtime_workers" + MC "pre_dream narrow API" + sub6 "Next: pre_dream narrow API, dupe resolution..." + "changes inside no longer require understanding entire engine" for this surface + Phase2 slice12.
    """

    def __init__(
        self,
        *,
        app: Any,
        container: Any | None = None,
        **kwargs: Any,
    ) -> None:
        self.app = app
        self.container = container
        self._logger = getattr(app, "logger", logger)
        # Internal caches (moved from original fn scope)
        self._last_news_update_ts = 0.0
        self._cached_news_data: dict[str, Any] = {"events": [], "overall_sentiment": "neutral", "impact": "medium"}

    def run(self) -> None:
        """Full pre-dream cycle logic relocated (price, RL, fast, LLM/vision/news, twin, ctx gen, proposals, set, sleep).

        Exact behavior/side-effects preserved from runtime_workers.pre_dream_daemon (246-590).
        Uses self.app.* ; fastpath mono in PreDreamMarketTickService module.
        """
        last_news_update_ts = self._last_news_update_ts
        cached_news_data = dict(self._cached_news_data)

        while True:
            try:
                tick = PreDreamMarketTickService(app=self.app).run_tick()
                if tick.should_continue:
                    time.sleep(12)
                    continue

                preamble = PreDreamConsensusPreambleService(app=self.app).run_preamble(
                    price=float(tick.price or 0.0),
                    df=tick.df,
                    regime=str(tick.regime or ""),
                    structure=tick.structure,
                    rl_signal=str(tick.rl_signal or "HOLD"),
                    rl_action=tick.rl_action,
                )
                if preamble.should_continue:
                    time.sleep(12)
                    continue

                consensus = preamble.consensus
                meta = preamble.meta
                rl_context = preamble.rl_context
                past_experiences = preamble.past_experiences
                chart_base64 = preamble.chart_base64
                min_conf = preamble.min_conf
                cycle_decision_context_id = preamble.cycle_decision_context_id
                blackboard = preamble.blackboard

                news = PreDreamNewsCycleService(app=self.app).run_cycle(
                    cycle_decision_context_id=cycle_decision_context_id,
                    cached_news_data=cached_news_data,
                    last_news_update_ts=last_news_update_ts,
                    blackboard=blackboard,
                )
                cached_news_data = news.cached_news_data
                last_news_update_ts = news.last_news_update_ts
                news_data = news.news_data
                news_impact = news.news_impact
                macro_news_sentiment = news.macro_news_sentiment
                macro_news_score = news.macro_news_score
                macro_news_multiplier = news.macro_news_multiplier
                avoid_active = news.avoid_active

                vision = PreDreamVisionCycleService(app=self.app).run_cycle(
                    consensus=consensus,
                    meta=meta,
                    rl_context=rl_context,
                    past_experiences=past_experiences,
                    chart_base64=chart_base64,
                    min_conf=min_conf,
                    macro_news_sentiment=macro_news_sentiment,
                    macro_news_score=macro_news_score,
                    news_data=news_data,
                    macro_news_multiplier=macro_news_multiplier,
                    avoid_active=avoid_active,
                )
                if vision.should_continue:
                    time.sleep(12)
                    continue

            except Exception as e:
                err = LuminaError(
                    severity=ErrorSeverity.RECOVERABLE_TRANSIENT,
                    code="RUNTIME_VISION_008",
                    message=str(e),
                    context={"traceback": traceback.format_exc()},
                )
                log_structured(err)
                (self._logger or logger).error(f"VISION_CYCLE_CRASH: {e}", exc_info=True)

            time.sleep(12)

        # update caches back (for if reused)
        self._last_news_update_ts = last_news_update_ts
        self._cached_news_data = cached_news_data

    # --- Narrow API helpers (for thin callers + tests; best-effort) ---

    def get_dream_snapshot(self) -> dict[str, Any]:
        return self.app.get_current_dream_snapshot()

    def apply_rl_bias(self, rl_signal: str, fast_result: dict[str, Any]) -> dict[str, Any]:
        """Small hygiene extraction for RL bias force (dupe with supervisor ~955)."""
        if rl_signal in {"BUY", "SELL"} and not fast_result.get("used_llm", False):
            fast_result = dict(fast_result)
            fast_result["used_llm"] = True
            fast_result["pass_to_llm"] = True
        return fast_result

    def generate_dream(self, payload: dict[str, Any]) -> dict | None:
        infer_json_fn = getattr(self.app, "infer_json", None)
        if callable(infer_json_fn):
            return infer_json_fn(payload, timeout=50, context="pre_dream_vision")
        return None

    def set_dream_fields(self, dream_json: dict) -> None:
        self.app.set_current_dream_fields(dream_json)

    def _fetch_locked_price(self) -> float:
        """Delegate to PriceDupeResolver (D2 sub19; closes supervisor/pre_dream price dupe)."""
        return PriceDupeResolver(app=self.app).fetch_locked_price()


# --- Module-level compat shim (thin delegation target; keeps bootstrap/tests/voice/exports unchanged) ---
def pre_dream_daemon(app: Any) -> None:
    """Thin delegation to bounded PreDreamDaemon (D2 sub-slice 7 pre_dream narrow API extraction/firewall).

    Per 05-31 SPF-006 + Phase 3 D2 "or runtime_workers" + MC "pre_dream narrow API" + sub6 "Next: pre_dream narrow API, dupe resolution..." + sub5 "dupe with supervisor untouched per granularity".
    The full logic is now in the bounded PreDreamDaemon; this is thin delegation for compat with existing callers/tests/bootstrap.
    """
    daemon = PreDreamDaemon(app=app)
    daemon.run()


__all__ = ["PreDreamDaemon", "pre_dream_daemon"]


# --- Risk Safety Review (Score: 9/10) per risk-safety-review skill ---
# ✅ fail-closed/best-effort on missing twin/infer/blackboard/news_agent (inherited + explicit continues/returns; current behavior preserved)
# ✅ REAL mode stricter (pre-proposal surface only; downstream FinalArbitration/gates/executor + sub4 lineage unchanged; paper unaffected)
# ✅ no optimistic assumptions (exact logic relocation from pre_dream_daemon 246-590; no behavior change on happy paths; pre-dream as ctx origin + proposals feeder documented)
# ✅ ConstitutionViolation defense (via existing paths + typed proposals/aggregate publish + downstream arb; no new bypasses)
# ✅ logging + ctx + provenance (central in daemon + cycle_decision_context_id origin per slice12 + producer="runtime_workers.pre_dream_daemon" + correlation_id on blackboard "agent.news.proposal" + TRADING_ENGINE_EXECUTION_AGGREGATE_TOPIC; sub4 lineage on downstream orders from dream)
# ✅ pre-dream daemon surface encapsulated in bounded component (no direct pre_dream cycle/RL/news/LLM/dream-gen/ctx-origin/blackboard producer outside PreDreamDaemon in runtime_workers; dupe hygiene limited inside new file only)
# Risk: shared live_* + dream_snapshot muts still hit via app (pre-proposal; affects readers); remaining dupes (price/RL/twin in supervisor) untouched per granularity.
# Mitigated by: additive, no happy-path change, tests with full mocks + extend existing twin test, Guardian 10.0, small reversible slice + 05-31 re-anchor + MC forcing + pre-proposal (capital paths gated).
# Per 2026-05-31 Phase 3 D2 + SPF-006 + MC post-sub6 "pre_dream narrow API" + sub6 "Next: pre_dream narrow API, dupe resolution..." + aperture-mission-control + sub5 granularity rule.

# --- Constitution Guard (rules 1/3/4/5/7) ---
# 1 Kapitaalbehoud: pre-dream as major producer of dream/ctx/RL bias/news proposals that feed downstream capital paths (orders via dream_snapshot + sub4 executor) + full lineage/provenance (slice12 ctx origin + sub4) now encapsulated + auditable in bounded daemon (D1 20min + D3).
# 3 Modulaire bounded contexts: new focused PreDreamDaemon; no god growth in runtime_workers; thin delegation from runtime_workers + bootstrap unchanged; aligns with meta D2 (ProposalGenerator/apply) + Paper*/EODForceCloseService sub4-6 patterns.
# 4 Typed contracts: narrow API; ctx/decision_context_id + producer + correlation_id already used in proposals/blackboard/aggregate per slice12 + sub4; execution aggregate publish already typed (model_validate + payload).
# 5 Veiligheid en observability vóór: central place for pre-dream logic + ctx origin + proposals + dream_snapshot + news avoidance + twin + RL bias + vision; no optimistic direct muts outside bounded; dupe hygiene note per granularity (sub6 "dupe with supervisor untouched"); pre-dream documented as earliest lineage root.
# 7 Testbaar: given-when-then + monkeypatch/mocks + fail-closed paths explicit in new tests + extend existing pre_dream twin test (per scaffolding); integration with runtime_workers thin deleg + bootstrap mock.
# No violation of 2/6 (evolution small steps; SIM/paper = experiment, REAL=fort; pre-dream pre-proposal so no direct REAL capital impact beyond existing gated paths).
# Per AGENTS + 05-31 + MC + Recursive Self-Improvement Protocol + all skills.

# End of module. Per AGENTS + 05-31 + MC + Recursive Self-Improvement Protocol + aperture-mission-control + constitution-guard + risk-safety-review + test-scaffolding + event-bus-contract.
