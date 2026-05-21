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
3. **Mode tagline** — ModeSwitch subtitle is primary mode copy; PresenceRail icon uses tooltip only (no visible tagline span).
4. **Vitality** — one canonical model (`organismVitalityModel.ts`); REAL uses "Guarded", SIM uses "Live" for engine/session glyph.
5. **Transitions** — mode switch + birth entry use `ModeTransitionVeil`; panel tabs use `panel-tab-transition-active` CSS pulse only.
6. **T0 single glass** — wizard outer wrap **or** step inner panel, never nested `lumina-glass--panel` on both.
7. **Shared organism clock** — CSS `--organism-*` vars and R3F scenes read `organismClockStore` (same elapsed origin).
8. **Distress grammar** — alerts use `distressPanelClass()` + `warnOverlay*Class()` typography; no flat amber/red utility boxes.
9. **HUD organism center** — CommandHud center is `HudOrganismCenter` (envelope pulse), not labeled `HudSignal` tiles. Hero readout defers to PresenceRail on hover/focus or Performance annex on click; max one pulse center in the HUD row.
10. **Status orchestrator** — `resolveDeckStatus()` owns blocking overlay, rail chip, and recovery; no orphan banners.
11. **Fail-closed backend** — `backendHealthStore` defaults `alive=false` until first probe; overlay only when `known && !alive`.
12. **Motion contract** — `visualQuality=low` freezes organism clock; ReasoningSpine/Stage honor `motionReduced`; bloom tier matrix explicit.
13. **Glass stack** — max 2 blurred glass surfaces visible in the default cockpit viewport (HUD + one active deck panel); enforced by `glassStackBudget.test.ts`. StatusBar uses reduced-blur `lumina-glass--hud` (`status-bar--glass`); inactive deck columns use `lumina-surface-muted`.
14. **Decision Theater hero cap** — stage renders max 2 `HudSignal` tiles; overflow lives in debug panel only.
15. **Contextual annex-only** — regime/P&L contextual metrics never occupy HUD secondary slots; Performance annex hint owns them.
16. **Evolution REAL background** — `EvolutionArena` sets `data-mode` + `evolution-arena-shell--real` on mount (no SIM gradient flash).
17. **Immersive frameless** — Living Core and Evolution arena tab content render without `--panel` wrapper in default viewport.
18. **3D scene identity** — Birth helix and Living Core must not import each other's scene components; shared code lives in `helixPrimitives.tsx`.
19. **Sync copy** — mode sync uses ModeSwitch dot + deduped toast only; PresenceRail secondary never shows sync text.
20. **REAL ambient mute** — in REAL mode, cockpit grid opacity `0.08`, mesh `::before 0.06`, stars `0.18`; SIM keeps stars + vignette at full posture.
21. **Evolution directed tableau** — arena camera locked (`enableZoom={false}`, no rotate); node detail via click dialog only (no in-viewport hover tooltips).
22. **HUD glow budget** — organism center pulse is primary HUD glow; shell halo demoted when `.hud-organism-center` is present (`:has(.hud-organism-center)::after`).
23. **Birth T1 activate deck** — launch control only in default viewport; genesis parameters (max days, advanced flags) collapsed or T0 — max one visible slider in default state.
24. **Living Core breath** — single organism breath via shared clock; CSS halo follows `--organism-envelope`, no independent pulse keyframes on `.living-core-halo--*`.
