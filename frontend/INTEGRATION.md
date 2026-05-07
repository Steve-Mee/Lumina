# React monitoring dashboard x Lumina launcher

De React cockpit in `frontend/` draait naast de bestaande Streamlit launcher (`lumina_launcher.py`).
Je gebruikt ze parallel:

- **FastAPI backend** op `http://localhost:8000`
- **Streamlit launcher** op `http://localhost:8501` (of jouw ingestelde poort)
- **React dashboard (Vite)** op `http://localhost:5173`

De backend exposeert `GET /api/monitoring/metrics/json` met zowel ruwe observability-data als canonical dashboardvelden in `_lumina_ui` / `lumina_ui`.

## Snelle start (Windows / PowerShell)

### 1) Start backend (`:8000`)

```powershell
cd lumina_os
$env:PYTHONPATH = ".."
$env:LUMINA_CONFIG = "..\config.yaml"
..\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Sanity check:

```powershell
curl http://127.0.0.1:8000/api/monitoring/metrics
```

### 2) Start Streamlit launcher (`:8501`)

Vanaf repo-root:

```powershell
python -m streamlit run .\lumina_launcher.py
```

In de Monitoring-tab staat nu een knop **Open React Dashboard**.
Optioneel kun je de URL overriden met:

```powershell
$env:LUMINA_REACT_DASHBOARD_URL = "http://localhost:5173"
```

### 3) Start React dashboard (`:5173`)

```powershell
cd frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## API key voor metrics/json

`/api/monitoring/metrics/json` vereist `X-API-Key`.

Frontend opties:

- in browser console:
  `localStorage.setItem("lumina_api_key", "<JOUW_API_KEY>")`
- of in `frontend/.env.local`:
  `VITE_LUMINA_API_KEY=<JOUW_API_KEY>`

## CORS en localhost:5173

Backend CORS voegt standaard deze React dev-origins toe:

- `http://localhost:5173`
- `http://127.0.0.1:5173`

Implementatie: `lumina_os/api/monitoring.py` via `extend_cors_origins_with_local_vite_dev(...)`.
Optioneel extra origins:

```powershell
$env:LUMINA_EXTRA_CORS_ORIGINS = "http://localhost:4173,http://devbox:5173"
```

## Payload contract `/api/monitoring/metrics/json`

Response bevat:

- volledige Prometheus snapshot entries
- `_lumina_ui` (canonical velden voor React hook)
- `lumina_ui` (alias, zelfde data)

Canonical velden:

- `trades_completed`
- `ppo_steps`
- `approval_twin_reward`
- `cpu`
- `gpu`
- `ram`
- `velocity`
- `phase`
- `historical_days`
- `synthetic_percent`
- `eta_minutes`

## Troubleshooting

- **401 op `/metrics/json`**: controleer API key in `localStorage` of `.env.local`.
- **CORS-error in browser**: controleer backend draait op juiste config en origin is `localhost:5173`.
- **Lege dashboardwaarden**: controleer `state/first_boot_progress.json`, `state/ppo_policy_metadata.json` en observability collector.
