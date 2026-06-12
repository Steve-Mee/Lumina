# ADR-0013: Birth Certificate v2

**Status**: Accepted

**Date**: 2026-06-11

## Context

Birth v1 completion relied on `lumina_birth_completed.flag` + policy zip existence. Trade count and near-complete grace (98%) allowed weak policies through. D4 campaign tooling could seed flags without training. Fail-closed deck access requires measurable readiness, not file presence alone.

## Decision

Birth Phase v2 completion requires a validated `state/lumina_birth_certificate.json` (schema version `2.0`) with:

- Policy SHA256 matching `lumina_ppo_policy.zip`
- OOS hold-out metrics (winrate, Sharpe, drawdown)
- Zero constitution violations during birth sim
- Minimum real data percentage and regime coverage

`artifacts_ok` / runtime bootstrap guard validate certificate v2, not v1 flags alone. Legacy flags are still written for tooling but are insufficient for deck/runtime access.

Rollback env: `LUMINA_BIRTH_V2_DISABLED=1` temporarily restores v1 flag+policy check (fail-closed default OFF).

## Consequences

- Positief: Deck and runtime gates enforce measurable readiness.
- Positief: Removes flag-seeding bypass from product paths.
- Negatief: All v1 installs require one re-birth.
- Risico's: CrossTrade outage blocks certified birth — practice mode remains synthetic without certificate.

## Alternatives Considered

- **Optie A:** Soft compat — v1 flags remain valid until v2 run — rejected per Musk hard-break decision.
- **Optie B:** Certificate optional enhancement — rejected; weak gate persists.

## Related ADRs

- ADR-0011: Tauri lifecycle gate
- ADR-0012: Single simulator SSOT
- ADR-0014: Curriculum + OOS gate
