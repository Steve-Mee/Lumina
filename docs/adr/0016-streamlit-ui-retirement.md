# ADR-0016: Streamlit UI retirement

**Status**: Accepted

**Date**: 2026-06-12

## Context

LUMINA migrated operator UI from Streamlit (`streamlit_launcher.py`, `lumina_launcher/ui/*`, `lumina_os/frontend/*`) to the **Neural Command Deck** (Tauri + React). Streamlit duplicated lifecycle, birth, monitoring, and config flows already exposed via FastAPI and implemented in `tauri-app/`.

Maintaining two UIs increased divergence risk (see ADR-0011) and polluted the dependency tree (`streamlit==1.56.0`, ~25 Python modules).

## Decision

Remove all Streamlit UI code and dependencies. The sole operator surface is:

1. **Tauri Command Deck** (`tauri-app/`) — desktop UI
2. **FastAPI backend** (`lumina_os/backend/`) — REST + WebSocket SSOT
3. **`lumina_launcher` domain services** (`core/`, `services/`) — shared logic (not UI)

Headless helpers previously embedded in Streamlit views move to `lumina_os/monitoring/` and `lumina_core/evolution/evolution_metrics_loaders.py`.

Bootstrap and `python -m lumina_launcher` no longer start Streamlit; they point operators to backend + Tauri.

## Consequences

- Positief:
  - Single UI truth; no Streamlit/Tauri lifecycle divergence.
  - Smaller install footprint and CI surface.
  - Cleaner codebase; domain logic in testable headless modules.
- Negatief:
  - Operators must use Tauri (Node.js + Rust toolchain required for dev).
  - Embedded React SPA at `GET /ui/` remains optional annex (not Streamlit).
- Risico's:
  - Regression in birth/setup flows — mitigated by parity registry, pytest, and Tauri vitest.

## Alternatives Considered

- **Keep Streamlit as fallback** — rejected: continued dual-maintenance and ADR-0011 bypass risk.
- **Sync Streamlit to `resolve_app_surface()`** — rejected: investment in dead UI; Tauri already SSOT consumer.

## Related ADRs

- ADR-0011: Tauri lifecycle gate SSOT

## Freeze archive (T13 · 2026-08-07)

The optional Vite SPA at `frontend/` is a **frozen archive** after Tauri tournament-naming parity (T12):

- Marker: [`frontend/FROZEN.md`](../../frontend/FROZEN.md)
- Policy: no new operator features; security/build fixes only
- Delete of `frontend/` remains an explicit future decision (not automated)

## References

- [launcher_feature_parity_registry.md](../launcher_feature_parity_registry.md)
- [command-deck-startup-runbook.md](../command-deck-startup-runbook.md)
- [starship-birth.md](../starship-birth.md) § Tauri tournament naming (T12)
