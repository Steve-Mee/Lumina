# TraderLeague Platform Skeleton

Full-stack skeleton for a competitive trading league:

- Backend: FastAPI + PostgreSQL
- Frontend: React + Vite + TypeScript
- Lumina integration: signed webhook on every trade close

## Features Included

- Live participant metrics: PnL, Sharpe, Max Drawdown, Winrate
- Public LUMINA entry endpoint (paper + real account mode)
- Daily/weekly/monthly ranking endpoint
- Trade replay endpoint with chart snapshot URL + reflection text
- Anti-cheat foundation:
  - Signed webhooks (`x-lumina-signature` HMAC SHA256)
  - Only verified brokers accepted
  - Idempotency via unique `broker_fill_id`

## Project Layout

- `backend/app/main.py` FastAPI app
- `backend/app/api/v1/routes/lumina.py` entry + webhook ingestion
- `backend/app/api/v1/routes/rankings.py` live + bucket rankings
- `backend/app/api/v1/routes/replay.py` trade replay API
- `backend/app/models/entities.py` SQLAlchemy data model
- `backend/sql/001_init.sql` core schema
- `backend/sql/002_rankings.sql` ranking function
- `backend/lumina_webhook_example.py` Lumina webhook client snippet
- `frontend/src/pages/Dashboard.tsx` dashboard shell

## Database Schema

Run SQL in order:

1. `backend/sql/001_init.sql`
2. `backend/sql/002_rankings.sql`

## Backend Run

```powershell
cd traderleague/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Initialize Schema + Seed Data

```powershell
cd traderleague/backend
python scripts/init_db.py
python scripts/seed_demo.py
```

## Frontend Run

```powershell
cd traderleague/frontend
npm install
npm run dev
```

## One-Command Local Stack (Docker)

1. Copy env files:

```powershell
cd traderleague
copy backend/.env.example backend/.env
copy frontend/.env.example frontend/.env
```

2. Start stack:

```powershell
docker compose up --build -d
```

3. Initialize schema and demo data:

```powershell
docker compose exec backend python scripts/init_db.py
docker compose exec backend python scripts/seed_demo.py
```

4. Open apps:

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs

Set frontend API base if needed:

- `VITE_API_BASE=http://localhost:8000/api/v1`

## LuminaEngine Integration

When a trade closes, send POST to:

- `/api/v1/lumina/webhooks/trade-close`

Use signed header:

- `x-lumina-signature: sha256=<hmac>`

Example sender is in:

- `backend/lumina_webhook_example.py`

Suggested place in Lumina flow:

- call sender right after trade close + reflection persistence in trade worker.

### Startup Self-Test (Lumina)

Lumina can emit one synthetic trade-close webhook on startup (dev only) to validate signing and endpoint wiring.

Set in Lumina env:

- `TRADERLEAGUE_WEBHOOK_ENABLED=true`
- `TRADERLEAGUE_WEBHOOK_URL=http://localhost:8000/api/v1/lumina/webhooks/trade-close`
- `TRADERLEAGUE_WEBHOOK_SECRET=replace_me`
- `TRADERLEAGUE_PARTICIPANT_HANDLE=lumina_public`
- `TRADERLEAGUE_BROKER_NAME=NinjaTrader`
- `TRADERLEAGUE_BROKER_ACCOUNT_REF=SIM-LUMINA`
- `TRADERLEAGUE_ACCOUNT_MODE=paper`
- `TRADERLEAGUE_WEBHOOK_SELFTEST=true`
- `TRADERLEAGUE_WEBHOOK_SELFTEST_COOLDOWN_SEC=900`
- `TRADERLEAGUE_WEBHOOK_SELFTEST_STATE_FILE=.traderleague_webhook_selftest.json`
- `APP_ENV=dev`

## Public Lumina Entry

Endpoint:

- `POST /api/v1/lumina/entry`

Allows public participant registration when token matches `LUMINA_PUBLIC_ENTRY_TOKEN`.

## Security Notes

- Do not store plaintext broker/API keys.
- Keep webhook secret and entry token only in env/secret manager.
- Expand anti-cheat with broker statement reconciliation and IP allowlisting in production.
