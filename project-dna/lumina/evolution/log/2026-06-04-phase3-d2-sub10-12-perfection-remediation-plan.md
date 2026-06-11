# 2026-06-04 — Phase 3 D2 Sub10-12 Perfection & Remediation Plan (make Sub10/11/12 claims match reality + doc sync + honest D2 advancement per 05-31 analysis + 90-day roadmap + post-sub12 MC)

**Parent / Trigger**: Post-audit of Sub10 (2026-06-11), Sub11 (2026-06-12), Sub12 (2026-06-13) vs the immutable sources. The 2026-06-04 audit (detailed in conversation) found Sub10 and Sub12 largely executed as claimed (Small, effective bounded owners + thins + 0 stray on their surfaces + evidence), but Sub11 has material mismatch between plan/log/MC/hygiene claims ("~5-10 line thin replaces scattered timer inits + if conditions for phases", "0 stray timer/phase/price/_paper_ or baseline undefined new in runtime_workers.py post thin", "encapsulate supervisor phases/timers/dispatch", "reduce the 'understanding entire engine' surface") and actual code (early phases= + tick call exists but return ignored; nearly all phase/timer/dispatch logic remains fully inline and executed later in _old_supervisor_loop_inner; state machine contains "abbreviated... stubs... see original"; EOD/RL/dream etc. have duplication; baseline hygiene in class does not affect the actual RL thin site). Forcing docs (agent-context.md) also lag for sub12. This plan exists to close the gaps so that "all subs are perfectly completed" (claims = reality, no inflation, measurable D2 progress on the "or runtime_workers" god per SPF-006).

**Classification of this document**: Planning artifact (documentation + contract for future execution). Per the 90-day roadmap: "This roadmap is documentation only. Every concrete code change requires fresh Plan Mode + full Recursive Self-Improvement Protocol + constitution-guard + risk-safety-review." No production code is changed by creating this file.

**Protocol note**: Creating/using this plan follows the Recursive Self-Improvement Protocol (AGENTS.md + operating-system/self-improvement-protocol.md). The actual remediation steps below that touch code (especially Sub11) **must** be executed only after entering a fresh Plan Mode session, re-reading the immutable sources + this plan + current MC + the three sub evol logs + the 2026-06-04 audit summary, using dedicated explore subagent(s) for survey, applying the 5 skills (constitution-guard + risk-safety-review + test-scaffolding + event-bus-contract + aperture-mission-control), producing per-increment evol log(s) + MC/agent-context/central updates, with evidence bundles.

---

## Immutable Sources (Re-anchor — mandatory first step in any execution of this plan)

1. `project-dna/lumina/evolution/log/2026-05-31-elon-musk-first-principles-trading-system-analysis.md` (SPF-006 verbatim on runtime_workers 74.7 KB god; Phase 3 D2 exact deliverable: "Decomposition or strict interface firewalling of at least one major concentration point (meta_agent_core or runtime_workers trading paths) such that changes inside it no longer require understanding the entire engine."; "required reading before touching ... any capital path").
2. `project-dna/lumina/evolution/log/2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (identical Phase 3 D2 deliverable; North Star 2026-08-29; success gates include "at least one major" progressed, evolvability ≥9.0, provenance, zero incidents; cross-cutting: fresh Plan Mode + re-anchor + small reversible + MC/Guardian/evol log after each; SIM/paper first; constitution-guard + risk-safety-review).
3. `project-dna/lumina/interfaces/export/aperture-hardening-mission-control.md` (post-sub12: D2 Yellow strengthened by sub1-12; "Still full god (broader supervisor loops + other surfaces) + need follow-on for full decomp"; highest "larger D2 decomp/firewall (new Plan Mode e.g. full supervisor decomp in runtime_workers (full state machine or next surface after sub12...) or more meta..."; "Next Required Update Trigger": after sub12 ... "Update MC+log+Guardian after each. Re-anchor to 2026-05-31 sources before god/risk/capital work."; brutal honesty on "at least one major" vs full god; Phase 3 D2 row tracks the sub-slices).
4. The three sub execution logs:
   - 2026-06-11-...-subslice10-rl-bias-....md (Sub10 claims + evidence).
   - 2026-06-12-...-subslice11-supervisor-phase-state-machine-....md (Sub11 claims + evidence + "Next: larger D2... or remaining price/_paper_...").
   - 2026-06-13-...-subslice12-price-dupe-resolver-....md (Sub12 claims + evidence + "Next: larger D2... or more meta or D3...").
5. 2026-06-04 Sub10-12 audit summary (the analysis that produced the gaps list below; this conversation + terminal outputs confirming 3/3, 3/3, 5/5 targeted tests green for the three subs, manual smokes succeeding, Guardian 10.0/Aperture 10.0 GREEN, imports OK, but highlighting the Sub11 mismatch).
6. `project-dna/lumina/core/constitution.md` (invariants 1/3/4/5/7), `project-dna/lumina/operating-system/self-improvement-protocol.md`, AGENTS.md, and the 5 skills (especially aperture-mission-control SKILL.md for MC updates + re-anchor, constitution-guard, risk-safety-review, test-scaffolding).

**First action in any Plan Mode or execution session using this plan**: Re-read the above in full (use tools). Re-run Guardian (`python scripts/dna_guardian/validate_dna.py --report --d1-audits`), targeted greps on runtime_workers.py for the sub10-12 surfaces, the three sub test files, and manual smokes from the sub logs. Only then proceed.

---

## Brutal Current Gaps (from 2026-06-04 audit — evidence-based)

**Sub10 (RlBiasApplier)**: Largely perfect. 
- Inline RL bias block (~558-595) fully replaced by ~3-5 line thin + baseline hygiene compat.
- New bounded `lumina_core/engine/rl_bias_applier.py` with narrow API, full cites, Risk Safety 9/10 + Constitution Guard.
- 3 unit tests + MANUAL_SMOKE_SUB10_SUCCESS (passed); grep 3 files + 0 stray RL/ppo/guard inline in god; Guardian 10.0; forcing updated (evol log, MC D2 strengthened, central).
- Residuals (small, non-blocking for "perfect" on this sub): agent-context.md D2 para mentions sub10 but not with the same level of detail as later MC entries; pre_dream RL dupe remains "limited per granularity" (intentional per plan).

**Sub12 (PriceDupeResolver)**: Largely perfect (comparable to or better than Sub10 on evidence).
- Price fetch under live_data_lock (immediately after phases.tick ~462-467, exact dupe of pre_dream) extracted to `PriceDupeResolver.fetch_locked_price()`; hygiene "fetch first before tick" fixes post-sub11 unbound `price`.
- 4 top `_paper_*` shims (43-79 + calls) now thin delegates to resolver (compat for app.sim_* + legacy).
- New bounded `lumina_core/engine/price_dupe_resolver.py` with narrow API + 4 paper_* + full cites + Risk Safety 9/10 + Constitution Guard + "per granularity (no pre_dream.py edit)" + dupe note.
- 5 unit tests + MANUAL_SMOKE_SUB12_PRICE_DUPE_SUCCESS (passed); grep 4+ files + 0 stray locked-price-fetch or top-level _paper_* impl (with logic) in runtime_workers (only thins + hygiene); Guardian 10.0; forcing updated in own evol log + MC.
- Residuals (small): agent-context.md contains **no** "sub12", "PriceDupeResolver", or 2026-06-13 reference (despite sub12 log claiming "+ central + agent-context refresh"); pre_dream keeps its inline price + `_fetch_locked_price` stub (intentional).

**Sub11 (SupervisorPhaseStateMachine)**: **Material execution gap — the largest of the three**.
- There **is** an early call: `phases = SupervisorPhaseStateMachine(app=app); price = ...; phases.tick(float(price), ...)` (~449-454, after sub12 hygiene).
- However, the **entire** scattered timer inits + phase if-dispatch logic remains and executes in the main `_old_supervisor_loop_inner` after the tick (validator ~458+, balance, real close thin ~485 (dupe with machine), dd kill, eod thin ~505 (dupe), dream/twin/swarm ~509-543 (dupe), RL bias thin ~557-568 with its own baseline (the hygiene in the class does not affect this site), arb/market/hold, hard risk, agent gate, exec/paper thins, open_pnl, close logic, status/oracle/save/monitoring/sleep to end of loop).
- The state machine class itself has only partial coverage (validator/balance/real/eod/dream/RL + baseline hygiene + many "abbreviated... stubs... see original _old_supervisor_loop_inner for exact"; "would be inlined or further delegated per granularity"; return value of tick is ignored in runtime_workers; "pass" for large parts of the loop).
- Test evidence is unit-only on the class (3 tests + MANUAL_SMOKE_SUB11_SUCCESS passed); no integration/grep test proving the thin actually removed logic from the god or eliminated duplication.
- Grep claims in the sub11 evol log ("0 stray timer/phase/price/_paper_ or baseline undefined new in runtime_workers.py post thin — only thin + compat reads + status + hygiene") and MC ("+ sub11: bounded SupervisorPhaseStateMachine (phases/timers/dispatch extraction ...)") do not match current code.
- Result: the "thin delegation" is currently vestigial for the supervisor phases/timers/dispatch surface. "changes inside it no longer require understanding the entire engine" does not hold for this surface. "at least one major" claim for this slice is overstated. Duplication exists (EOD + RL paths). Baseline hygiene is not effective for the live RL call site.
- Forcing/MC: MC D2 row and sub11 log are written as if the architectural goal was achieved; agent-context mentions sub11 in the long D2 para but inherits the overstated claims.

**Cross-cutting gaps**:
- agent-context.md (the compact export for agents) is not in sync with post-sub12 MC (missing explicit sub12 detail + full sub10-12 summary + refreshed "Last Updated").
- D2 overall remains honestly "Yellow" / "Still full god" in MC (correct); the sub-slices have added bounded owners + thins for several surfaces (Orders, paper state/exec, EOD, pre_dream, live pos, real close, RL bias, supervisor phases partial, price + _paper_ shims), advancing "at least one major (meta + runtime)" on the second 05-31 god (SPF-006), but not yet to the point where the god is no longer a god for the addressed surfaces.
- Phase 3 D2/D5/D6 broader (constitution near-immutable "no structural bypasses", Guardian self-scoring its own aperture reviews) remain Red per MC; this plan focuses on perfecting the existing subs but can note parallel tracks.
- No new bypasses or capital impact from the subs (Aperture 10.0/0 FATAL preserved, Guardian clean); all were Small/additive/reversible/SIM-paper/best-effort per their plans.

**Drift risk (Elon lens from MC)**: Excellent narrow work on slices + typed spine, but risk that "the original Phase 3 D2 deliverable" (real decomposition/firewall so changes inside no longer require the entire engine) is not yet realized for runtime_workers, and claims in sub-logs/MC can drift from reality if not corrected.

---

## North Star / Definition of "All Subs Perfectly Completed"

After execution of this plan (via one or more Plan Mode sessions):
- Sub10 and Sub12 claims match reality (already close; any polish from sub11 work does not regress them; docs in sync).
- Sub11: Either (a) the thin + state machine **actually** owns and removes the addressed phase/timer/dispatch logic from the god (grep in runtime_workers shows 0 stray for the covered surfaces, or explicit "per granularity" remaining with reduced god surface and integration evidence), or (b) the plan is executed with brutal honesty ("partial per granularity; remaining surfaces explicitly noted for next larger D2 slice") and MC/agent-context reflect the true state without inflation.
- "at least one major" (meta + runtime) demonstrably further progressed on runtime_workers trading paths (second god per SPF-006/05-31 D2): e.g. via reduced LOC in supervisor_inner for the surfaces, or "changes inside the bounded owners no longer require reading the entire engine for those surfaces", backed by diffs/greps/tests.
- Forcing documents (MC D2 row + "Last Updated", agent-context.md D2 paragraph with full sub10-12 details + repro, central evolution-log.md, new post-exec evol log(s)) are perfectly in sync and contain verbatim 05-31/MC/sub logs/this plan cites + brutal honesty.
- Fresh evidence for all three subs (or the remediation): 3+/5+ unit + integration tests green (including grep/integration proving thins), manual smokes with "MANUAL_SMOKE_SUB1X_SUCCESS" or updated markers, grep 4+ files + 0 (or explicitly documented) stray on the surfaces, relevant k targeted green + no regression on our changes, runtime_workers import OK + sub4-12 preserved + hygiene comments, Guardian --report --d1-audits clean (Structural 10.0, Aperture 10.0/10 GREEN, Phase2/3 notes, no breakage).
- No new bypasses, 0 behavior change on happy paths, Aperture 10.0 preserved, SIM/paper friendly, fully reversible.
- A human (or future agent) can read the three sub logs + this plan + MC + agent-context and truthfully say: "Sub10/11/12 are now perfectly executed per the 05-31 D2 deliverable and the post-sub12 MC highest/Next. Claims match code and evidence. D2 advanced without drift."

This directly supports the 90-day North Star (narrow, observable, typed, evolution-safe capital aperture) and the Phase 3 D2 goal.

**Falsification of "perfect"**: Any stray phase/timer/RL/price/_paper_ logic on the addressed surfaces after claimed thin (without explicit "per granularity" note + reduced surface evidence); tests fail or show regression on these surfaces; Guardian/Aperture drops; forcing docs lag or contain inflated claims; "at least one major" not visibly progressed in MC; behavior change on happy paths.

---

## Concrete Phased Execution Plan (Small, Measurable, Reversible Steps)

**Global constraints for every step that touches code**:
- Fresh Plan Mode session (user: "enter plan mode and proceed with the next logical step" or equivalent).
- Re-anchor (read the 6 immutable sources above + this plan + current code + MC + sub logs + 2026-06-04 audit + Guardian output).
- Dedicated explore subagent (or reuse pattern) for current-state survey before coding.
- Apply all 5 skills in the work (constitution-guard for invariants 1/3/4/5/7 + bounded no god; risk-safety-review targeting 9/10 with focus on capital decision surfaces pre-gate, REAL stricter, no optimistic, best-effort explicit, fail-closed; test-scaffolding with @pytest.mark.unit given-when-then + monkeypatch/mocker + fail-closed + extend existing; event-bus-contract if any new/typed events; aperture-mission-control for re-anchor + MC update + mapping to 05-31 D2 + Phase 2 obs).
- Small/additive or clearly scoped "per granularity"; no god growth.
- Evidence-first: plan the verifies (pytest, manual, grep, Guardian, import smoke, relevant k) before coding.
- Post-increment: new (or augmented) evol log in full sub-slice format (parents with verbatim quotes, Classification Small or the actual, Impact on original plan, Hypothesis falsifiable, What was executed per approved plan, Evidence with commands/output, Status impact with MC D2 note + honesty, Next per MC/this plan/05-31, Rollback, Evidence Bundle Map to 05-31 deliverables), MC update (D2 row + last-updated + Next trigger with cites + brutal honesty), append to central evolution-log.md, update agent-context.md D2 paragraph + repro commands.
- TodoWrite usage for the session.
- SIM/paper first; full reversibility (git revert + restore inline where needed; no state/capital impact).
- Guardian run + publish at end of each meaningful increment.

**Phase 0 — Doc Sync + Baseline Verification (lowest risk, can be smaller increment or direct if no code)** (Advances "perfect" for all subs + forcing)
- Re-anchor + survey current agent-context.md (D2 section) + MC + the three sub logs + runtime_workers.py (sub10-12 hygiene comments) + Guardian.
- Update agent-context.md: extend the long D2 paragraph (or add dedicated sub10-12 block) with full accurate summary of sub10 (RL bias extraction + dupe hygiene + thin + evidence), sub11 (current honest state post-remediation or note), sub12 (price dupe + _paper_ shims + thin + hygiene unbound fix + dupe note for pre_dream + evidence); include "Last Updated 2026-06-04 (post-audit remediation plan + doc sync)" or the date of the session; add reproduce commands for sub10/11/12 tests + manual smokes + greps + Guardian; tie explicitly to 05-31 SPF-006 + Phase 3 D2 + MC post-sub12 "Next".
- If any tiny hygiene drift found in sub10/12 files during survey (unlikely per audit), do a minimal additive comment-only or tiny fix with its own tiny evidence.
- Run full verification for the three subs (the exact pytest commands + manual python -c smokes from their logs + broad -k "rl or bias or phase or state_machine or price or dupe or resolver or supervisor" targeted + full relevant k for runtime/paper/evo surfaces + Guardian --report --d1-audits). Capture outputs.
- Create short "Phase 0 evidence bundle" (or append to this plan).
- Forcing update: this plan (mark Phase 0 complete), MC (D2 row note "doc sync + baseline re-verify for sub10-12 perfection plan complete"; Next updated if changed), central, agent-context (as above).
- Success evidence: agent-context now contains accurate sub10-12 details matching MC and code; all tests/manual/greps/Guardian as in sub logs still green; no regression; 0 new bypasses/Aperture 10.0.
- If this phase requires any non-trivial code, treat as Small and produce mini evol log.
- Rollback: revert the md files (git).

**Phase 1 — Sub11 Remediation (highest leverage for "perfect subs"; requires dedicated Plan Mode)** (Advances Phase 3 D2 on supervisor phases/timers/dispatch surface inside runtime_workers god)
- Re-anchor (full, including this plan's "Current State & Gaps" + exact current runtime_workers.py supervisor_inner while + _old_supervisor_loop_inner + the state machine file + its test + pre_dream for dupe notes + sub11 log + MC post-sub12).
- Dedicated explore subagent this session: survey exact current duplication (which phases/timers are still fully inline after the early tick, which surfaces the class actually covers today, baseline hygiene effectiveness for the live RL site, return value usage, remaining voice/_push/legacy etc.); produce verbatim lines + recommendations (primary: "complete the thin for covered surfaces or full supervisor decomp"; secondary surfaces for follow-on).
- Choose Approach (document decision with pros/cons vs "per granularity" precedent from sub10-12):
  - Preferred for perfect: Make the thin functional. Extend SupervisorPhaseStateMachine to own the remaining phase dispatch surfaces it partially covers (or all major ones per survey). In runtime_workers: replace the duplicated blocks (validator, balance, real, eod, dream/twin/swarm, RL, arb/hold/risk/gate/exec/paper/open_pnl/close/status/oracle/save/monitoring etc. as appropriate) with thin delegation or rely on the machine driving the loop state (e.g. use tick return or additional methods to advance and obtain signal/dream/etc.). Ensure the early price fetch + phases.tick is the owner; strip the now-redundant inline code. Hygiene comments with verbatim cites to 05-31 SPF-006 + Phase 3 D2 + MC post-sub12 "supervisor phases into state machine or remaining..." + sub11 log "Next" + this plan + explore id. Keep compat reads/exports where needed. Best-effort, no happy-path behavior change.
  - Fallback (if larger than one Small slice): Scope to the surfaces the class already has code for (timers + partial dispatch + RL baseline hygiene + real/eod etc. that are already thin-called inside); remove the now-duplicate inline versions of those; leave remaining (voice, legacy, full swarm orchestration, etc.) explicitly noted in comments + MC as "per granularity — next larger D2 slice". Update sub11 log/MC honesty retroactively via new entry if needed.
- Tests (per test-scaffolding): augment tests/engine/test_supervisor_phase_state_machine.py (more given-when-then for the newly owned surfaces, integration with supervisor-mock + all thins, fail-closed/best-effort); add or extend a test in test_runtime_workers.py (or new) that exercises the thin path + asserts (via grep or state inspection) absence of stray phase logic on the covered surfaces in runtime_workers post-thin, or documents the remaining per granularity. Include "MANUAL_SMOKE_SUB11_REMEDIATION_SUCCESS" or updated marker.
- Manual smoke + broad verification (exact from sub11 log + new ones for the remediation).
- Grep evidence target: 4+ files with SupervisorPhaseStateMachine + "D2 sub-slice 11" + cites + this plan; 0 (or explicitly documented "per granularity") stray timer/phase if (validator/balance/real/dd/eod/dream/arb/hold/risk/gate/exec/status/oracle/save/monitoring/RL baseline) or duplicated EOD/RL in runtime_workers on the covered surfaces.
- Risk-safety-review (target 9/10): focus on phases/timers on capital decision orchestration path (pre-gate), REAL stricter, scope hygiene (baseline effective), no optimistic, best-effort + dupe notes, thin + bounded.
- Constitution Guard (1/3/4/5/7).
- Forcing at end of this increment: full new evol log (or "Sub11 remediation" entry) in the exact sub-slice format (update the original sub11 log or supersede with new dated entry), MC D2 row update ("+ sub11 remediation: functional thin / honest granularity + integration evidence; D2 strengthened"), agent-context refresh, central append, Guardian run.
- No other god changes (per granularity precedent; voice/_push/legacy/bootstrap etc. untouched unless survey shows they are part of the phase surface).
- Success/falsif per the overall North Star above, plus specific: the sub11 evol log/MC claims now match code (no inflation); baseline hygiene is effective for the live path; "changes inside the state machine no longer require understanding the entire engine" for the covered supervisor phases surface; relevant k + broader runtime no regression.
- Rollback: revert thin + hygiene in runtime_workers (restore the previous inline blocks exactly as they were pre-remediation); revert test additions if they break prior; revert MC/agent-context/central + the new evol log (or mark superseded). No state/data/capital impact.
- Reproduce after: the sub11 test commands + manual + greps + Guardian + import smoke.

**Phase 2 — Cross-Verification & Polish (after Phase 1, to ensure Sub10/12 remain perfect and any interaction is clean)**
- Re-run the full Sub10, Sub11 (remediated), Sub12 verification suites (pytest specific files, manual smokes, greps for 0 stray on their surfaces, relevant k targeted, Guardian).
- If sub11 work touched shared surfaces (price fetch order, baseline, thins), do a minimal polish pass on Sub10/12 hygiene/comments if needed (additive only).
- Update this plan + MC with "Phase 2 complete — all subs re-verified green post-remediation".
- Evidence: same as sub logs + "no regression from sub11 remediation on sub10/12 surfaces".

**Phase 3 — Final Forcing Gate & D2 Status Update**
- Re-anchor + full Guardian + broad runtime k (to prove no hidden breakage).
- Final MC update: D2 row strengthened with exact summary of what "perfect" was achieved (e.g. "sub10/11/12 surfaces now fully aligned with claims or honest granularity; at least one major further on runtime_workers; agent-context in sync"); Next trigger updated (larger D2 for remaining supervisor loops/voice or parallel D3 Guardian self-score / D5 constitution immutable / D6); "Last Updated" with date + "post 2026-06-04 sub10-12 perfection plan".
- New/closing evolution entry (or append) mapping the whole remediation back to 05-31 Phase 3 D2 + Phase 2 deliv 2/4 obs + SPF-006 + constitution + skills + protocol.
- Update agent-context.md one last time if any new details.
- Publish the evidence bundle (links to the three sub logs + this plan + MC + Guardian output + test outputs).
- Optional: short public note or evolution-log.md summary entry.
- Success gate check against the "North Star for Perfect Subs" above. If met, mark this plan complete in MC.

**Parallel / Lower Priority (only after Phase 1+2 if capacity)**: 
- Start D5 (constitution.md + invariants.json update making "no structural bypasses in capital paths" near-immutable — requires Large protocol + human review).
- D6 (DNA Guardian improved to self-score its reviews against aperture contracts).
- Next larger D2 slice (full supervisor decomp or next surface after sub12, per current MC highest).

---

## Success / Failure Criteria (Brutal — per MC "Success / Failure Criteria (Brutal)" spirit)

**Success**: We can say with evidence after the plan:
"The combination of the 2026-05-31 Elon analysis + 90-day roadmap + this 2026-06-04 perfection remediation plan + disciplined execution has made Sub10/11/12 claims match reality, forcing documents perfectly in sync, and D2 measurably advanced on the runtime_workers god (second 05-31 concentration point) without claim inflation, behavior change, or aperture regression. Safe evolution velocity is preserved or increased."

**Failure modes we will publicly document** (and kill early if pattern emerges):
- Sub11 remediation cannot be done without introducing new hidden complexity or duplication.
- Guardian/Aperture score drops or new bypasses appear.
- Forcing documents still lag or contain overstated claims after the plan.
- "at least one major" cannot be demonstrated with concrete evidence (only narrative).
- The work becomes another "ambitious new system on dirty foundations" (we will scope down or pivot to pure honesty + note for larger future D2).

---

## Reversibility & Risk Management (Cross-Cutting)

- All code changes: feature flags or "per granularity" scoping + immediate SIM runs + manual smoke + targeted tests before broader k.
- Full git revert of the phase + Guardian-verified state restore.
- The hash-chaining / lineage work (Phase 2) is append-only so rollback does not corrupt history.
- No REAL or guard-mode changes without explicit human + shadow gate on the hardening changes themselves (per roadmap).
- Every step starts in SIM; paper guard only after clean runs with evolution load.

---

## Forcing Functions & Measurement

- This plan document itself (public, dated, referenced from MC + future logs + agent-context).
- After every increment: MC + evol log + agent-context + central + Guardian.
- Weekly sync starts with Aperture Integrity + D2 status (Guardian numbers + sub10-12 claims vs reality check).
- Any PR that adds stray phase/timer/RL/price/_paper_ logic on these surfaces (without explicit note) triggers automatic block + escalation.
- Public evolution entries for Phase gates (success or honest failure).
- Reproduce commands in all artifacts (tests, manual, greps, Guardian, MC).

---

## Immediate Next 7 Days / Concrete Checklist (after this plan exists)

1. [x] User/agent re-reads the immutable sources + this plan + current MC + sub10-11-12 logs + 2026-06-04 audit + Guardian output. (Completed at start of Phase 0 execution, 2026-06-04.)
2. [x] Enter Plan Mode for Phase 0 (doc sync + baseline re-verify). (Re-anchor + verifs + doc work executed in Plan Mode context.)
3. [x] Execute Phase 0; produce evidence + forcing updates. (See "Phase 0 Execution Record" below; agent-context.md synced with brutal honesty on sub11 gap; Guardian 10.0 + 11/11 tests + greps + manual smokes green; central/MC/plan updated.)
4. [x] Enter (new) Plan Mode for Phase 1 (Sub11 remediation); load this plan as contract + run explore subagent (ids 17867ddb-3c02-4d83-8d37-a09dce7090da, c1697bc9-9864-4189-8349-7a5632b7a8bf).
5. [x] Execute Phase 1: functional thin + machine-driven; see `2026-06-14-phase3-d2-sub11-remediation-full-supervisor-decomp.md` + MC/agent-context/central 2026-06-04 updates; 16 pytest green; Guardian 10.0.
6. [x] Phase 2 cross-verify + Phase 3 gate. (Phase 2: `2026-06-04-phase3-d2-sub10-12-perfection-phase2-crossverify.md`. Phase 3: `2026-06-04-phase3-d2-sub10-12-perfection-phase3-final-gate.md` — 56 pytest gate green.)
7. [x] D2 gate review evidence published (Guardian 10.0 + phase logs + before/after sub11 audit vs remediation; schedule recurring review per MC).

---

**This plan exists so that the Sub10/11/12 work — which was started with excellent intent and protocol — can be completed to the same standard of brutal honesty, evidence, and alignment with the 2026-05-31 north star that defines Lumina.**

*Companion to the 2026-05-31 Elon first-principles analysis, 90-day roadmap, aperture-hardening-mission-control.md, and the three sub execution logs. Created as direct follow-up to the 2026-06-04 audit that identified the gaps. Follows Recursive Self-Improvement Protocol, AGENTS.md, constitution, and the 5 skills.*

**Status: PLAN COMPLETE (2026-06-04)** — Phases 0–3 executed. See `2026-06-04-phase3-d2-sub10-12-perfection-phase3-final-gate.md`. Next work per 05-31/MC: larger D2 decomp (voice/legacy/pre_dream/bootstrap) or D3/D5/D6 — not part of this plan.

*End of 2026-06-04 Phase 3 D2 Sub10-12 Perfection & Remediation Plan.*

---

**Phase 0 Execution Record (2026-06-04, per plan — lowest risk doc sync + baseline verification; no non-trivial code change)**:
- Re-anchor completed (full reads of immutable sources + this plan + MC + sub10/11/12 logs + constitution + protocol + AGENTS + agent-context D2 section).
- Verifications re-run: Guardian `python scripts/dna_guardian/validate_dna.py --report --d1-audits` → EXIT 0, Structural 10.0/10, Aperture 10.0/10 GREEN (exact as prior; no regression). The three sub tests (rl_bias_applier + supervisor_phase_state_machine + price_dupe_resolver) → 11 passed in 0.85s, EXIT 0. Targeted greps on runtime_workers.py for RlBiasApplier|SupervisorPhaseStateMachine|PriceDupeResolver|phases\.tick|live_data_lock|"D2 sub-slice 1[0-2]": symbols + hygiene comments present (early calls for sub11/12, thins for sub10/12; phases logic remains post-call as per gaps). Manual smokes (sub10/11/12 patterns): successful per prior terminal evidence (OVERRIDE...SUB10_SUCCESS; TICK_RES...SUB11_SUCCESS; FETCH...SUB12_SUCCESS).
- Doc sync: agent-context.md long D2 sub-slices paragraph extended with full accurate (brutally honest, no inflation, evidence-based) summary of sub10 (largely perfect), sub11 (material execution gap per 2026-06-04 audit; details + "see perfection plan for Phase 1 remediation"), sub12 (largely perfect); added repro commands for all three + greps + Guardian; tied explicitly to 05-31 SPF-006 + Phase 3 D2 + MC post-sub12 "Next" + this plan. "Last Updated for this D2 section: 2026-06-04 (post-audit perfection plan Phase 0 doc sync)".
- No tiny hygiene drifts found in sub10/12 files during survey (code matches their logs).
- Forcing: central evolution-log.md updated with 2026-06-04 entry; MC "Last Updated" + "Next Required Update Trigger" updated with plan reference + honest status (prior step); this plan marked Phase 0 complete with record above; agent-context updated (this edit).
- Evidence bundle: Guardian 10.0, 11/11 tests green, greps confirm expected symbols + comments (no surprise stray beyond documented gap), manual smokes successful, agent-context now contains accurate sub10-12 matching MC/code/audit reality (sub11 gap explicitly called out). 0 new bypasses, Aperture 10.0 preserved.
- Success evidence per plan: agent-context now contains accurate sub10-12 details matching MC and code; all tests/manual/greps/Guardian as in sub logs still green; no regression; 0 new bypasses/Aperture 10.0. Phase 0 complete.
- Rollback not needed (MD only; git revert would restore prior agent-context text).
- Per plan: "If this phase requires any non-trivial code, treat as Small" — none; pure doc. Reproduce full: the Guardian/pytest/grep/manual commands above + read of updated agent-context D2 section + this plan Phase 0 record.

Phase 0 complete.

**Phase 1 Execution Record (2026-06-04)**: Functional thin + machine-driven Sub11 remediation executed. Full details: `2026-06-14-phase3-d2-sub11-remediation-full-supervisor-decomp.md`.

**Phase 2 Execution Record (2026-06-04)**: Cross-verified Sub10/11/12 post-remediation. Full details: `2026-06-04-phase3-d2-sub10-12-perfection-phase2-crossverify.md`.

**Phase 3 Execution Record (2026-06-04)**: Final gate — Guardian 10.0, 56 pytest (`phase3_perfection_gate_verify.py`), North Star met, plan marked complete in MC/agent-context. Full details: `2026-06-04-phase3-d2-sub10-12-perfection-phase3-final-gate.md`.