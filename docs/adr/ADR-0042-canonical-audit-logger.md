# ADR-0042: Canonical Audit Logger and Hash Chain

**Status:** Accepted  
**Date:** 2026-05-03  
**Deciders:** LUMINA Engineering

## Context

LUMINA used multiple parallel audit implementations with incompatible hash-chain behavior:

- `prev_hash + entry_hash` (file-lock + canonical serializer) in some security/governance paths.
- `prev_hash + hash` (different canonical serializers) in decision/evolution paths.
- direct append-only JSONL in at least one reconciliation path.

This fragmentation creates avoidable risk:

- chain verification logic differed by module, so integrity guarantees were not uniform.
- concurrency protection differed (`filelock`, `threading.Lock`, or none), causing cross-process race risk.
- schema/version fields were inconsistent, complicating forensics and replay.

For REAL mode, this violates the constitution goals around fail-closed, transparency, and auditability.

## Decision

We introduce one canonical system:

1. **Central facade:** `lumina_core/audit/logger.py` with `AuditLogger` and `StreamRegistry`.
2. **Canonical chain format:** `chain_version = "lumina_audit_v1"` with `prev_hash` + `entry_hash`.
3. **Single append primitive:** `safe_append_jsonl(..., hash_chain=True)` for all migrated audit streams.
4. **Per-stream routing:** preserve separate files via stream registration instead of a mega-log file.
5. **Compatibility bridge (max 2 weeks):** legacy `hash` is dual-written (equal to `entry_hash`) only where older readers still expect it.
6. **Fail-closed behavior:** in REAL mode, chain corruption/append failure raises `AuditChainError`; SIM/PAPER recover by rotating corrupt files.
7. **Flexible payload model:** canonical metadata is standardized while domain payload fields stay free-form at top-level.

Migrated paths include security, governance approvals, evolution decisions, agent decision logs, thought logs, constitutional audits, and trade reconciler audit writes.

## Consequences

### Positive

- One verifiable integrity model across safety-critical audit paths.
- Consistent cross-process locking and deterministic append behavior.
- Improved REAL-mode fail-closed semantics for audit corruption/write failures.
- Lower maintenance cost: replay and chain verification no longer depend on module-specific hashing variants.

### Negative

- Transition complexity while legacy `hash` readers are still active.
- Slight write overhead from canonical envelope fields and recovery checks.
- Additional migration burden for any external tooling that assumed old per-module schemas.

## Alternatives considered

1. **Keep module-specific chain formats** — rejected; continues integrity drift and duplicated validation logic.
2. **Adopt legacy `hash` as canonical** — rejected; weaker consistency and less reuse of existing file-lock + validator primitives.
3. **Single global audit file for all streams** — rejected; high contention, larger blast radius, and poorer operational isolation.

## Links

- Related ADRs: `docs/adr/0003-trading-constitution-sandboxed-mutation-executor.md`
- Related ADRs: `docs/adr/0001-bounded-contexts-central-event-bus.md`
- Related docs: `docs/AGI_SAFETY.md`
