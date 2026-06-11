# 2026-05-31 — Phase 2 Slice 13: Add Best-Effort Hash Chain Validation Warnings in the Guardian (Make Breaks Scream)

**Parent**:
- `2026-05-31-elon-phase2-12-complete.md` (Slice 12 extended the continuous hash chain upstream to dream/multi-agent coordination roots)
- `2026-05-31-elon-phase2-12-dream-and-multi-agent-lineage.md`
- `2026-05-31-elon-aperture-hardening-90-day-roadmap.md` (Phase 2 deliverable 4: cryptographic/hash-chained provenance + Guardian "Aperture" dimension with degradation detection)

**Protocol Status**: This is the formal opening hypothesis entry for Phase 2 Slice 13. No implementation begins until this entry and a dedicated Plan Mode are complete.

---

## Hypothesis

In Slices 03–12 we built:
- Continuous `prev_hash` chaining on the core risk decision path (gate_entry → risk.policy.decision → risk.final_arbitration.result).
- Upstream extension so the chain can start from proposal events on the main bus (Slice 11) and even from dream_state / multi-agent coordination events (Slice 12).
- A reconstruction helper (`decision_lineage.reconstruct_risk_decision_chain` + `is_chain_healthy`) that walks the chain and reports `hash_ok` per link.

**Current reality**:
- The reconstruction helper already computes `hash_ok` for every link (tampering or broken chain is detectable in code).
- However, the Guardian (the primary daily forcing function + public health signal) only reports "reconstruction helper available" and "wiring active".
- There is **no active screaming** when a chain is broken, when `hash_ok=False` appears for a recent decision_context_id, or when the chain is suspiciously short/missing expected nodes.
- Broken lineage is currently a silent (or only post-audit) failure. It does not create pain, degradation signals, or public forcing-function pressure.

**Hypothesis**:
By adding best-effort, loud, actionable hash-chain validation warnings inside the Guardian (the single most visible daily health artifact), we turn the new cryptographic spine into a true forcing function:
- Any broken or incomplete chain for recent decision_context_ids produces clear ⚠️ / 🔴 output in every Guardian run.
- The Aperture Integrity Score (or a new sub-dimension) degrades when hash-chain health is poor.
- This makes "our beautiful lineage is lying to us" impossible to ignore — exactly the Elon first-principles mechanism of making problems painful and public.

This is the smallest reversible slice that converts the observability we just built (Slices 03–12) into an active, screaming regression detector and forcing function.

---

## Falsifiable Predictions

1. After the slice, running the Guardian on an environment with at least one broken or incomplete chain (synthetic or real) will produce explicit, loud warnings naming the affected decision_context_id(s), the broken link(s), and recommended action.
2. Guardian output will contain a clear "Hash Chain Health" or "Lineage Integrity" section with counts (healthy / broken / missing nodes) and a degradation signal when problems exist.
3. The Aperture Integrity Score logic (or a new sub-score) will be influenced by hash-chain health (or a separate visible "Lineage Health" metric will be added).
4. Zero negative impact on Guardian runtime, on any trading path, or on the reconstruction helper itself.
5. The change remains best-effort and non-blocking (Guardian never crashes or blocks on lineage issues).

---

## Scope (Strictly Limited)

**In scope (this slice only)**:
- Extend `scripts/dna_guardian/validate_dna.py` (or a small helper it calls) with best-effort hash-chain validation logic.
- Use the existing `reconstruct_risk_decision_chain` + `is_chain_healthy` helpers.
- Add a visible section in Guardian stdout (and ideally in the structured JSON it can emit) that reports:
  - Recent decision_context_ids examined (last N hours or last K decisions).
  - Count of chains with `hash_ok=False` or suspiciously short chains.
  - Explicit call-outs for broken links (which event, which prev_hash mismatch).
- Make the output loud (⚠️ / 🔴 / ACTION REQUIRED language) when problems are found.
- Optional tiny degradation contribution to the existing Aperture Integrity Score or a new "Lineage Integrity" note.
- One or two synthetic test cases (or extension of existing Guardian tests) proving the warning fires.
- Public completion entry.

**Out of scope**:
- Hard failure or blocking behavior in Guardian (must remain best-effort and non-fatal).
- Full provenance report UI (separate item on the list).
- Downstream (order submission/fills) lineage.
- Shadow deployment.
- Changing the reconstruction helper itself (only consuming it).
- Making this run on every single decision in production (start with best-effort sampling of recent contexts the Guardian can see).

---

## Why This Slice Now

We spent 12 slices making the chain real, continuous, and rooted at the earliest intention formation point.

The next natural and highest-leverage forcing function (per Elon's explicit preference for painful, public, measurable mechanisms that make problems impossible to ignore) is to make the Guardian **scream** when that chain is broken or missing.

Without this, the beautiful lineage we built risks becoming another silent observability feature that nobody looks at until after a problem.

This slice closes the loop: build the physics → make violations of the physics loud and public every single day.

It directly advances the 90-day roadmap requirement that "DNA Guardian now has a permanent 'Aperture' dimension in its health scoring and degradation detection."

---

## Reversibility & Safety

- Purely additive reporting code inside the Guardian.
- All logic is best-effort and wrapped in try/except (existing Guardian pattern for optional deep checks).
- Can be disabled or rolled back in one commit with zero effect on trading, risk, or even other Guardian dimensions.
- No new dependencies, no new critical paths.

---

**This entry opens Phase 2 Slice 13.** Plan Mode + skill reviews (constitution-guard + event-bus-contract + risk-safety-review where relevant) required before implementation.

*Red thread: The single authoritative path must not only exist and be hash-chained — violations of that chain must be impossible to miss in the primary daily health artifact.*