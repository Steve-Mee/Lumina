# React monitoring dashboard × Lumina launcher

Het Vite-dashboard in `frontend/` is een **losstaande SPA** naast de bestaande **Streamlit launcher** (`lumina_launcher.py`). De launcher-tab **„Monitoring Dashboard“** blijft de Python/Streamlit-versie gebruiken (`lumina_os/frontend/monitoring_dashboard.py`). De React-app is de nieuwe cockpit op **poort 5173**.

## Architectuur

| Onderdeel | URL / entry | Rol |
|-----------|-------------|-----|
| React dashboard | `http://localhost:5173` | Vite SPA, proxy `/api` → backend |
| FastAPI (Trader League backend) | Standaard `http://localhost:8000` | Metrics + `_lumina_ui` blok (`/api/monitoring/metrics/json`) |
| Streamlit launcher | meestal `http://localhost:8501` (of jouw preset) | `lumina_launcher.py` inclusief Monitoring-tab |

Je draait dus **parallel**: backend (:8000) + optioneel launcher (:8501) + **React** (:5173).

## Vereisten kort

- **Node.js 20+**, **npm**.
- **`lumina_os` backend actief op :8000** (of pas proxy aan, zie onder).
- Geldige **API key** in `config.yaml` onder `security.api_keys` voor `X-API-Key`; de frontend gebruikt **`localStorage` key `lumina_api_key`** of `VITE_LUMINA_API_KEY` in `.env.local` voor dev-bootstrap (zie [README](./README.md)).
- **CORS**: `lumina_os` voegt `http://localhost:5173` toe (zie `lumina_os/api/monitoring.py` + `config.yaml`).

---

## Stap 1 — Backend starten (:8000)

Vanaf repo-root (dit project gebruikt ook `lumina_core` op `PYTHONPATH`):

### PowerShell

```powershell
cd lumina_os
$env:PYTHONPATH = ".."
$env:LUMINA_CONFIG = "..\config.yaml"
..\.venv\Scripts\python.exe -m uvicorn backend.app:app --reload --host 127.0.0.1 --port 8000
```

Of gebruik [`lumina_os/scripts/dev.ps1`](../lumina_os/scripts/dev.ps1) met `-Action backend` (zet `PYTHONPATH` en port al).

Controle:

```powershell
curl http://127.0.0.1:8000/api/monitoring/metrics
```

(Optioneel authenticated JSON: kopieer `X-API-Key` naar de frontend.)

---

## Stap 2 — Streamlit launcher (bestaande flow)

Niets aan de React-app verbindt automatisch naar de launcher. Zoals elders:

```powershell
# vanaf repo-root, met geactiveerde venv
python -m streamlit run .\lumina_launcher.py
```

Monitoring-tab (`render_monitoring_dashboard_tab`) praat tegen `BACKEND_BASE_URL` (= `LUMINA_BACKEND_URL` env of default `http://localhost:8000`), **los** van de SPA.

---

## Stap 3 — React dashboard (:5173)

```bash
cd frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. De Vite-proxy stuurt browser-requests naar **`/api/...`** door naar **`VITE_API_PROXY_TARGET`** (default `http://localhost:8000`).

---

## Stap 4 — Optioneel launcher-integratie (link in Streamlit)

Je kunt in de launcher-tab voor operators een harde link tonen naar de SPA (pas tab **„Monitoring Dashboard“** aan als je dat wilt coden):

```python
import streamlit as st

st.markdown("### React monitoring cockpit (Vite)")
st.link_button("Open in browser", "http://localhost:5173", help="Draai tegelijk: npm run dev in frontend/")
st.caption("Zorg dat uvicorn op :8000 draait en dat `lumina_api_key` gezet is in de browser voor metrics/json.")
```

**Let op**: Streamlit blokkeert geen SPA; twee tabbladen in de browser (launcher + localhost:5173) is de meest voorspelbare workflow.

---

## Backend & contract

- **Endpoint**: `GET /api/monitoring/metrics/json` + header `X-API-Key`.
- **Payload**: volledige observability-snapshot **plus** plat blok **`_lumina_ui`** met o.a. `trades_completed`, `ppo_steps`, `phase`, … (zie `lumina_os/api/monitoring.py`).
- **Andere host/poort backend**: zet `VITE_API_PROXY_TARGET` in `frontend/.env.local` (dev) of pas `vite.config.ts` proxy aan.

---

## Docker (optioneel)

Zie **[`docker-compose.dev-example.yml`](./docker-compose.dev-example.yml)** voor een minimaal voorbeeld: Vite in een Node-container met proxy naar de API op de host (`host.docker.internal`). Start (naast draaiende backend op de host):

```bash
cd frontend
docker compose -f docker-compose.dev-example.yml --profile vite up vite-dev
```

---

## Troubleshooting

| Symptoom | Actie |
|----------|--------|
| 401 op metrics/json | Zet API key: `localStorage.setItem('lumina_api_key','…')` of `VITE_LUMINA_API_KEY` in `.env.local` + herlaad. |
| CORS-fout | Controleer dat backend draait met uitgebreide origins (5173) en dat je geen verkeerde URL gebruikt. |
| Lege metrics | Controleer `state/first_boot_progress.json` en Prometheus; `_lumina_ui` vult aan vanuit bestanden + metrics. |
| Proxy faalt in Docker | Zet `VITE_API_PROXY_TARGET=http://host.docker.internal:8000` in env voor de Vite-service. |
