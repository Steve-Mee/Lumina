# Frontend SPA — FROZEN ARCHIVE (T13)

**Status:** Frozen archive (not deleted)  
**Freeze date:** 2026-08-07  
**Parity sign-off:** T12 Tauri tournament naming complete — Command Deck is operator SSOT.

## SSOT

| Surface | Role |
|---------|------|
| `tauri-app/` | **Operator UI SSOT** (Neural Command Deck) |
| `lumina_os/backend/` | REST + WebSocket API |
| `frontend/` | **Legacy Vite monitoring SPA only** — experiments / annex |

Related: [ADR-0016](../docs/adr/0016-streamlit-ui-retirement.md), [README.md](./README.md), [docs/starship-birth.md](../docs/starship-birth.md) § Tauri tournament naming.

## Policy (fail-closed for product work)

1. **No new features** in `frontend/` (Birth, Twin, swarm tournament, REAL ops, etc.).
2. **No dual-maintenance** of operator copy — tournament / EdgeScore / attention strings live in `tauri-app/`.
3. **Allowed:** security patches, dependency CVEs, build break fixes, docs clarifying freeze.
4. **Delete/relocate** of this tree only after explicit operator decision (out of T13 scope).

## Parity checklist (T12 / T13)

- [x] Tournament physics naming SSOT in Tauri (`birthTournamentNaming.ts`)
- [x] Status fetch promotes legacy `swarm_edgescore_*` → `swarm_tournament_*`
- [x] Stage HUD **Tournament lift** field (swarm); stage **EdgeScore** remains composite pass metric
- [x] This freeze archive marker + README lock

## Operator pointer

Production workflows: start backend + Tauri Command Deck  
(see `docs/command-deck-startup-runbook.md` if present, else `tauri-app/README`).
