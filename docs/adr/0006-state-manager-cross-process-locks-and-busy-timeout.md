# ADR-0006: Centrale State Manager voor Cross-Process Concurrency

**Status:** Proposed  
**Date:** 2026-05-02  
**Deciders:** LUMINA Engineering (Steve + AI)

## Context

LUMINA schrijft evolutie-state naar meerdere append-only JSONL- en SQLite-bestanden vanuit verschillende processen (launcher, backend endpoints, workers, tests). Bestaande bescherming met `threading.RLock` is alleen intra-process en voorkomt geen write-contention tussen processen.

Dit veroorzaakt drie risico's:

- Hash-chains kunnen breken wanneer meerdere writers dezelfde `prev_hash` lezen en parallel appenden.
- JSONL-bestanden kunnen partial writes of niet-deterministische volgorde krijgen onder zware contention.
- SQLite writers kunnen faillen met `database is locked` zonder consistente retry-strategie.

Voor een zelf-evoluerend systeem dat beslissingen auditbaar moet maken, is dit een architecture-level probleem.

## Decision

We introduceren `lumina_core/state/state_manager.py` als centrale state-laag voor evolutie-persistentie:

- **JSONL writes:** `safe_append_jsonl(path, record, hash_chain=...)`
  - gebruikt cross-process `filelock`
  - ondersteunt retry + exponential backoff bij lock contention
  - gebruikt `flush + fsync` voor sterke write-duurzaamheid
  - ondersteunt optionele hash-chaining (`prev_hash` + `entry_hash`)
- **SQLite writes:** `safe_sqlite_connect(path, ...)`
  - zet `PRAGMA journal_mode=WAL`
  - zet `PRAGMA busy_timeout`
  - past retry/backoff toe op lock/busy tijdens connectie-initialisatie
- **Gecentraliseerde lock-regie:** lockfiles onder `state/.locks/` (of `LUMINA_STATE_LOCK_DIR`)

Alle evolutie-state writers gebruiken nu deze manager:

- `DNARegistry`
- `VetoRegistry`
- `AgentBlackboard`
- `EvolutionLifecycleManager`
- `EvolutionRolloutFramework`
- `AgentDecisionLog`
- `append_hash_chained_jsonl`

## Consequences

### Positive

- Cross-process veilig append-gedrag voor JSONL-bestanden.
- Hash-chain integriteit blijft behouden onder parallelle writers.
- Minder flakey failures door consistente SQLite busy-handling.
- Eenduidige persistentie-API voor nieuwe evolutie-componenten.

### Negative

- Kleine write-latency toename door lock + fsync + backoff.
- Extra lock-bestanden in `state/.locks/`.
- Meer centrale afhankelijkheid: regressies in state manager raken meerdere modules tegelijk.

## Alternatives considered

1. **Alleen per-module `threading.RLock` behouden**  
   Verworpen: beschermt niet tegen multi-process contention.

2. **Alle state volledig migreren naar SQLite**  
   Verworpen: te grote migratie en verlies van eenvoudige append-only auditlogs.

3. **OS-specifieke locking (`fcntl`/`msvcrt`) zonder library**  
   Verworpen: hogere onderhoudslast; `filelock` is al dependency en cross-platform.

## Related ADRs

- ADR-0001: Bounded contexts + centrale event bus
- ADR-0002: Shadow deployment + human approval
- ADR-0003: Trading constitution + sandboxed mutation executor
- ADR-0005: Test suite overhaul (markers/timeouts/isolated fixtures)
