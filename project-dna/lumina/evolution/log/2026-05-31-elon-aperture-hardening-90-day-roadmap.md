# 2026-05-31 — Aperture Hardening 90-Day Execution Roadmap (Follow-up to Elon First-Principles Analysis)

**Parent Document**: `2026-05-31-elon-musk-first-principles-trading-system-analysis.md`  
**Scope**: Concrete, phased, measurable execution plan to close the capital aperture erosion gaps identified in the parent analysis.  
**Impact Class**: Large (touches core risk execution, contracts, and safety invariants).  
**Protocol Compliance**: This roadmap is documentation only. Every concrete code change requires fresh Plan Mode + full Recursive Self-Improvement Protocol + constitution-guard + risk-safety-review.

---

## North Star (90 Days)

By 2026-08-29 the Lumina capital aperture satisfies:

> "There is exactly one way for any decision (human, agent, or evolved DNA) to result in a real or paper-guard order reaching a broker: a fully typed, constitution-audited, Final-Arbitration-enforced, hash-chained path published on the Event Bus. All bypass mechanisms have been structurally eliminated or made impossible outside explicitly sandboxed, time-boxed, Guardian-audited SIM experiments."

**Primary Metrics** (first-principles):
- **Aperture Integrity Score** (new Guardian dimension): target ≥ 9.3/10
- **Bypass Usage Count** (REAL + guard modes): target 0 (permanent)
- **Decision Provenance Completeness**: ≥ 95% of trades fully reconstructible end-to-end
- **Evolvability of Risk Layer**: ≥ 9.0 (from ~7.5 baseline)
- **Incident Rate from Evolution Changes**: 0 in REAL for the 90-day period

---

## Phase 0 — Foundation & Visibility (Days 0-7, immediate)

**Goal**: Make the current leaks painful, visible, and impossible to ignore. No structural removal yet.

**Concrete Deliverables**:
1. Guardian extension (or new `--aperture` mode): detect usage of the three bypass flags + incomplete Order metadata in risk/safety/gate paths. Emit ⚠️ blocks + degradation signals.
2. Runtime assertions (fail-closed in REAL/guard modes): when any skip flag is encountered in strict modes → raise ConstitutionViolation + log + Guardian alert. SIM remains permissive with heavy logging.
3. New evolution entry + ADR draft for every current bypass usage site (with exact file:line).
4. Baseline measurement: run Guardian + new aperture checks; publish numbers in agent-context.md + dna_health_latest.json.
5. Update AGENTS.md (small clarification) and this roadmap with exact current bypass locations.

**Success Gate (Day 7)**: Guardian report shows explicit "Aperture Erosion" section with counts > 0. No code yet removed.

**Reversibility**: Trivial (the assertions are additive).

---

## Phase 1 — Pain + Containment (Days 8-30)

**Goal**: Eliminate the *easiest* bypass vectors and force all new code through the correct path. Make the "trusted path" optimization explicitly expensive and reviewed.

**Concrete Deliverables**:
1. Remove or make fatal the `skip_admission_chain_recheck` early return in broker_bridge.py (or add cryptographic "approval token" that expires and is only issued by the official gate in non-experimental modes).
2. Deprecate the engine mutable flag `admission_chain_final_arbitration_approved`. Replace with explicit per-decision context passed through the call stack (or Event Bus).
3. Mandate `payload_model=` on 100% of new Event Bus publishes (enforced via event-bus-contract skill + test).
4. Convert the 3-4 highest-volume blackboard/dream topics used in pre-trade decisions to strict Pydantic models (start with TradeIntent / DreamState critical fields).
5. Add unit + property tests that prove no Order can reach broker.submit_order in guard modes without full AdmissionChain + FinalArbitration trace (using the existing test scaffolding skill patterns).
6. First public "Aperture Integrity Score" published via Guardian.

**Success Gate (Day 30)**:
- Zero bypass usage in automated tests for guard modes.
- Guardian Aperture Integrity Score ≥ 7.5 (from baseline ~4-5 estimated).
- At least one full end-to-end decision lineage visible on the Event Bus for a live SIM trade.

**Reversibility**: Feature flags + 48h rollback window. All changes behind SIM-only initially.

---

## Phase 2 — Structural Closure (Days 31-60)

**Goal**: The three identified bypass mechanisms no longer exist in production code paths. The Event Bus is the primary (not side-channel) nervous system for trading decisions.

**Concrete Deliverables**:
1. Complete removal of the three skip layers (or reduction to a single, auditable, time-boxed "emergency experimental override" that requires human + shadow + explicit constitution audit).
2. 100% of agent proposals, risk allocations, arbitration decisions, and order submissions published as typed events with full lineage (decision_context_id + prev_hash chaining).
3. Subscribers to critical topics receive validated Pydantic model *instances* (not dicts) — requires evolution of EventBus + schemas (aligns with event-bus-contract skill vision).
4. Cryptographic / hash-chained provenance for every decision that reaches Final Arbitration (simple sequential hash or Merkle tree per decision_context_id).
5. Extended shadow deployment: every evolution experiment that touches risk logic must run in a "shadow aperture" mode that replays real market data but never touches the live broker.
6. DNA Guardian now has a permanent "Aperture" dimension in its health scoring and degradation detection.

**Success Gate (Day 60)**:
- Static + dynamic analysis proves 0 remaining bypass paths in non-experimental code.
- ≥ 80% of pre-trade decision volume flows through the typed Event Bus with models.
- Provenance reconstruction script exists and is used in at least one post-trade audit.
- No REAL or guard-mode incidents attributable to aperture changes.

**Reversibility**: Full git revert of the phase + Guardian-verified state restore. The hash-chaining is append-only so rollback does not corrupt history.

---

## Phase 3 — Physics-Grade Observability & Simplification (Days 61-90)

**Goal**: The aperture is not only narrow and typed — it is the *easiest* and *most observable* way to reason about the system. Large orchestrators touching capital paths have been decomposed or firewalled.

**Concrete Deliverables**:
1. "One human, 20 minutes" audit: a single script + markdown view that shows the complete provenance + constitution checks + risk numbers + agent lineage for any trade (live or historical).
2. Decomposition or strict interface firewalling of at least one major concentration point (meta_agent_core or runtime_workers trading paths) such that changes inside it no longer require understanding the entire engine.
3. Full integration of Aperture Integrity Score into the daily/periodic Guardian run and agent-context.md Summary.
4. Public demonstration: a 30-day SIM campaign with aggressive evolution experiments where the aperture caught 100% of unsafe proposals before they could reach the broker (with logs as evidence).
5. Update to constitution.md and invariants.json (if needed) to make "no structural bypasses in capital paths" an explicit near-immutable rule (requires Large protocol + human review).
6. Self-reference: the DNA Guardian itself has been improved using the new aperture visibility (Guardian scores its own reviews against the aperture contracts).

**Success Gate (Day 90)**:
- Aperture Integrity Score ≥ 9.3
- Evolvability of risk/safety/gate layer ≥ 9.0 (Guardian + human)
- Zero full-state resets required during the entire 90 days for core trading state.
- At least 3 evolution entries that were directly accelerated or made safer by the new provenance and aperture tooling.
- The parent hypothesis predictions for 90 days are either met or have clear, documented falsification with lessons learned.

---

## Cross-Cutting Requirements (All Phases)

- **Protocol**: Every code change touching risk, order flow, Event Bus, or safety follows fresh Plan Mode + this roadmap as reference + constitution-guard + risk-safety-review + evolution entry.
- **Measurement**: Guardian runs at least daily during active phases; results published. New aperture dimension added to dna_health_latest.json schema.
- **Forcing Functions**:
  - Every weekly sync starts with "Aperture Integrity" slide (Guardian numbers + bypass count).
  - Any PR that adds a new `skip_` or direct Order construction triggers automatic block + escalation.
  - Public evolution entries for every phase gate (success or failure).
- **Parallel Tracks**:
  - DNA Guardian / LLM sprint continues (improves the quality of the documents guiding this work).
  - Debt destruction on remaining weak files (self-improvement-protocol.md etc.) continues independently.
- **Risk Management**: All hardening work starts in SIM. Paper guard only after 2+ weeks clean SIM with evolution load. REAL only after explicit human + shadow gate on the *hardening changes themselves*.

---

## Success / Failure Criteria (Brutal)

**Success**: At day 90 we can say with evidence:

"The combination of the 2026-05-31 Elon analysis + this roadmap + disciplined execution has made the capital aperture of Lumina narrower, more observable, and more evolvable than at the start of the period, with zero capital or mission incidents attributable to the changes. Safe evolution velocity has increased as a direct result."

**Failure modes we will publicly document**:
- Any production incident in REAL/guard during the 90 days caused by aperture changes.
- Inability to remove the bypass mechanisms without introducing new hidden complexity.
- Guardian Aperture score plateaus below 8.0 due to implementation difficulty.
- The work becomes another "ambitious new system on dirty foundations" (we will kill it early if this pattern emerges).

---

## Immediate Next 7 Days (Concrete Checklist)

1. [ ] Run Guardian + publish baseline numbers (including this roadmap as a scanned document).
2. [ ] Add aperture erosion detection to Guardian (or manual script first).
3. [ ] Create the ADR or evolution entry that lists *every* current bypass site with exact line numbers.
4. [ ] New Plan Mode session for Phase 0/1 implementation (the first concrete PRs).
5. [ ] Update agent-context.md Summary to mention the new top debt item and 90-day aperture work.
6. [ ] Schedule the Day 7 gate review (public, with Guardian data).

---

**This roadmap exists to make the physics diagnosis in the parent document *actionable* without violating the small-step, evidence-based, fail-closed principles that define Lumina.**

*Companion artifact to the 2026-05-31 Elon Musk first-principles trading system analysis. Both entries are part of the approved extreme acceleration plan execution.*

**Next human/agent action required**: Enter Plan Mode for the first implementation increment (Phase 0 visibility + assertions). Do not write production code yet.