# ADR-0040: Fabric-Only Foundation, Emergency Opt-In, and Sentinel Domain

**Status:** Accepted  
**Date:** 2026-08-11  
**Deciders:** LUMINA Engineering + Operator (First Principles review)

## Context

Product SSOT (`config.yaml`) already selects Fabric/`ninjatrader` with
`fallback_on_fabric_failure=false`. Library defaults and ADR-0029/0035 residual
language still defaulted to CrossTrade when config was missing. The Operator
Vault emergency checkbox revealed CrossTrade credential fields but did **not**
write the runtime flag. Command Deck could bind `0.0.0.0`. Dual-plane GREEN
must never be theater (orders-only).

LUMINA is an experimental 24/7 self-evolving organism. Three laws:

1. Minimal human intervention
2. Max probability of becoming a top trader
3. Absolute capital + integrity protection

## Decision

### 1. Fabric is the only skeleton; CrossTrade is a loadable prosthesis

- Default `broker.live_provider` / library fallbacks: **`ninjatrader`**
- Invalid/missing provider → **ninjatrader** (never silent CrossTrade)
- CrossTradeBroker is **lazy-imported** (zero default import in factory /
  package `__init__`)
- Plugin load requires deliberate opt-in via
  `EmergencyOptInState` (`live_provider=crosstrade` **or**
  `fallback_on_fabric_failure=true`)

### 2. Single emergency control plane

- Module: `lumina_core/broker/emergency_opt_in.py`
- Machine truth: `broker.fallback_on_fabric_failure` (+ live_provider)
- Operator Vault checkbox writes this flag on save (and prefills from it)
- Append-only audit: `logs/emergency_opt_in_audit.jsonl`
- No silent Fabric→CrossTrade hop for orders; history hop only when flag true

### 3. Permanent non-goal: non-loopback without mTLS + allowlist + Sentinel

- Default API bind: `127.0.0.1`
- Override via `LUMINA_API_BIND` only if **all** are set:
  - `LUMINA_ALLOW_NON_LOOPBACK=true`
  - `LUMINA_MTLS_ENABLED=true`
  - `LUMINA_IP_ALLOWLIST` non-empty
  - `LUMINA_SENTINEL_ACTIVE=true`
- Enforced by `lumina_core/cyber_sentinel.py` (`resolve_api_bind_host`)

### 4. Dual-plane GREEN = Fabric + NT BarsRequest proof only

- `CRITICAL_CHECK_IDS` includes `historical_bars`
- `write_certificate` tags dual-plane proof; refuses if historical_bars
  explicitly not pass when checks provided
- Live GREEN remains host+brain live SSOT; Birth gate requires dual-plane
  certificate (not human/Twin vote)

### 5. Sentinel hard veto = ConstitutionalGuard rank for network/token only

- Domain: network bind, tokens, auth anomalies, intrusion signals, unauthorized
  external connections
- **Forbidden:** trading logic, strategy mutation, position sizing vetoes
- Minimal shell ships now; full IDS evolution is sandbox-gated later

### 6. Phase 2 unlock evidence bundle (minimum)

1. Multi-day (48–72h) uninterrupted Fabric-only run on Sim101 with zero
   CrossTrade code loaded
2. Full order lifecycle + historical bars + live ticks via native path + audit
3. Heartbeat timeout → SAFE_MODE → flatten 100% deterministic
4. No non-loopback bind or token leak in logs
5. Sentinel (or equivalent) zero critical alerts
6. Perfect Birth marker + human promotion marker

Without the complete bundle, Phase 2 stays closed.

### 7. Live-repo architecture self-mod: never without human promotion marker

- Aligns with ADR-0030 Architecture Meta-Controller
- Sandbox proposals only; live repo apply requires human promotion marker
  (future ultra-high-confidence Twin + multi-gate may assist but never replace
  this for architecture/code self-mod)

## Consequences

### Positive

- Architectural law matches product SSOT
- Operator intent becomes machine truth
- Smaller intrusion surface by default
- Dual-plane honesty preserved

### Negative

- Tests that assumed Crosstrade default must set provider explicitly
- Explicit Crosstrade order path still needs `live_provider=crosstrade`
  (plugin_loadable via that path)
- Non-loopback server deploys need four env flags + real mTLS/allowlist work

## Alternatives considered

1. Keep Crosstrade library default until “gates pass” — rejected; product already Fabric-first; residual default is betrayal.
2. Delete CrossTrade entirely — deferred; Phase 0 non-goal was removal; plugin demotion is sufficient now.
3. Soft-warn on 0.0.0.0 only — rejected; permanent non-goal requires hard veto.

## Links

- Supersedes residual default language in ADR-0029 / ADR-0035 regarding
  `live_provider` default = crosstrade
- ADR-0030 Architecture Meta-Controller
- ADR-0039 Fabric Link Health SSOT
- `lumina_core/broker/emergency_opt_in.py`
- `lumina_core/cyber_sentinel.py`
