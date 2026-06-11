# 2026-05-31 — Phase 2 Slice 03: Introduction of Simple Hash Chaining for Risk Decision Lineage

**Parent**:
- `2026-05-31-elon-phase2-02-complete.md`
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 deliverable 4: "Cryptographic / hash-chained provenance for every decision that reaches Final Arbitration (simple sequential hash or Merkle tree per decision_context_id)")
- `2026-05-31-elon-musk-first-principles-trading-system-analysis.md` (60-day target)

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 03. No implementation work will begin until this entry exists and a dedicated Plan Mode has been completed.

---

## Hypothesis

Phase 2 Slice 01 made the two critical risk decisions (policy + final arbitration) emit as typed events on the Event Bus.

Phase 2 Slice 02 made them correlated via a shared `decision_context_id` + lightweight reference.

The next required step per the global plan is to make this lineage **tamper-evident** through simple hash chaining.

**Hypothesis**:
Adding a `prev_hash` (or `prev_event_hash`) field to the metadata of the `risk.final_arbitration.result` event (referencing the hash of the preceding `risk.policy.decision` event for the same decision_context_id) creates the first real hash-chained provenance link in the core risk decision path.

This is the smallest possible, reversible slice that directly implements the "prev_hash chaining" part of the 60-day / Phase 2 target without jumping to a full Merkle tree or system-wide hashing yet.

It follows the proven pattern: make the current (still forgeable) lineage state visible and start enforcing the chain incrementally.

---

## Falsifiable Predictions

1. After this slice, the `risk.final_arbitration.result` event will contain a `prev_hash` field in metadata that matches the hash of the corresponding `risk.policy.decision` event for the same `decision_context_id`.

2. A new test will verify that tampering with the policy decision payload would break the hash chain validation (even if we only do best-effort checking initially).

3. Guardian will report a "Hash Chain Coverage" metric for the risk decision pair (starting from the first implementation).

4. The change remains fully reversible and has zero impact on gate behavior or capital decisions.

5. The Event Bus events now carry the first elements of cryptographic lineage as required by the 90-day roadmap.

---

## Scope (Strictly Limited)

**In scope**:
- Compute a simple hash (e.g., SHA256 of the serialized previous event payload + sequence or a canonical representation) when publishing the arbitration result.
- Store it as `prev_hash` in the arbitration event metadata.
- Store the current event's own hash (or make it easy to compute) for future chaining.
- Update the correlation test to also assert the hash link exists.
- Add minimal Guardian visibility for hash chain presence.
- Public evolution entry + completion entry.

**Out of scope** (to keep the slice small):
- Full Merkle tree or tree-based provenance (later slice).
- Hash chaining on agent proposals, dream state, or other topics yet.
- Enforcing the hash chain at subscribe time or in production (make it visible first).
- Changes to DomainEvent schema (keep in metadata for now).

---

## Why This Slice Now

The global plan is explicit: after typed + correlated, we need **hash-chained provenance**.

Doing a minimal `prev_hash` link between the two events we already have on the bus is the perfect next forcing function. It makes the "tamper-evident" property real for the most critical risk decisions while staying within the "small, measurable, reversible slices" rule.

This is exactly how Elon-style execution has been conducted throughout this entire aperture hardening track: incremental, physics-first, forcing functions before big architectural overhauls.

No deviations from the 2026-05-31 global plan will be tolerated.

---

## Reversibility & Safety

- All hashing is additive metadata.
- The hash computation can be turned off with a single flag or comment.
- No effect on any trading decision logic.

---

**This entry opens Phase 2 Slice 03.** Plan Mode + skill reviews are required before any code changes.