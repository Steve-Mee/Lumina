# 2026-05-31 — Phase 2 Slice 04: Activate Hash Chain Monitoring in Guardian + Basic Risk Decision Provenance Reconstruction

**Parent**:
- `2026-05-31-elon-phase2-03-complete.md` (Slice 03 delivered simple prev_hash chaining between the two core risk decisions)
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 success gate: "Provenance reconstruction script exists and is used in at least one post-trade audit" + "DNA Guardian now has a permanent 'Aperture' dimension")

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 04. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

We now have typed, correlated, and hash-chained events for the two most critical risk decisions on every order attempt that reaches the gate (`risk.policy.decision` and `risk.final_arbitration.result`).

However, writing the hashes is not enough. Per the global plan, we must make the chain **actively monitored** and begin providing **reconstruction capability**.

**Hypothesis**:
Adding explicit hash chain health monitoring inside the Guardian (for the risk decision pair), combined with a small, focused provenance reconstruction helper that can walk the chain for a given `decision_context_id` using the `prev_hash` / `event_hash` links, will turn the new hash chaining mechanism from "we write it" into a real, observable, forcing-function capability.

This is the smallest next slice that directly advances two Phase 2 success criteria:
- Provenance reconstruction script exists and is used.
- Guardian has a stronger permanent Aperture dimension.

It follows the proven pattern: after making the mechanism exist (Slice 03), immediately make any breakage or incompleteness loud and actionable.

---

## Falsifiable Predictions

1. After this slice, a Guardian run will explicitly report "Risk Decision Hash Chain Health" for recent decisions (healthy / broken / partial).

2. There will exist a small, importable helper (e.g. `reconstruct_risk_decision_chain(decision_context_id)`) that, given a decision_context_id, returns the ordered list of the two risk events with their hashes verified.

3. If someone (in a test) tampers with one of the events' payloads after publication, the Guardian will flag the chain as broken for that decision_context_id.

4. The reconstruction helper is used in at least one test or audit path.

5. All changes remain small, reversible, and have zero impact on trading logic.

---

## Scope (Strictly Limited)

**In scope**:
- Add a new small section in `scripts/dna_guardian/validate_dna.py` that checks the last N risk decision pairs for hash chain integrity (using the existing fingerprint logic).
- Create a small, focused helper (probably in `lumina_core/risk/` or a new small `provenance.py`) that can reconstruct the risk decision chain for a decision_context_id from bus history and validates the hashes.
- Wire the helper into the Guardian check so it can be exercised.
- Update one or two tests to exercise the reconstruction.
- Public evolution entry + completion entry.
- Tiny agent-context update if needed.

**Explicitly out of scope**:
- Full system-wide provenance (agent → dream → risk allocation → arbitration → fill).
- Merkle tree structures.
- Automatic breaking of trades on broken chains (visibility + forcing function first).
- Changes to Event Bus or DomainEvent schema.

---

## Why This Slice Now (Global Plan Fidelity)

The 60-day success gate explicitly requires both:
- Hash-chained provenance, **and**
- A provenance reconstruction script that is actually used.

After Slice 03 (we write the chains), the highest-leverage next step is to make the chains observable and reconstructible. This is classic Elon first-principles execution: build the mechanism → immediately instrument it so deviation is impossible to hide.

This also strengthens the permanent "Aperture" dimension in the Guardian (another explicit Phase 2 deliverable).

---

## Reversibility & Safety

- The Guardian check is read-only / best-effort.
- The reconstruction helper is purely observational.
- No production behavior changes.

---

**This entry opens Phase 2 Slice 04.** Plan Mode + skill reviews (at minimum constitution-guard) are required before implementation.

*Red thread: fully typed + correlated + hash-chained + now actively monitored and reconstructible risk decisions on the single authoritative path.*