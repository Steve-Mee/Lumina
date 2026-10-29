# ADR-0061: SIM account whitelist and HMAC LIVE_RELEASE (S1)

**Status:** Accepted  
**Date:** 2026-10-29  
**Deciders:** LUMINA Engineering

Numbering note: the integration plan drafted S1 as ADR-0060. S0 already occupies
ADR-0060 (ungated-place freeze). This record is ADR-0061. The S0 freeze is
unchanged.

## Context

S0 (ADR-0060) hard-blocks ungated `place_order` paths (`UNGATED_PLACE_BLOCKED_S0`)
and keeps `supervisor_tick_exec` closed for research signals. Binding decisions
D1–D11 still apply. Two safety gaps remained:

- **G-WL:** NinjaTrader account checks used prefix helpers (`Sim*`, `DEMO*`).
  Any `SimFoo` matched. An empty configured name in `sim` skipped the match.
- **G-LIVE:** There was no HMAC `LIVE_RELEASE`. A yaml flag plus file hash
  without HMAC is too weak (D4).
- **G-MUT:** Account / whitelist / `live_release` keys were agent-mutable via
  code-evolution and hot-reload.
- **G-SIMBYP:** `RiskOrchestrator` set `enforce_rules` only for `real`, so
  `sim_real_guard` could skip Brain risk caps.
- **G-CS:** The NT AddOn used the same prefix heuristic with no C# whitelist
  tests.

Research SIM orders stay **S3**. This ADR must not lift the S0 freeze, must not
enable a live account path, and must not weaken Risk Core, the Validation Gate,
Fase 5 floors, or ADR-0055 costs.

First principles:

- Capital preservation: no live order path exists in S1. A valid HMAC is not
  a live enablement.
- Fail-closed: empty whitelist, missing secret, wrong key, replay, clock skew,
  or a tampered payload rejects.
- Extreme intellectual honesty, rigorous testing, radical creativity: every
  reject code has a unit test; attack tests cover env/yaml rebind, monkeypatch,
  forgery, replay, and clock skew. The Elon Musk Mindset Protocol applies:
  a yaml flag or a prefix helper is not a lock.
- Kernmissie: self-evolving organism, trading DNA, capital preservation,
  minimal user intervention after birth. S1 does not reopen S0.

## Decision

- NEW `lumina_core/risk/sim_account_guard.py` is the Risk Core SIM admit.
  Membership is exact casefold. Prefix helpers are diagnostics only and never
  allow. Empty or omitted `sim_account_whitelist` denies every account.
  The process-frozen list cannot widen at runtime except through an HMAC-signed
  operator release (`purpose=sim_whitelist_widen`). Live names on the list are
  refused.
- NEW admission steps `sim_account_whitelist` and `live_release` sit on
  `CANONICAL_ADMISSION_STEPS` after `session_equity_sync` and before
  `risk_policy`. Both are in `UNBYPASSABLE_ADMISSION_STEPS` (env bypass
  forbidden in every mode).
- NEW `lumina_core/risk/live_release.py` verifies an HMAC-SHA256 hex-64
  review artifact inside the live Risk Core: `enabled`, human `approved_by`
  (not a research/agent id), `adr_path` + `adr_sha256`, UTC window, nonce,
  purpose, schema. Secret from env `LUMINA_LIVE_RELEASE_SECRET` only (min 16
  chars). Never in git, yaml, fabric.json, or the Event Bus. Missing/invalid/
  expired/wrong-key/replay/clock-skew/tampered payload → reject.
- `admit_live_orders` always returns `live_account_path_closed_s1` after a
  successful HMAC. S1 does not enable live orders.
- ADAPT NT `check_account_match`: whitelist first on SUBMIT. CANCEL/flatten
  may skip the whitelist so emergency exits still reach NT. REAL: demo ADR
  reason, then live_release, then S1 close.
- ADAPT C# `SimAccountWhitelist` + `LiveReleaseGuard` on
  `NtAccountOrderGateway`. Empty Fabric list denies. A Fabric
  `LiveReleaseEnabled` boolean without Brain HMAC attestation is not
  sufficient. Memory/SimHost gateway is unchanged so CI fills still work.
- ADAPT `RiskOrchestrator`: `enforce_rules` follows
  `ModeCapabilities.risk_enforced` (unknown mode → True). `sim` stays
  learning-mode (`risk_enforced=False`). Freeze the whitelist at initialize.
- ADAPT code-evolution forbidden keys/prefixes and hot-reload: whitelist,
  `live_release`, `research_execution_mode`, `account_name` cannot widen
  without process restart + signed release.
- `UNGATED_PLACE_BLOCKED_S0` and `supervisor_tick_exec` stay closed for
  research. Yaml `mode: sim` / `research_execution_mode` is not a control.

## Consequences

### Positive

- Unknown SIM accounts fail closed in Python Risk Core and the NT gateway.
- Live enablement cannot be faked with a yaml flag or a hash without HMAC.
- Agents cannot mint or rotate the HMAC secret.

### Negative

- Operator `fabric.json` without `SimAccountWhitelist` denies NT places until
  the launcher rewrites the demo name onto the list.
- REAL later admission steps (audit fail-closed, VaR) are latent on the default
  chain until a later ADR opens the live path. They remain in code and are
  covered via `sim_real_guard`.

## Alternatives considered

1. Prefix `Sim*` allow — rejected: G-WL; any `Sim999` would place.
2. File hash without HMAC — rejected: D4.
3. Put the HMAC secret in `config.yaml` / `fabric.json` — rejected: agent-writable.
4. Duplicate the HMAC secret into C# `%APPDATA%` — rejected: copies the secret
   onto disk next to the AddOn. Fabric rejects REAL; Brain verifies HMAC.
5. Lift the S0 freeze so whitelisted SIM research orders can place — rejected:
   that is S3.

## Links

- Plan: `docs/plans/INTEGRATION_PLAN_research_to_nt8.md` (PR #62)
- S0 freeze: `docs/adr/0060-research-bridge-shadow-first.md`
- Cost card: `docs/adr/0055-nt-execution-cost.md`
- Fase 5: `docs/adr/0059-research-phase5-empirical-proof-and-fabric-ports.md`
- Charter: `RESEARCH_CHARTER.md`
- Constitution: `project-dna/lumina/constitution.md`
