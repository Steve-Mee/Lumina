# ADR-003: Central Event Bus Contract (AgentBlackboard)

**Status:** Accepted  
**Date:** 2026-04-23  
**Deciders:** LUMINA Engineering (Steve + AI)

---

## Context

LUMINA v52 introduced `AgentBlackboard` as a central publish/subscribe bus for
inter-agent communication.  However, topic names, payload schemas, and
backpressure policies were defined ad-hoc across multiple modules.  This creates:

- Hidden coupling when a publisher changes its payload structure.
- Difficult debugging when a subscriber receives unexpected payload shapes.
- No single place to see "what topics exist and what they contain".

## Decision

Formalise the event bus contract with:

### Canonical Topics

| Topic | Producer(s) | Payload keys | Backpressure |
|-------|------------|--------------|--------------|
| `agent.emotional_twin.proposal` | `EmotionalTwinAgent` | `signal`, `confidence`, `bias_scores` | block_fail |
| `agent.news.proposal` | `NewsAgent` | `signal`, `impact`, `headline` | block_fail |
| `agent.tape.proposal` | `MarketDataService` | `signal`, `tape_delta`, `volume_ratio` | block_fail |
| `agent.swarm.proposal` | `MultiSymbolSwarmManager` | `dream_state`, `symbol`, `signal` | block_fail |
| `agent.swarm.snapshot` | `SwarmManager` | `cycle_id`, `metrics` | drop_and_audit |
| `execution.aggregate` | `LuminaEngine` | `signal`, `confidence`, `reason` | block_fail |
| `market.tape` | `MarketDataService` | `bar`, `timestamp`, `regime` | drop_and_audit |
| `meta.reflection` | `MetaAgentOrchestrator` | `hyperparam_suggestion`, `generation` | drop_and_audit |
| `evolution.promoted` | `EvolutionOrchestrator` | `dna_hash`, `fitness`, `mode` | drop_and_audit |

### Backpressure Policies

- **block_fail**: Queue full → raise immediately.  For topics that affect REAL
  trade decisions.  Subscribers must be fast.
- **drop_and_audit**: Queue full → discard message, log to `logs/security_audit.jsonl`.
  For telemetry and monitoring topics.

### Producer Allowlists

Critical topics (`execution.aggregate`, `agent.*.proposal`) have explicit
producer allowlists in `AgentBlackboard.__init__`.  Unauthorized publishers
are rejected and audited.

### Payload Validation

Topic payloads are validated against Pydantic models defined in
`lumina_core/engine/agent_blackboard.py` (to be added in v54).  Until then,
publishers are responsible for payload correctness.

## Consequences

- **Positive:** Single reference for all bus topics and their semantics.
- **Positive:** `block_fail` on execution topics prevents silent data loss.
- **Positive:** Producer allowlists reduce agent spoofing attack surface.
- **Neutral:** Future Pydantic payload validation adds ~5 µs/event overhead.
- **Negative:** Adding a new topic requires updating this ADR — small process overhead.

## Enforcement

- `tests/test_agent_blackboard.py` verifies producer allowlists.
- This ADR is the authoritative reference; any topic additions must update this
  document and the allowlist in `agent_blackboard.py`.
