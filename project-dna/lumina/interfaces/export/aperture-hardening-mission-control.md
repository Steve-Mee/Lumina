# Aperture Hardening Mission Control

**Status**: Living forcing function. This is the single source of truth for progress against the original plan.

**Immutable Sources (read these first, always)**:
- `project-dna/lumina/evolution/log/2026-05-31-elon-musk-first-principles-trading-system-analysis.md` — The brutal first-principles diagnosis.
- `project-dna/lumina/evolution/log/2026-05-31-elon-aperture-hardening-90-day-roadmap.md` — The 90-day execution plan derived from the diagnosis.

**North Star Date (from original roadmap)**: 2026-08-29

**Purpose of this document**: Make it impossible to lose sight of the original revolutionary intent. No more "where are we?" friction. No more context fragmentation.

---

## Current Overall Position (Brutal Truth — 2026-05-31 snapshot)

- **Phase 0**: Complete
- **Phase 1 (incl. 1.3.4 zero-trace)**: Complete on the structural bypass removal. `aperture_guard.py` is now a permanent regression detector. All 4 FATAL bypasses (B-001..B-004) have zero traces in source, tests, and active DNA. This was the foundation.
- **Phase 2 — Structural Closure**: Partially executed. Significant progress on the cryptographic lineage spine, but the hardest and highest-leverage original deliverables are barely touched.
- **Phase 3 — Physics-Grade Observability & Simplification**: **Program slices Green-Yellow** (D1/D3/D4/D5/D6 + D2 runtime surface); **90-day success gate not met** (see close-out `2026-06-04-phase3-track-c-closeout.md`).

**Calendar reality**: The 90-day target (2026-08-29) is approaching or has pressure. We have spent the majority of the available time on excellent but narrow observability infrastructure (the 25-slice Typed Spine work) while the original Phase 2 deliverables 5 and the entire Phase 3 remain almost untouched.

**Elon verdict so far**: We have built a very clean, auditable chain. We have not yet made the capital aperture revolutionary in the full sense defined in the 2026-05-31 analysis. The "jaws dropping" outcome is still at risk of becoming "very solid engineering that most sophisticated teams could have done" instead of physics-grade, first-principles, order-of-magnitude safer autonomous capital allocation.

---

## Phase 2 — Structural Closure: Progress vs Original 6 Deliverables

From the 90-day roadmap (exact text preserved):

**Goal**: The three identified bypass mechanisms no longer exist in production code paths. The Event Bus is the primary (not side-channel) nervous system for trading decisions.

| # | Original Deliverable (verbatim) | Status | Evidence | Major Gaps / Risks | Honest Assessment |
|---|----------------------------------|--------|----------|--------------------|-------------------|
| 1 | Complete removal of the three skip layers (or reduction to a single, auditable, time-boxed "emergency experimental override") | Green | Phase 1.3.4 + aperture_guard as permanent FATAL detector. All B-00x removed with zero traces. | None material on the original bypasses. | Done correctly and thoroughly. |
| 2 | 100% of agent proposals, risk allocations, arbitration decisions, and order submissions published as typed events with full lineage (`decision_context_id` + `prev_hash` chaining) | **Green-Yellow** (live WS/poll + poll/get_fills) | CrossTrade `lookup_pending_lineage` shared: submit map → `get_fills` + **TradeReconciler WS/poll ingest** (`2026-06-11-phase2-ws-fill-lineage-overlay.md`). Typed `execution.fill.received` + decision_lineage see ctx on all live ingest paths. | Wire without submit context still best-effort (rare). Order-status WS channels out of scope. | Live production fills observable on WS + poll + get_fills paths. | 
| 3 | Subscribers to critical topics receive validated Pydantic model *instances* (not dicts) | **Green-Yellow** | D3 slices 1–4 (2026-06-04): `payload_instance` on bus + blackboard; `typed_payload_from_event` in bindings, gatekeeper, meta agents, `decision_lineage`, `dna_registry`. Reproduce: `python -m pytest tests/agent_orchestration/ tests/risk/test_decision_lineage_typed.py tests/test_dna_registry.py -q`. | Non-critical trackers/JSONL still dict export; `DomainEvent.payload` dict retained for backward compat. | Critical capital-path consumers migrated; not universal spine for every topic. |
| 4 | Cryptographic / hash-chained provenance for every decision that reaches Final Arbitration | Green-Yellow (live advanced) | `decision_lineage.py` + extend/build_pretrade + report/CLI + Guardian (screaming on critical fills) + auto broker.get_fills. Paper complete. CrossTrade now carries real ctx/prev from submit (pending overlay) → typed events → verified hash_ok in reconstruct/provenance for live fills. See log 2026-06-06-phase2-live-broker-lineage-wiring.md. | Best-effort overlay if no submit lineage (mitigated by policy attach); some mark_closing callers still omit ctx (ongoing). | Live production fills now have default observable cryptographic chain (not just paper). | 
| 5 | Extended shadow deployment: every evolution experiment that touches risk logic must run in a "shadow aperture" mode that replays real market data but never touches the live broker | **Yellow-Green** (practical coverage achieved) | Official thin bridge + validate helper + rich human review + structural hook (DNARegistry.mutate + PolicyDNA.create) + explicit high-fidelity wiring at all high-volume genetic/LLM/dream/promotion surfaces, **including the original SPF-003 god-component** (`meta_agent_core.py`). Fresh 2026-06-03 audit confirmed these are the only creation paths that carry risk hyperparams. All relevant shadow tests green. | Honest residual gaps (enumerated in 2026-06-03 evolution log): (1) Direct live config application path in `_apply_candidate` (the sole writer to engine.config max_risk/drawdown_kill) can still fire in auto-apply modes without fresh human shadow review at apply time. (2) Any future completely non-DNA risk mutation vector (none found in current codebase). (3) Fundamental best-effort nature of all call sites. No other live risk config mutation sites exist. | Practical coverage of the surfaces that mattered in the 2026-05-31 diagnosis. The creation of risk-affecting evolution experiments is now protected in all known high-volume paths. The mechanism is not yet hard-guaranteed. |
| 6 | DNA Guardian now has a permanent "Aperture" dimension in its health scoring and degradation detection | Yellow | Dimension exists. Baselines updated through Slice 25. Screaming logic for lineage present. | Guardian currently has a syntax error that prevents reliable daily runs. Not yet "permanent forcing function" in practice. | Good intent. Execution hygiene is currently broken. |

**Phase 2 Success Gate (original)**:
- Static + dynamic analysis proves 0 remaining bypass paths in non-experimental code → Mostly met.
- ≥ 80% of pre-trade decision volume flows through the typed Event Bus with models → Not met.
- Provenance reconstruction script exists and is used in at least one post-trade audit → Partially met (exists, usage unclear).
- No REAL or guard-mode incidents attributable to aperture changes → Unknown / unproven at scale.

---

## Phase 3 — Physics-Grade Observability & Simplification: Progress vs Original 6 Deliverables

**Goal (verbatim)**: The aperture is not only narrow and typed — it is the *easiest* and *most observable* way to reason about the system. Large orchestrators touching capital paths have been decomposed or firewalled.

| # | Original Deliverable | Status | Comment |
|---|----------------------|--------|---------|
| 1 | "One human, 20 minutes" audit: single script + markdown view showing complete provenance + constitution checks + risk numbers + agent lineage | **Green-Yellow** | `aperture_audit_artifact.py` + `d1_golden_path.py` + `scripts/phase3_d1_golden_path_verify.py` (genuine D4 ctx contract verify). 12+ audit/dna tests. Guardian D1 auto-audit + D3 ctx merge. Reproduce: `python scripts/phase3_d1_golden_path_verify.py`. | Longer multi-month live SIM campaigns optional. | Golden path on genuine D4 evidence (25 ctx bundle) verified 2026-06-04. |
| 2 | Decomposition or strict interface firewalling of at least one major concentration point (meta_agent_core or runtime_workers) | **Yellow** (first+second+third sub-slices on meta risk mutation (Pydantic+central apply+mandatory shadow+violation + creation helper in risk module, D5 gaps closed); + sub4: initial runtime_workers trading paths firewall (Paper/EOD Order sites now via bounded PaperTradeExecutor forcing full decision_context_id/prev_hash/metadata from dream/context; provenance on sim capital paths; advances "or runtime_workers" + Phase 2 lineage on all orders); + sub5: bounded PaperSimulator owning paper sim state + execution (thin deleg from supervisor_inner; uses PaperTradeExecutor; further decomp of runtime_workers trading god per 05-31 D2 + MC "full supervisor decomp in runtime_workers" example + sub4 "Next: full PaperSimulator owning state"); + sub6: bounded EODForceCloseService (thin deleg from supervisor_inner; EOD closer extraction per MC/sub5 Next; further decomp of runtime_workers trading god per 05-31 D2 + MC "EOD closer extraction" example + sub5 "Next: EOD closer extraction"); + sub7: bounded PreDreamDaemon (thin deleg from runtime_workers/bootstrap; pre_dream narrow API + dupe hygiene per MC/sub6 Next; further decomp of runtime_workers trading god per 05-31 D2 + MC "pre_dream narrow API" example + sub6 "Next: pre_dream narrow API, dupe resolution..."); + sub8: bounded LivePositionManager (shared live_* owner + thin deleg from runtime_workers (real close + legacy _paper_sync + paper close legacy) + paper_simulator + eod_force_close_service + operations_service; dupe reset resolution per MC "shared live_* manager" + sub7 "Next: ... dupe resolution / shared live_* manager..."; "at least one major" further progressed on second god) + sub9: bounded RealCloseDetector (real close detect heuristic + mark_closing/fallback/reflection + best-effort decision_context_id injection for last mark_closing caller + reset orchestration via LivePositionManage + sub10: bounded RlBiasApplier (RL bias extraction from supervisor_inner ~558 + dupe hygiene with pre_dream RL/apply_rl_bias per MC "full dupe resolution for _paper_*/RL/price with pre_dream" + sub9 "Next: full dupe resolution for _paper_*/RL/price with pre_dream..." + explore) + sub11: bounded SupervisorPhaseStateMachine (phases/timers/dispatch extraction from supervisor_inner while + baseline scope hygiene (post-sub10 baseline_signal fix) + dupe notes for price/_paper_ per MC "supervisor phases into state machine or remaining price/_paper_ dupe resolution" + sub10 "Next: supervisor phases into state machine, remaining price/_paper_ dupe resolution with pre_dream..." + explore); + sub12: bounded PriceDupeResolver (locked price dupe resolution + _paper_ shims extraction from runtime_workers + dupe note for pre_dream per MC "remaining price/_paper_ dupe resolution with pre_dream" + sub11 "Next: ... remaining price/_paper_ dupe resolution with pre_dream..." + explore id 019e9360-4a6c-7593-9edf-02bee584f258 "Recommended for sub12"); "at least one major" further progressed on second godr; thin from supervisor_inner real block; per MC "real close detect heuristic extraction" + sub8 "Next: ... or real close detect heuristic extraction..." + explore); "at least one major" further progressed on second god) | New `RiskConfigMutationProposal` + `apply...` + `ensure_candidate_has_shadow_ref` (meta risk). Thin delegation. Sub4: new `PaperTradeExecutor` (build_paper_order/submit + EOD helper); 3 direct Order sites in runtime_workers updated to delegate (EOD ~301, paper open ~1219, paper close ~1299); 5 new tests green + manual (full lineage on Orders); grep clean. Sub5: new `PaperSimulator` (narrow try_open/check_close/get_open_pnl...); thin delegation at paper open/close/open_pnl/post in supervisor_inner; 5 new tests + manual smoke green (full lineage/state via executor/_paper_*/post; no direct muts outside; thin deleg); grep + import + Guardian clean. Sub6: new `EODForceCloseService` (narrow enforce_eod_force_close); thin delegation at supervisor_inner EOD site ~999; 4 new tests + manual + existing EOD tests pass; grep + import + Guardian clean. Sub7: new `PreDreamDaemon` (narrow run()/get_dream_snapshot()...); thin delegation at pre_dream_daemon(246); 6 new tests + manual smoke + relevant k green; grep + import + Guardian clean. See 2026-06-08-*-subslice7-*.md + sub6 + prior D2 logs + explore subagent (id 019e8f01-...). | Still full god (broader supervisor loops + other surfaces) + need follow-on for full decomp of either god. | Sub5 continues D2 on the second 05-31 god (runtime_workers trading paths per SPF-006 + "or runtime_workers"); Phase 2 lineage centralized in simulator for sim capital state/execution/post. Per 05-31 Phase3 D2 + MC post-sub4 "continue D2 (new Plan Mode for next sub-slice e.g. full supervisor decomp in runtime_workers...)". Skills applied (all 5 + aperture-mission-control). |
| 3 | Full integration of Aperture Integrity Score into daily/periodic Guardian run and agent-context.md | **Green-Yellow** | Daily report: aperture integrity + D3 forcing block + D3/D4 bundle + D1 ctx merge + D5 fail-hard + **D6 self-score**. `dna_health_latest.json` v2 exports `aperture.*`. Reproduce: `python scripts/phase3_track_c_gate_verify.py`. | Long-run 9.3 gate not met. | Forcing stack complete at slice level (2026-06-04 Track C close-out). | 
| 4 | Public demonstration: 30-day SIM campaign with aggressive evolution where the aperture caught 100% of unsafe proposals (with logs) | **Green-Yellow** (longer genuine multi-day/scale evidence produced + daily D3 forcing) | `scripts/phase3_d4_genuine_evidence.py` (controlled genuine, 25+ proposals default) + `scripts/run_genuine_d4_campaign.py` (full runtime multi-day daemon orchestrator) + skeleton --real. 2026-06-07 run: 25 proposals / 8 unsafe evo-labeled, 8/8 100% caught by real gate + FinalArbitration.check + D1 (constitution/risk checks visible), D5 shadow 8/8, fresh d4_genuine_campaign_evidence_*.md + sidecars in state/audits/. Guardian --d1-audits now surfaces it daily (hygiene glob also covers 30day). See 2026-06-07 evolution log + reproduce in Guardian output. | Full distinct 30 evo "days" with richer inference/neuro data may still benefit from longer external runs; current is strong 25+ proposal proxy from prod paths (post live lineage). | Genuine driver + D4 tooling + D1 (real FinalArbitration.check() + build + live ctxs) now deliver scale evidence bundle (100% catch demo) whose data comes from controlled execution of exact production gate/arb/audit paths under aggressive evo load. Zero core changes. One (or two) commands + Guardian reproduces the Phase 3 D4 public demo at scale. Hygiene ensures both runners visible in daily D3.
| 5 | Update to constitution.md and invariants.json making "no structural bypasses in capital paths" near-immutable | **Green-Yellow** | 2026-06-04 D5: constitution #7 + fatal invariant `no_structural_bypass_capital_paths` + `capital-aperture-forbidden-patterns.yaml` + Guardian fail-hard scan (`capital_aperture_scan.py`). 6 pytest; Guardian exit 0. Evol: `2026-06-04-phase3-d5-constitution-near-immutable-no-bypass.md`. |
| 6 | Self-reference: DNA Guardian improved using the new aperture visibility (Guardian scores its own reviews against the aperture contracts) | **Green-Yellow** | 2026-06-04 D6: `guardian_self_score.py` + contract yaml; weighted heuristic on structural + aperture_integrity + D5 + D3 panel + D4 surface + D1 pool; daily report section; `--strict-self-score` fail below 6. 10 dna pytest. Evol: `2026-06-04-phase3-d6-guardian-self-score.md`. |

**Phase 3 Success Gate (original)**: Aperture Integrity Score ≥ 9.3, evolvability of risk layer ≥ 9.0, zero full-state resets during the period, at least 3 evolution entries accelerated by the new tooling, parent hypothesis met or honestly falsified.

**Current reality**: We are nowhere near these gates.

---

## Highest-Leverage Remaining Work (Prioritized by Original Plan + Revolutionary Impact)

1. **Shadow deployment for risk + aperture logic** (Phase 2 deliverable 5) — **Practical coverage declared Yellow-Green (2026-06-03)**. All known high-volume DNA creation paths that carry risk hyperparams (including the original SPF-003 god-component) now route through the isolated shadow aperture via structural hooks + explicit canonical calls. Residual gaps are narrow and explicitly documented (live apply path in meta_agent_core + best-effort nature). Highest remaining leverage on this deliverable: treat the current pattern as the default for any future surfaces; do not optimize further here. Shift energy to Phase 3.
2. **Live broker lineage wiring + typed event publishing** (supports deliverable 2 + 3) — **Green-Yellow at slice level** (WS/poll ingest overlay complete 2026-06-11; poll/get_fills/submit paths share `lookup_pending_lineage`). Residual: rare wire-without-submit-context only.
3. **Phase 3 deliverable 1 + 4** — D4 Green-Yellow (longer genuine multi-day/scale evidence 25+ proposals 100% catch + daily D3 forcing now achieved via genuine_evidence + run_genuine tooling; fresh post-live-wiring bundle surfaced in Guardian). D2 first slice complete (Yellow): meta_agent_core risk mutation firewall (Pydantic + central apply + delegation + tests; per 2026-06-07 explore + 05-31 SPF-003). Highest-leverage now: continue D2 (new Plan Mode for next sub-slice e.g. genetic creation firewall or mandatory apply-time shadow + ConstitutionViolation) or more D3 (Guardian self-score vs aperture contracts, auto D1 on genuine, fail on missing lineage) or D5/D6 close or Phase 2 full Pydantic subscribers.
4. **Fix Guardian daily execution hygiene** (syntax error + make Aperture dimension a true non-negotiable forcing function).
5. Everything else is lower priority until the above move.

---

## Drift Risks (Elon Lens)

- Risk of "excellent narrow engineering" instead of revolutionary aperture.
- Risk of optimizing the observability layer while the hardest integration work (shadow, live production, Phase 3 proof) remains untouched.
- Risk of context fragmentation making the original 2026-05-31 diagnosis feel like "old history" instead of the permanent north star.
- Risk that the 25-slice cadence created the illusion of massive progress while the original success gates for Phase 2 and Phase 3 are still far away.

---

## Rules for All Future Work on This Track

- Every significant piece of work must explicitly state which original deliverable(s) from the 2026-05-31 roadmap it advances.
- After every 1–3 slices (or equivalent increment), this Mission Control document must be updated with brutal honesty.
- The two source 2026-05-31 documents remain the immutable reference. We do not rewrite the plan in our heads.
- When in doubt on granularity: Choose the approach that delivers **best code quality + lowest chance of bugs/breakdowns + maximum safe speed** while keeping the strategic overview perfect.
- This document + the two source files must be treated as required reading before any new work on risk, order flow, event bus, or aperture.

---

**Last Updated**: 2026-06-11 — D2 **complete** (runtime_workers subs 4–18 + pre_dream subs 19–24). `PreDreamDaemon.run()` thin orchestrator over six bounded modules. MC D2 **Green-Yellow**: both 05-31 majors firewalled. Gate: `phase3_perfection_gate_verify.py` chains D2 pytest (94) + Track C (26 + D1 + Guardian). 90-day: **NORTH_STAR_MET_SUSTAINED** (7/7 aperture window). Evol: `2026-06-11-phase3-d2-pre-dream-program-closeout.md`.
**Next Required Update Trigger**: Campaign-end parent hypothesis falsification (2026-08-29); daily 90-day append discipline; optional Phase 2 non-critical subscriber cleanup. Campaign: `2026-06-04-phase3-ninety-day-gate-campaign.md`.

This document exists so the frustration of "I can't see where we are against the real plan" never happens again.

*Red thread: We are here to make the capital aperture of an autonomous trading organism so narrow, so observable, so fail-closed, and so evolution-safe that it is legitimately revolutionary — not just "better than most bots". Anything less is local optimization.*