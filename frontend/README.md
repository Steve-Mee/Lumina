# LUMINA · React monitoring dashboard

Korte start voor de Vite + React + TypeScript SPA (`localhost:5173`). Uitgebreide integratie met de Streamlit launcher staat in **[INTEGRATION.md](./INTEGRATION.md)**.

## Vereisten

- Node.js 20+ · npm 10+

## Eén‑minuut setup

```bash
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. Zorg parallel dat **FastAPI** op **:8000** draait (zie [INTEGRATION.md](./INTEGRATION.md)).

## Authenticatie metrics

`/api/monitoring/metrics/json` vereist `X-API-Key`.

- Kopieer [`.env.example`](./.env.example) naar **`.env.local`**.
- Optie A: **`VITE_LUMINA_API_KEY=...`** (alleen dev) — wordt bij eerste pageload naar `localStorage` `lumina_api_key` gezet als die nog leeg is.
- Optie B: in de browserconsole `localStorage.setItem('lumina_api_key','<jouw-key>')`.

**Operatornaam top-bar**: `VITE_DASHBOARD_OPERATOR` in `.env.local`.

## Build

```bash
npm run build
npm run preview
```

## Proxy (dev)

Standaard: `/api` → `http://localhost:8000`. In Docker: zie `.env.example` → **`VITE_API_PROXY_TARGET`**.

## Optioneel Docker

[Voorbeeld-compose](./docker-compose.dev-example.yml) voor Vite-dev + backend op de host.
