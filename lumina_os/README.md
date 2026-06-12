# lumina_os

Complete Trader League + LUMINA FastAPI backend. Operator UI is the **Neural Command Deck** (`../tauri-app/`).

## Configuratie (.env)

Maak een `.env` bestand in deze map (bijvoorbeeld op basis van `.env.example`):

- TRADER_LEAGUE_DATABASE_URL: database connectie (standaard sqlite)
- TRADER_LEAGUE_CORS_ORIGINS: komma-gescheiden origins voor frontend toegang

## Structuur

- backend/app.py: FastAPI app met trade ingest, leaderboard en health endpoints
- backend/database.py: SQLAlchemy engine + tabellen (participants, trades)
- backend/models.py: Pydantic request/response modellen
- backend/webhook.py: Webhook endpoint voor externe trade ingest

## Operator UI

Start de **Neural Command Deck** (Tauri) from `../tauri-app/` after the backend is running. Streamlit dashboards were removed (ADR-0016).

## Installeren

Vanuit de map lumina_os:

```bash
pip install -r requirements.txt
```

## Backend starten

```powershell
powershell -ExecutionPolicy Bypass -File .\run_backend.ps1
```

Dit script zet automatisch `PYTHONPATH` naar de repo-root en voorkomt de
`ModuleNotFoundError: No module named 'lumina_core'` valkuil.

Belangrijke endpoints:

- POST /webhook/trade
	- body: `TradeSubmit`
	- response: `{ "status": "ok", "trade_id": <int> }`
- POST /trades
	- alias van `/webhook/trade` (zelfde body/response)
- GET /trades?limit=100&participant=NAME
	- recente trades, optioneel gefilterd op participant
- GET /leaderboard
	- response: `{ "leaderboard": [...], "last_updated": "..." }`
- GET /reconciliation-status
	- runtime status van TradeReconciler (connection, pending closes, errors)
- DELETE /trades
	- verwijdert alle trades
- DELETE /demo-data
	- verwijdert alleen demo data (`DEMO_*` participants + hun trades)

## Command Deck (operator UI)

See [../docs/command-deck-startup-runbook.md](../docs/command-deck-startup-runbook.md). Backend must run on `http://127.0.0.1:8000` before starting Tauri.

Belangrijkste bronnen voor monitoring:

- `state/monitoring_runtime_metrics.json`
- `state/monitoring_daily_pnl.jsonl` (trend uit runtime snapshots)
- `state/monitoring_twin_decisions.jsonl`
- `state/monitoring_gate_rejections.jsonl`
- `state/monitoring_reasoning_latency.jsonl`
- `state/monitoring_model_load_times.jsonl`
- `state/ppo_policy_metadata.json`
- `state/adaptive_intelligence_status.json`
- `state/adaptive_intelligence_events.jsonl`

## Monitoring API (FastAPI)

Router: `lumina_os/backend/monitoring_endpoints.py` (mounted in `backend/app.py`).

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/monitoring/health` | No | Kill-switch, websocket, regime summary |
| `GET /api/monitoring/metrics` | No | Prometheus scrape |
| `GET /api/monitoring/metrics/json` | `X-API-Key` | Full JSON metrics snapshot |
| `GET /api/monitoring/metrics/history` | `X-API-Key` | SQLite metric history |
| `GET /api/monitoring/regime/history` | `X-API-Key` | Regime flip history |
| `GET /api/monitoring/adaptive-intelligence/latest` | `X-API-Key` | Latest adaptive intelligence state + `transition_summary` |
| `GET /api/monitoring/adaptive-intelligence/history` | `X-API-Key` | Recent intelligence transition events |

Example:

```bash
curl http://localhost:8000/api/monitoring/adaptive-intelligence/latest -H "X-API-Key: <key>"
curl "http://localhost:8000/api/monitoring/adaptive-intelligence/history?limit=50" -H "X-API-Key: <key>"
```

## Demo Data Seeden en Verwijderen

Run vanuit de map lumina_os:

```bash
python scripts/seed_demo_data.py
```

Alle demo records worden aangemaakt met participant naam `DEMO_*` en zijn makkelijk op te ruimen:

```bash
python scripts/seed_demo_data.py --clear
```

Of via API:

```bash
curl -X DELETE http://localhost:8000/demo-data
```

## Tests

Run vanuit de map lumina_os:

```bash
pytest -q tests/test_api.py
```

## PowerShell Shortcuts (Windows)

Je kunt alles ook starten via een enkel script:

```powershell
./scripts/dev.ps1 backend
./scripts/dev.ps1 dashboard
./scripts/dev.ps1 seed
./scripts/dev.ps1 clear
./scripts/dev.ps1 test
```

Dit helpt vooral voor demo-data beheer:

- `seed` maakt demo data aan
- `clear` verwijdert alleen demo data (`DEMO_*`)

## API Voorbeelden

### Curl: trade versturen

```bash
curl -X POST http://localhost:8000/webhook/trade \
	-H "Content-Type: application/json" \
	-d '{
		"participant": "LUMINA_BOT",
		"mode": "paper",
		"symbol": "NQ",
		"signal": "long",
		"entry": 18250.0,
		"exit": 18263.0,
		"qty": 1,
		"pnl": 260.0,
		"reflection": {"note": "Breakout continuation"},
		"chart_base64": null
	}'
```

### Curl: leaderboard ophalen

```bash
curl http://localhost:8000/leaderboard
```

### Curl: recente trades ophalen

```bash
curl "http://localhost:8000/trades?limit=20&participant=LUMINA_BOT"
```

### Curl: reconciliation status ophalen

```bash
curl http://localhost:8000/reconciliation-status
```

### PowerShell (Windows): trade versturen

```powershell
$body = @{
	participant = "LUMINA_BOT"
	mode = "paper"
	symbol = "NQ"
	signal = "long"
	entry = 18250.0
	exit = 18263.0
	qty = 1
	pnl = 260.0
	reflection = @{ note = "Breakout continuation" }
	chart_base64 = $null
} | ConvertTo-Json -Depth 5

Invoke-RestMethod -Method Post -Uri "http://localhost:8000/webhook/trade" -ContentType "application/json" -Body $body
```

## Fill Reconciliation Self-Test

Synthetic test:

```bash
python scripts/validation/trade_reconciler_self_test.py
```

Optional live websocket sample (bijv. 20 seconden window):

```bash
python scripts/validation/trade_reconciler_self_test.py --live-window-seconds 20
```

## Audit Log

TradeReconciler schrijft audit events naar:

- `logs/trade_fill_audit.jsonl`

Override via env var:

- `TRADE_RECONCILER_AUDIT_LOG`
