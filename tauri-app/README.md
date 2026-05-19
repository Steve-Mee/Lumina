# LUMINA Neural Command Deck (Tauri)

Native desktop UI for the LUMINA trading organism — **Tauri v2 + React 19 + TypeScript + Vite**.

## LUMINA documentation

- [docs/lumina-core-architecture.md](../docs/lumina-core-architecture.md) — system design, data flow, security
- [docs/lumina-core-api-contracts.md](../docs/lumina-core-api-contracts.md) — REST and WebSocket JSON Schema contracts

## Development

Prerequisites: Node.js 20+, Rust (stable), Python backend on `:8000` (see root [README.md](../README.md)).

```bash
npm install
npm run tauri dev
```

Dev server: `http://localhost:1420`

## First-boot onboarding wizard

On first launch (or when setup is incomplete), the app shows a **Smart Progressive Onboarding Wizard** instead of the Command Deck. The backend computes which steps are required via `GET /api/setup/onboarding`.

**Typical full flow:** Welcome → Smart Setup (Ollama/model) → Credentials → Quick Config → Birth Activate → Command Deck.

**Short path:** When only 1–2 steps remain (e.g. Birth only), Welcome is skipped and the wizard opens on the first pending step.

**Simulate fresh install (dev):**

```powershell
powershell -ExecutionPolicy Bypass -File ..\scripts\reset-onboarding-dev.ps1
cd ..\lumina_os
$env:PYTHONPATH = ".." ; $env:LUMINA_CONFIG = "..\config.yaml"
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
cd ..\tauri-app
npm run tauri dev
```

Styling: **Tailwind CSS v4** + **shadcn/ui** (base-nova, dark mode default via `class="dark"` on `<html>`). Run `npx shadcn@latest add <component>` to add UI primitives.

## Template

Scaffolded with `create-tauri-app` (`react-ts` template). Official Tauri + React + TypeScript starter — customize for the Neural Command Deck cockpit in subsequent phases.
