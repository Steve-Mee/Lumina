# LUMINA Deck — Cinematic Tier Contract

Visual surfaces are classified T0–T3 so onboarding, birth, and cockpit share one grammar.

| Tier | Surfaces | Glass | Motion | 3D |
|------|----------|-------|--------|-----|
| **T0 Form** | Wizard steps (backend, credentials, config) | `lumina-glass--panel`, minimal | Step fade only | None |
| **T1 Cinematic** | Welcome, Birth hero, Living Core, birth finale | `--overlay` + vignette | Orchestrator + luxury spring | Helix + bloom |
| **T2 Command** | HUD, deck panels, Decision Theater, annex | `--hud` / `--panel` | Mode motion + panel tab pulse | Optional |
| **T3 Utility** | Subsystems drawer (airlock), settings, diagnostics | `--panel` / `--overlay` | Snappy | None |

## Rules

1. **No T3 widgets inside T1** — PPO dashboards and training controls belong in diagnostics (T3), not birth hero (T1).
2. **Single status severity** — blocking overlay > rail chip > recovery banner; never duplicate backend/welcome messaging.
3. **Mode tagline** — visible only on ModeSwitch subtitle; rail icon uses tooltip.
4. **Vitality** — one canonical model (`organismVitalityModel.ts`); REAL uses "Guarded", SIM uses "Live" for engine/session glyph.
5. **Transitions** — mode switch + birth entry use `ModeTransitionVeil`; panel tabs use `panel-tab-transition-active` CSS pulse only.
6. **T0 single glass** — wizard outer wrap **or** step inner panel, never nested `lumina-glass--panel` on both.
7. **Shared organism clock** — CSS `--organism-*` vars and R3F scenes read `organismClockStore` (same elapsed origin).
8. **Distress grammar** — alerts use `distressPanelClass()` + `warnOverlay*Class()` typography; no flat amber/red utility boxes.
9. **HUD hero cap** — max 2 signals in CommandHud; contextual metrics defer to Performance annex hint when session idle.
10. **Status orchestrator** — `resolveDeckStatus()` owns blocking overlay, rail chip, and recovery; no orphan banners.
11. **Fail-closed backend** — `backendHealthStore` defaults `alive=false` until first probe; overlay only when `known && !alive`.
12. **Motion contract** — `visualQuality=low` freezes organism clock; ReasoningSpine/Stage honor `motionReduced`; bloom tier matrix explicit.
