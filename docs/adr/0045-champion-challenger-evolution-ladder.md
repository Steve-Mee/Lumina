# ADR-0045: Champion / Challenger self-evolution ladder

**Status:** Accepted  
**Date:** 2026-08-14  
**Deciders:** LUMINA Engineering (Steve + AI)

## Context

DNA evolution in SIM is real. Trading-code evolution wrote to a sandbox store the engine never loaded. Calling H5 "Done" violated truth-seeking (constitution #3). Lumina must evolve as a pioneer without rewriting the live repo or endangering REAL capital.

First principles: the flying vehicle (champion) stays up; the new vehicle (challenger) proves on a drone ship (internal paper venue on live tape, zero NinjaTrader); then atomic swap with abort. Safety gates stay; allowlists may expand via council + Steve.

## Decision

- **Immutable core:** constitution, Admission Chain, risk/broker, live git-tree of those paths.
- **OverlayPort** loads `state/code_evolution/applied/{champion,challenger}/` by `runtime_role`. Default champion overlay is empty. Challenger files never leak into champion ticks (K1).
- **Apply writes challenger store only.** Champion `register_dna(version=active)` is never used by challenger (K2).
- Snippet eval only via `SandboxedCodeExecutor` (K3).
- **Challenger venue:** live MDS fan-out (non-blocking, K5), internal fills with spread friction + reality-gap gate (K6), hash-chained journal + replay (K7), own process/fault boundary (K4), one slot (K9).
- **Invalidation classifier** is not the proposer (K8). Snippet/indicator/lookback → `policy_incompatible` (Playground re-entry, never Birth). `confluence_threshold` only → `behavior_tweak`.
- **Council** (Twin, constitution, risk, swarm, evolution-proof) writes independent votes. Steve final. Timeout = no. Risk veto needs `override_risk_veto` + dual confirm (K14). Dual-channel: Phase Hub always, Telegram best-effort.
- **Cutover:** freeze bundle → flat book (K11) → complete bundle (K10) → make-before-break pointer flip → canary auto-restore (K13). Chaos drill required (K12). Rollback always, even after a long proof path.
- **Schema:** `organism_extensions.sqlite3` only (`org_*` columns). Overlay needing org-cols fails closed without matching ledger (K15). No ALTER of core tables.
- **Architecture sandbox:** real unified-diff apply on a temp copy; never invent optimistic health deltas. Human APPROVED still required; never auto-apply.
- **K1–K16** are merge-gates. Open critical item = no merge.
- **Waves are implementation order only.** After implementation, Done = every K-item has code + a test. An open K-item is not Done, even if its wave todo is checked.

Wiring closeout (same ADR): OverlayPort on champion follows `CHAMPION.json` (never `applied/challenger/`). Challenger paper intents run Admission Chain in sim-mode with `forbid_bypass`. VenueRuntime journals fills; tape replay is the K7 harness. Playground re-entry is requested for `policy_incompatible` and never starts Birth. Council notify writes Phase Hub always and Telegram best-effort. Architecture apply requires `COUNCIL.json` plus human `APPROVED`.

Code floors for code-as venue proof: min_days 5, min_trades 50, gap-gate pass.

## Consequences

### Positive

- Closed-loop self-evolution with selection pressure, without live-repo mutation.
- Champion isolation; falsifiable journals; instant abort.

### Negative

- Extra surfaces to maintain (venue, council, cutover).
- Fill model ≠ exchange matching (honesty via reality-gap, not a second exchange).

## Alternatives considered

1. Live-repo self-rewrite — rejected (unbounded capital/system risk).
2. New matching-engine “Lumina Exchange” — rejected (years of work, second fill-truth).
3. Restart Birth after every code change — rejected (suffocates evolution).
4. Skip rollback because the proof path is long — rejected (constitution #3).

## Links

- ADR-0002, 0003, 0004, 0030, 0032, 0033
- Code: `lumina_core/code_evolution/runtime_overlay.py`, `lumina_core/evolution/challenger_venue/`, `lumina_core/evolution/cutover.py`
- Tests: `tests/evolution/test_challenger_ladder_k.py`
