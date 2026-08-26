# ADR-0011: Tauri lifecycle gate — backend SSOT for startup surface

**Status**: Accepted

**Date**: 2026-06-11

## Context

The Neural Command Deck (Tauri) previously inferred startup routing from mixed client heuristics (`skip_wizard`, sticky `priorPhase === "cockpit"`, birth status polling). That allowed bypass paths: operators could land on an empty Command Deck without valid PPO artifacts, or see the setup wizard after setup was complete when birth was still pending.

LUMINA requires fail-closed capital and artifact discipline (see constitution and ADR-0007). The Elon Musk Mindset Protocol applies: one truth, minimal moving parts, no hidden bypasses.

Three operator-visible surfaces exist: **Setup**, **Birth**, and **Deck**. The Tauri Command Deck consumes backend SSOT via `GET /api/setup/onboarding`.

## Decision

We introduce a **single backend function** `resolve_app_surface()` in `lumina_launcher/core/onboarding.py` as the lifecycle SSOT.

1. **`GET /api/setup/onboarding`** exposes `app_surface` (`setup` | `birth` | `hub` | `deck`) and `app_surface_reason`.
2. **`should_skip_wizard()`** is true for `hub` or `deck` (fail-closed on certificate/artifacts).
3. **Tauri client** maps `app_surface` → phase via `mapAppPhase()`; no sticky deck phase across **process** restart. Session override: operator may open deck from hub (`operatorDeckActive`).
4. **Post-birth cold-start default is `hub`** (`maturation_hub`), not deck — operator enters Command Deck deliberately.
5. **Cold-start cover:** `StartupReadinessScreen` while phase `loading` (named steps; soft Fabric probe; toasts suppressed).
6. **Defense in depth on deck:**
   - `useDeckLifecycleGuard` redirects if backend disagrees after mount.
   - `DeckBlockingOverlay` + `resolveDeckBirthGate()` block interaction when `!artifacts_ok`.
7. **Birth restart:** incomplete or interrupted birth always resolves to `birth` surface; auto-resume only with existing checkpoint (Phase 3). Explicit Resume/Wipe preferred over silent continue for interrupted/checkpoint states.
8. **No React Router** — `OnboardingGate` remains the phase switch; scope stays bounded.

## Consequences

- Positief:
  - One function determines cold-start surface; testable matrix (T1–T8).
  - Operators get predictable restart behaviour documented in `docs/command-deck-startup-runbook.md`.
  - Deck access without PPO artifacts is structurally blocked.
  - Streamlit UI removed (ADR-0016); Tauri + API are the only operator surfaces.
- Negatief:
  - API payload change; clients must consume `app_surface` (legacy fallback temporary).
  - Extra refresh/guard logic on cockpit mount.
- Risico's:
  - Race if birth completes during wizard — mitigated by `refresh()` after major actions.
  - Backend down forces `setup` surface even when setup was complete — intentional fail-closed.

## Alternatives Considered

- **Optie A:** Client-only phase machine with localStorage persistence.
  - Afgewezen: bypass risk, divergent Streamlit/Tauri behaviour.
- **Optie B:** React Router with URL paths (`/setup`, `/birth`, `/deck`).
  - Afgewezen: unnecessary scope; phase gate sufficient for desktop single-window app.
- **Optie C:** Auto-enter deck when birth completes without cinematic handoff.
  - Afgewezen: removes operator payoff and explicit consent moment.

## Related ADRs

- ADR-0001: Bounded contexts central event bus
- ADR-0007: Promotion gate real mode
- ADR-0010: Death of trusted path optimization

## References

- Implementation plan: `docs/requests/tauri-startup-gate-implementation-plan.md`
- API contract: `docs/lumina-core-api-contracts.md` §9
- Operator runbook: `docs/command-deck-startup-runbook.md`
