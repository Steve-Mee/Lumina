# LUMINA · React monitoring dashboard

> **FROZEN ARCHIVE (T13 · 2026-08-07):** Operator UI SSOT is the **Neural Command Deck**
> (`tauri-app/` + `lumina_os/backend/`, [ADR-0016](../docs/adr/0016-streamlit-ui-retirement.md)).
> This Vite SPA is a **legacy monitoring annex only** — **no new features**.
> Parity sign-off: T12 tournament naming in Tauri. Policy and checklist: **[FROZEN.md](./FROZEN.md)**.
> Full tree delete only after explicit operator decision (not part of T13).

Korte start voor de Vite + React + TypeScript SPA (`localhost:5173`). Uitgebreide integratie staat in **[INTEGRATION.md](./INTEGRATION.md)**.

## Vereisten

- Node.js 20+ · npm 10+

## Eén‑minuut setup

```bash
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. Zorg parallel dat **FastAPI** op **:8000** draait (zie [INTEGRATION.md](./INTEGRATION.md)).

## Authenticatie monitoring API

Deze endpoints vereisen `X-API-Key`:

- `/api/monitoring/metrics/json`
- `/api/monitoring/adaptive-intelligence/latest`
- `/api/monitoring/adaptive-intelligence/history`

- Kopieer [`.env.example`](./.env.example) naar **`.env.local`**.
- Optie A: **`VITE_LUMINA_API_KEY=...`** (alleen dev) — wordt bij eerste pageload naar `localStorage` `lumina_api_key` gezet als die nog leeg is.
- Optie B: in de browserconsole `localStorage.setItem('lumina_api_key','<jouw-key>')`.

**Operatornaam top-bar**: `VITE_DASHBOARD_OPERATOR` in `.env.local`.

## Adaptive Intelligence UI

### Badge (top bar)

`IntelligenceTierBadgeLive` pollt `/api/monitoring/adaptive-intelligence/latest` en toont in de launcher-topbar (Birth Phase + Monitoring):

- **Tier** (HIGH / STD / LIGHT) met tier-accent glow
- **Model** (`recommended_model`)
- **Backend** (`Ollama`, `vLLM`, `llama.cpp` via provider-mapping)
- **Status dot**: groen = healthy, geel = degraded/transition, rood = error/probe/fetch-fout

Op Birth Phase valt de badge terug op `adaptive_intelligence` uit `/api/birth/status` wanneer er nog geen persisted monitoring-state is.

### Status card (Monitoring dashboard)

`IntelligenceTierStatusCardLive` staat in de rechterkolom van het Monitoring-dashboard (boven de activity stream) en toont het volledige inference-profiel: model, reasoning mode, context, mode, status/transition en laatste update met handmatige refresh.

### Health mapping

| Dot | Conditie |
|-----|----------|
| Groen | Status OK, geen degrade, geen probe-error |
| Geel | `degraded_state`, actieve tier-transition, of refresh terwijl data al geladen is |
| Rood | Fetch-fout, geen status na load, of `last_probe_error` |

Provider labels: `ollama` → Ollama, `vllm` → vLLM, `llama_cpp` / `llama-cpp` → llama.cpp.

## Build

```bash
npm run build
npm run preview
```

## Proxy (dev)

Standaard: `/api` → `http://localhost:8000`. In Docker: zie `.env.example` → **`VITE_API_PROXY_TARGET`**.

## Optioneel Docker

[Voorbeeld-compose](./docker-compose.dev-example.yml) voor Vite-dev + backend op de host.
