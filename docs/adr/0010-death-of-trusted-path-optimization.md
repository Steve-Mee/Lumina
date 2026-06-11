# ADR-0010: Death of the Trusted-Path Optimization (Capital Aperture Hardening)

**Status**: Accepted  
**Date**: 2026-05-31  
**Phase**: 1.3.4 closure of the 2026-05-31 Elon first-principles aperture track

## Context

The original 2026-05-31 Elon Musk first-principles analysis identified four FATAL structural bypass mechanisms (B-001 through B-004) plus a mutable god-flag that together created multiple trusted paths around the late authoritative Admission Chain + Final Arbitration. These paths allowed orders to reach the broker while skipping critical risk, constitution, and provenance checks.

This was not a performance optimization in the healthy sense — it was architectural erosion that made safe self-evolution and REAL-mode capital protection structurally difficult to guarantee.

Phases 1.1–1.3 were executed to first make the leaks painful (runtime enforcement), then structurally remove the mechanisms, then perform complete hygiene so that no traces remained in code, tests, or active documentation.

## Decision

We have permanently eliminated the trusted-path optimization pattern for capital-moving decisions.

- All four B-00x mechanisms have been structurally removed.
- The god-flag has been purged.
- The `aperture_guard` module has been repurposed as a permanent regression detector (any call in strict modes is fatal).
- Zero traces remain in production code or tests (per explicit requirement that leaving references "because they must be used" is unacceptable).
- The only path from any decision to broker.submit_order in strict modes is the fully enforced authoritative gate chain.

Future evolution experiments or performance work may only optimize *inside* the authoritative path. Shortcuts around it are architecturally forbidden in strict modes.

## Consequences

**Positive**:
- The capital aperture is now narrow by construction in REAL and sim_real_guard.
- Cognitive load for anyone reading risk/execution code is dramatically lower (only one story exists).
- Regression protection is permanent and self-enforcing via the detector + Guardian.
- Safe self-evolution velocity can increase because the blast radius of mistakes is structurally contained.
- Forcing functions (Guardian, agent-context, evolution log) now accurately reflect reality.

**Negative / Trade-offs**:
- All order paths must now pay the full cost of the authoritative gate (this is the explicit reason the parallel gate optimization track was deferred until after 1.3).
- Some emergency/force-close paths required extra defensive hygiene.

**Risks**:
- Performance pressure could tempt future developers to re-introduce shortcuts. Mitigated by the permanent fatal detector + constitution-guard requirement on any risk-adjacent change + public evolution entries.

## Alternatives Considered

- Keep limited, well-documented, time-boxed bypasses for "performance" or "emergency" cases.
  - Rejected. Any such mechanism re-creates the original erosion problem and violates the first-principles north star.

- Only remove in production code but leave references in tests "because they must be used".
  - Explicitly rejected by user feedback (Elon would not be satisfied).

- Treat the cleanup as purely technical debt without architectural status.
  - Rejected. This was a core first-principles decision about the shape of the system.

## Related

- 2026-05-31-elon-musk-first-principles-trading-system-analysis.md
- 2026-05-31-elon-aperture-hardening-90-day-roadmap.md
- All 1.2.x and 1.3.x evolution entries (especially 1.3.4 zero-trace hygiene and the final inventory closure)
- `lumina_core/risk/aperture_guard.py` (the permanent detector)
- `project-dna/lumina/operating-system/rules/aperture.yaml`

This ADR records the architectural death of the trusted-path pattern. Implementation details live in the evolution log.