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

Styling: **Tailwind CSS v4** + **shadcn/ui** (base-nova, dark mode default via `class="dark"` on `<html>`). Run `npx shadcn@latest add <component>` to add UI primitives.

## Template

Scaffolded with `create-tauri-app` (`react-ts` template). Official Tauri + React + TypeScript starter — customize for the Neural Command Deck cockpit in subsequent phases.
