# LUMINA Neural Command Deck (Tauri)

Native desktop UI for the LUMINA trading organism — **Tauri v2 + React 19 + TypeScript + Vite**.

## LUMINA documentation

- [docs/lumina-core-architecture.md](../docs/lumina-core-architecture.md) — system design, data flow, security
- [docs/lumina-core-api-contracts.md](../docs/lumina-core-api-contracts.md) — REST and WebSocket JSON Schema contracts
- [docs/command-deck-startup-runbook.md](../docs/command-deck-startup-runbook.md) — what happens on cold start and restart
- [docs/requests/tauri-startup-gate-implementation-plan.md](../docs/requests/tauri-startup-gate-implementation-plan.md) — lifecycle gate design

## Development

Prerequisites: Node.js 20+, Rust (stable), Python backend on `:8000` (see root [README.md](../README.md)).

```bash
npm install
npm run tauri dev
```

Dev server: `http://localhost:1420`

## Startup lifecycle (three surfaces)

On every cold start the app shows **exactly one** surface. The backend is the single source of truth via `GET /api/setup/onboarding` → `app_surface`.

| Surface | When | UI |
|---------|------|-----|
| **Setup** | First install, or setup incomplete, or backend unreachable | `OnboardingWizard` (progressive wizard) |
| **Birth** | Setup complete but PPO artifacts missing (`artifacts_ok === false`) | `BirthPhaseScreen` (cinematic monitor) |
| **Deck** | Setup complete **and** birth complete (`artifacts_ok === true`) | `CockpitShell` + Command Deck |

**Fail-closed invariant:** Without valid PPO artifacts (`lumina_agents/ppo/lumina_ppo_policy.zip` + completion flags) the operator never gets an unlocked Command Deck — even on `error`, `interrupted`, or stale client phase.

**Client routing:** `OnboardingGate` switches on `onboardingStore.phase` (`loading | wizard | birth | cockpit`). Phase is derived from `mapAppPhase()` in `src/lib/onboardingPhase.ts`. Defense-in-depth: `useDeckLifecycleGuard` in `CockpitShell` redirects away from the deck if the backend disagrees; `DeckBlockingOverlay` blocks interaction when birth is incomplete.

### Typical first-time flow

Setup wizard: Welcome → Smart Setup (Ollama/model) → Credentials → Quick Config → Birth Activate → cinematic birth → **Enter Command Deck** → Deck welcome overlay.

### Restart behaviour (summary)

| Situation | Surface after restart |
|-----------|------------------------|
| Setup not finished | Setup wizard (resume pending steps) |
| Setup done, birth never started or idle | Birth screen (not wizard) |
| Birth running or interrupted | Birth screen; interrupted sessions may auto-resume from checkpoint |
| Birth complete with artifacts | Command Deck directly (no wizard flash) |

See [command-deck-startup-runbook.md](../docs/command-deck-startup-runbook.md) for the full operator matrix and dev reset commands.

### Dev: simulate states

**Fresh install:**

```powershell
powershell -ExecutionPolicy Bypass -File ..\scripts\reset-onboarding-dev.ps1
```

**Partial birth (restart into birth surface):**

```powershell
powershell -ExecutionPolicy Bypass -File ..\scripts\reset-onboarding-dev.ps1 -PartialBirth
```

Then start backend and Tauri:

```powershell
cd ..\lumina_os
$env:PYTHONPATH = ".." ; $env:LUMINA_CONFIG = "..\config.yaml"
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
cd ..\tauri-app
npm run tauri dev
```

## Styling

**Tailwind CSS v4** + **shadcn/ui** (base-nova, dark mode default via `class="dark"` on `<html>`). Run `npx shadcn@latest add <component>` to add UI primitives.

## Template

Scaffolded with `create-tauri-app` (`react-ts` template). Official Tauri + React + TypeScript starter — customize for the Neural Command Deck cockpit in subsequent phases.
