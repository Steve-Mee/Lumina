# 2026-05-31 — Phase 2 Slice 14: Strengthen Reconstruction into a Clean "Full Pre-Trade Decision Provenance" Report

**Parent**:
- `2026-05-31-elon-phase2-13-complete.md` (Slice 13 made broken hash chains scream loudly in the Guardian)
- `2026-05-31-elon-phase2-12-complete.md` and earlier (the continuous hash-chained lineage from dream/multi-agent roots through proposals → gate_entry → risk.policy.decision → final_arbitration)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 3 deliverable 1: "One human, 20 minutes" audit — a single script + markdown view showing complete provenance + constitution checks + risk numbers + agent lineage for any trade)

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 14. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

Across Slices 03–13 we have built:
- A complete, cryptographically chained lineage (decision_context_id + prev_hash) from the earliest intention formation (dream + multi-agent coordination) all the way through proposals, admission.gate_entry, risk allocation, and Final Arbitration.
- `lumina_core/risk/decision_lineage.py` with `reconstruct_risk_decision_chain()` that returns a structured list with `event_hash`, `prev_hash`, and `hash_ok` for every node.
- Active screaming in the Guardian (Slice 13) when any recent chain is broken.

**Current reality**:
- The reconstruction helper is powerful but low-level. It returns raw event dicts.
- To get a human-auditable story for a specific trade or decision, a developer or risk reviewer must manually stitch together:
  - The chain from decision_lineage
  - The original proposal payloads (what the agents actually proposed and why)
  - The risk numbers and limits applied at each step
  - The Final Arbitration outcome and reasoning
  - Agent identities and blackboard correlation
- There is no single, clean, copy-pasteable artifact that a human can look at in 5–10 minutes and understand the full pre-trade decision provenance for a given `decision_context_id`.

**Hypothesis**:
By adding a small, focused "provenance report" layer on top of the existing reconstruction helper (plus targeted lookups into proposals, blackboard events, and risk decisions), we can produce a single, human-readable Markdown (or structured text) report for any decision_context_id that tells the complete story:

- When and how the intention was first formed (dream / meta / coordination context)
- Which agents contributed proposals and with what confidence/reasoning
- The exact path through the capital aperture (gate_entry → risk allocation → final arbitration)
- The cryptographic chain integrity (all `hash_ok` values)
- Key risk numbers, limits, and the Final Arbitration verdict
- Any constitution or policy violations along the way

This directly advances the original 90-day roadmap goal of making the aperture "the easiest and most observable way to reason about the system" and provides the foundation for the "one human, 20 minutes" audit capability.

This is the natural, high-value next forcing function after making the chain scream: turn the screaming detector into a clear, actionable, human-consumable explanation.

---

## Falsifiable Predictions

1. After the slice, there will exist a function or CLI entrypoint (e.g. `python -m lumina_core.risk.decision_lineage report <decision_context_id>`) that produces a clean, readable provenance report for any decision_context_id that has gone through the authoritative path.
2. The report will include (at minimum):
   - Decision context ID and timestamp range
   - Upstream origin (dream / coordination / proposal events with key fields)
   - The ordered, hash-verified chain (gate → risk decision → arbitration) with `hash_ok` status per link
   - Summary of agent proposals that fed into the decision
   - Final risk numbers and arbitration outcome
   - Any detected breaks or anomalies
3. The report will be usable both programmatically (returns structured data + markdown string) and from the command line.
4. Guardian will gain a new optional line or `--provenance <ctx>` mode that can emit the report for recent broken chains.
5. Zero impact on any trading or risk decision logic. The report layer is read-only and best-effort.

---

## Scope (Strictly Limited — One Slice)

**In scope**:
- Extend `lumina_core/risk/decision_lineage.py` with a new `build_pretrade_provenance_report(decision_context_id, *, event_bus=None, blackboard=None) -> dict` (and a `format_as_markdown(report) -> str` helper).
- The report should intelligently pull:
  - The core risk decision chain (already exists)
  - Matching proposal events (agent.*.proposal) for context
  - Key fields from gate_entry, risk.policy.decision, and final_arbitration.result
  - Blackboard correlation where useful
- Make it work even with partial data (best-effort, like the rest of the lineage system).
- Add a simple CLI entrypoint or script (e.g. `python -m lumina_core.risk.provenance_report <ctx>`) for quick human use.
- One strong test that generates a realistic (synthetic) chain and verifies the report contains the expected sections and hash_ok status.
- Small Guardian integration note (optional `--provenance` or automatic inclusion for broken chains in the warning output).
- Public completion entry + agent-context update.

**Out of scope (defer to later slices)**:
- Full downstream lineage (order submission, fills, P&L attribution) — that is a separate item on the list.
- Beautiful web UI or dashboard.
- Automatic attachment of the report to every trade in the ledger (future enhancement).
- Shadow deployment integration.
- Changes to any live trading or risk path.

---

## Why This Slice Now

We have spent 13 slices making the single authoritative path real, cryptographically chained, rooted at the earliest intention, and actively monitored with screaming warnings.

The next highest-leverage step is to make that chain **immediately useful to a human** without requiring them to be a deep expert in the reconstruction helper.

This is classic Elon-style physics: we built the measurement system → now we make the measurement consumable and actionable at human speed.

It also directly serves the long-term north star in the 90-day roadmap ("one human, 20 minutes" full provenance audit).

---

## Reversibility & Safety

- Purely additive read-only reporting layer on top of already-existing helpers.
- No side effects on trading, risk, Event Bus, or blackboard.
- Can be removed or disabled in minutes.
- All logic is best-effort (partial data still produces a useful partial report).

---

**This entry opens Phase 2 Slice 14.** Plan Mode + skill reviews (constitution-guard + event-bus-contract) required before implementation.

*Red thread: The single authoritative capital aperture must not only be narrow, typed, and hash-chained — its complete history must be trivially understandable by a human in minutes.*