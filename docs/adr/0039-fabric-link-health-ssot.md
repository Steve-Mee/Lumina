# ADR-0039 — Fabric Link Health SSOT (Live ≠ Proof)

**Status:** Accepted  
**Date:** 2026-08-10  
**Related:** ADR-0035 Execution Fabric gRPC, Code Red NT stability, Operator Vault

## Context

Operators saw **LUMINA Link RED** (“Host stopped”) while **Operator Vault GREEN** (14/14 checks).  
Root cause: three GREEN dictionaries (Link live sessions, diagnostic report, sticky paper certificate) without continuous reconciliation.

## Decision

1. **Single health model** `build_fabric_link_health` / `GET /api/setup/fabric-link-status`.
2. **Live level** `RED | AMBER | GREEN | RESTARTING` — host + port + Brain session/supervisor.
3. **Proof** = dual-plane diagnostic certificate (orders + historical_bars), time-boxed.
4. **`green` API field** = live GREEN only (never certificate alone).
5. **`gate_birth_ok`** = host up **and** recent proof (Birth / seal).
6. Vault UI shows **live** and **proof** as separate badges; primary color is live.

## Consequences

- Systems Go may proceed on `host_ready + proof` (AMBER OK); trading gates still fail-closed on live.
- Paper 14-day cert is legacy proof storage only — not Vault primary GREEN.
- Link window `RESTARTING` reduces false Repair panic during AddOn recycle.

## Rejected alternatives

- Trust certificate for UI GREEN (caused dual-lie).
- Require live GREEN for cold-start always (too strict when Brain not yet connected).
