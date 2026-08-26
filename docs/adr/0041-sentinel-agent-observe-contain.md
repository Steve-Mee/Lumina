# ADR-0041: Sentinel Agent — Observe → Contain (Network/Token Domain)

**Status:** Accepted  
**Date:** 2026-08-11  
**Deciders:** LUMINA Engineering  
**Related:** ADR-0040 Fabric-only foundation, SECURITY_HARDENING.md

## Context

ADR-0040 established permanent non-goals and a Sentinel shell. 90-day scope
requires an operational agent that can **observe** intrusion-class signals and
**contain** network/token exposure without becoming a trading god-module.

## Decision

1. **SentinelAgent** (`lumina_core/sentinel_agent.py`) is process-scoped, tickable,
   and starts with the Command Deck backend when present.
2. **Domain-limited hard veto** (equal rank to ConstitutionalGuard **only** for):
   network bind, tokens, authn/authz anomalies, intrusion indicators, unauthorized
   external connections, bus unauthorized producers (security signal only).
3. **Forbidden:** place/cancel orders, strategy mutation, position sizing, REAL arm,
   architecture self-mod, birth wipe.
4. **Containment SSOT:** `state/sentinel_containment.json` — when active:
   - non-loopback clients are denied (middleware)
   - weak Fabric tokens remain rejected outside SIM
   - operators clear via explicit clear path (not auto Twin)
5. **Thresholds (fail-closed burst):**
   - ≥20 auth failures / 60s → contain
   - ≥30 rate-limit hits / 60s → contain
   - ≥5 unauthorized bus producers / 300s → contain
6. **IP allowlist:** `LUMINA_IP_ALLOWLIST` (CIDR or IPs). Enforced for non-loopback
   clients via middleware; required for non-loopback bind (ADR-0040).
7. **API TLS:** `LUMINA_API_TLS_CERT` + `LUMINA_API_TLS_KEY` enable uvicorn TLS;
   non-loopback bind requires TLS/mTLS + allowlist + `LUMINA_SENTINEL_ACTIVE`.
8. **Weak Fabric tokens:** `sim-dev-token` and known placeholders forbidden for
   Brain outside SIM; in SIM require `LUMINA_FABRIC_ALLOW_SIM_DEV_TOKEN=true`.
   SimHost may still default to sim-dev-token for pure local SIM only.
9. **Prometheus `/metrics`:** loopback free; off-loopback requires API key unless
   `LUMINA_METRICS_PUBLIC=true` (explicit ops scrape opt-in).

## Consequences

### Positive
- 24/7 intrusion surface can be contained without touching capital logic
- Impossible to skip TLS/allowlist for public bind
- Clear audit trail (`logs/sentinel_audit.jsonl`)

### Negative
- Burst thresholds may false-positive under misconfigured load tests
- Full IDS pattern ML / self-evolving rules remain future (sandbox + promotion)

## Alternatives considered

1. Full IDS with auto network quarantine of host OS — rejected for scope/risk  
2. Sentinel may trip trading SAFE_MODE — deferred; domain separation preferred  
3. Soft-warn only on auth bursts — rejected (fail-closed)

## Links

- ADR-0040, ADR-0030 (architecture self-mod still human marker)
- `lumina_core/cyber_sentinel.py`, `lumina_core/sentinel_agent.py`
- `lumina_os/backend/sentinel_middleware.py`
