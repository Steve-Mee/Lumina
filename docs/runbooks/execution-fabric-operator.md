# Execution Fabric — Operator Runbook (PR-D Safety MVP)

**Audience:** operators running SIM/Paper with LUMINA Execution Fabric  
**ADR:** [0035-execution-fabric-grpc.md](../adr/0035-execution-fabric-grpc.md)

## Components

| Component | Default |
|-----------|---------|
| Fabric gRPC | `127.0.0.1:50051` |
| Auth | `LUMINA_FABRIC_TOKEN` (shared Brain + Fabric) |
| Audit log | `%APPDATA%\LUMINA\fabric-audit.jsonl` |
| Config | `%APPDATA%\LUMINA\fabric.json` |

> **Code Red — NinjaTrader must stay up:** soft setup never kills NT; only Repair may. Full write-up: [ninjatrader-process-stability-code-red.md](./ninjatrader-process-stability-code-red.md).

## After install — Zero-IT Fabric (non-technical users)

1. Install **NinjaTrader 8** if missing (Lumina offers the official download).
2. Open Lumina → **Credentials / Setup** (Fabric tab).
3. Lumina **auto-heals** on first open when NT is installed:
   - token + `fabric.json`
   - deploys `Lumina.Fabric.NtBridge` + source AddOn to the real My Documents Custom folder
   - closes NinjaTrader if files are locked, rebuilds integration when possible
   - restarts NT, waits for the bridge, runs dual-plane diagnostic
4. Connection must be **GREEN** (orders **and** historical bars) before Genesis.
5. If RED/AMBER: click **Repair NinjaTrader connection** (same pipeline — no manual file renames).
6. CrossTrade is **optional emergency fallback only**.

APIs:
- `POST /api/setup/fabric-bootstrap` — token + deploy (light)
- `POST /api/setup/fabric-heal` — **full repair** (close NT, redeploy, launch, test)
- `POST /api/setup/fabric-connection-test` — diagnostic only (GREEN certificate)
- `GET /api/setup/fabric-link-status`
- `POST /api/setup/fabric-nt-watch` — NT binary change → re-probe; failure sets halt + **needs_repair**

On NinjaTrader update/reinstall: open Setup and click **Repair NinjaTrader connection** (or let auto-heal run after halt). Do **not** ask users to rename `.dll.new` files.

## Dual-plane health (Execution + Market Data) — mandatory

GREEN means **both** planes are proven. Execution-only green lights are **invalid**.

| Plane | What is checked | Host required |
|-------|-----------------|---------------|
| **Execution** | token, port, auth, place, flatten, SAFE_MODE | SimHost **or** NT8 AddOn |
| **Market data** | `historical_bars` via Fabric `RequestHistoricalData` (≥10 real bars) | **NT8 AddOn only** (native BarsRequest) |

Critical check IDs include `historical_bars`. Failures:

| Code | Meaning | Fix |
|------|---------|-----|
| `HOST_NO_NT_DATA` | SimHost / null provider — no NT data feed | Stop SimHost; start NT8 AddOn on `:50051` |
| `NO_BARS` / `NT_BARS_ERROR` | NT returned empty / error | Connect Continuum/Kinetick; fix instrument |
| `INSTRUMENT_NOT_FOUND` | Symbol not in NT | Use NT format e.g. `MES 09-26` or config `MES SEP26` |
| `HISTORICAL_TIMEOUT` | BarsRequest hung | Data provider disconnected / NT busy |

**SimHost is execution-only.** It will keep place/flatten GREEN but must leave **historical_bars RED**. That is correct fail-closed behaviour — never treat SimHost as “native coupling OK”.

NinjaScript Output must show:

```
[FabricHost] Host started successfully … historical=nt
[FabricData] hist … code=ok bars=…
```

When `broker.live_provider=ninjatrader`, Brain historical load uses Fabric only (no CrossTrade). `CROSSTRADE_TOKEN` may be empty.

## First-time token (customers)

Use **Generate** for `LUMINA_FABRIC_TOKEN` on the Lumina first-boot **Connection Credentials** step.
That writes:

| Target | Content |
|--------|---------|
| Workspace `.env` | `LUMINA_FABRIC_TOKEN=…` (Brain / Python) |
| Windows **User** env | same value (NinjaTrader reads after **restart**) |
| `%APPDATA%\LUMINA\fabric.json` | host defaults only — **no secret value** |

Headless / operator install:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install_fabric_token.ps1
```

**Single host rule:** only one process may bind `127.0.0.1:50051` (SimHost **or** NT8 AddOn, never both).

## NinjaScript Output empty? / diagnostic `HOST_NO_NT_DATA`

### No “Lumina” under New
Background AddOn only — **no** separate window. Success = NinjaScript Output + file log + green `historical_bars`.

### Two hosts, one port
| Host | Process | Historical |
|------|---------|------------|
| **SimHost** | `Lumina.Execution.Fabric.SimHost.exe` | `HOST_NO_NT_DATA` (execution-only) |
| **NT AddOn** | inside `NinjaTrader.exe` | real bars via BarsRequest |

Diagnostics used to **auto-start SimHost**, which stole `:50051` from the AddOn. Fixed: when NinjaTrader is running, SimHost is killed and is **not** auto-started.

### Live tree (OneDrive)
| Wrong (stale) | Right (live) |
|---------------|--------------|
| `…\Documents\NinjaTrader 8\` | **`…\OneDrive\Documenten\NinjaTrader 8\`** |

DLL load in log ≠ AddOn Active. Deploy **both**:

| File | Role |
|------|------|
| `bin\Custom\Lumina.Fabric.NtBridge.dll` | Product bridge: `FabricNtHost` + `NtAccountOrderGateway` + hist/live (≥40 KB + type markers) |
| `bin\Custom\AddOns\@LuminaFabricHost.cs` | Source AddOn entry + **New → LUMINA** status window |
| `%APPDATA%\LUMINA\fabric-deploy-manifest.json` | Last deploy hash/size (operator timeline) |

**Stub NtBridge (~12 KB) is a hard fail** — heal/deploy must refuse or quarantine it.

### Zero-IT install (preferred for end users)

**Do not ask users to open NinjaScript Editor / F5.** Lumina **Repair connection** (`POST /api/setup/fabric-heal`):

1. Closes NinjaTrader if needed  
2. Deploys bridge DLLs + `@LuminaFabricHost.cs`  
3. Injects source into `NinjaTrader.Custom.csproj`  
4. **Sanitizes csproj** — never compile `obj\**\*.resources.cs` / AssemblyAttributes into the main assembly (CS0579)  
5. Runs `dotnet build` on Custom (x64, no satellite resource sources left for NT F5)  
6. Scrubs `obj` pollution + re-sanitizes csproj  
7. Relaunches NT, waits for host, dual-plane diagnostic  

Dev-only fallback if heal cannot build: NinjaScript Editor → Compile (F5).

#### If NinjaScript shows CS0579 (duplicate Assembly* attributes)

Cause: satellite `obj\...\NinjaTrader.Custom.resources.cs` (or AssemblyAttributes) were listed under `<Compile Include="obj\...">` next to root `AssemblyInfo.cs`.

Fix (automated by heal):

```powershell
python scripts/_verify_nt_custom_heal.py
# or Lumina → Repair NinjaTrader connection
```

Manual: remove every `<Compile Include="obj\..."/>` from `NinjaTrader.Custom.csproj`, ensure `<Compile Remove="obj\**" />`, delete `obj\**\*.resources.cs`.

### See Lumina in NinjaTrader (LUMINA Link)

CrossTrade shows presence under **New → CrossTrade**. Lumina does the same:

**Control Center → New → LUMINA** opens **LUMINA Link** (status-only).

| Color | Meaning |
|-------|---------|
| **GREEN** | Bridge running + Lumina Brain session authenticated + not SAFE |
| **AMBER** | Bridge healthy, waiting for Lumina app (or SAFE mode) |
| **RESTARTING** | Clean host recycle &lt; ~8s — wait; do not Repair yet |
| **RED** | Host not running / token / port conflict — use Lumina Repair |

### Live vs Proof (SSOT — never dual-lie)

| Signal | Source | Means |
|--------|--------|--------|
| **Live level** (Link + Vault primary color) | Host status + port + Brain session / supervisor | Real-time bridge health |
| **Proof / Certified** | Dual-plane diagnostic certificate (≤2h birth, ≤30m badge) | “Orders + historical bars worked” |
| **gate_birth_ok** | Host up **and** recent proof | Birth / Genesis activate |

**Operator Vault must not show primary GREEN from paper certificate alone.**  
If LUMINA Link is RED “Host stopped” while Vault says GREEN → bug (fixed: Vault polls `GET /api/setup/fabric-link-status` live SSOT).

API: `GET /api/setup/fabric-link-status` returns `level`, `meaning`, `green` (live only), `host_ready`, `gate_birth_ok`, `proof`.

No order buttons, no token paste — capital controls stay in the Lumina app. Host still runs with the window closed.

**Do not** keep a stale small `LuminaNt8AddOn.dll` (~17KB) in Custom — CLR will bind that identity forever and `FabricNtHost` will appear “missing”. Deploy quarantines it as `LuminaNt8AddOn.dll.STALE_DISABLE`.

```powershell
# Preferred: Lumina app → Setup → Repair NinjaTrader connection
# Dev manual path:
# 1) Fully EXIT NinjaTrader
powershell -ExecutionPolicy Bypass -File scripts\deploy_fabric_nt8.ps1
# 2) Start NT → trust new DLL if prompted
# 3) (dev only if heal skipped) New → NinjaScript Editor → Compile (F5)
# 4) New → LUMINA  → expect AMBER “Bridge ready…” (or GREEN if Lumina Brain connected)
# 5) Lumina → Run fabric diagnostic → historical_bars GREEN + Link window GREEN
```

If Output shows `FabricNtHost type missing`:

1. Confirm `Lumina.Fabric.NtBridge.dll` exists under `OneDrive\Documenten\NinjaTrader 8\bin\Custom\`
2. Delete/quarantine any `LuminaNt8AddOn.dll` without NtBridge
3. Full NT restart + Compile F5
4. Check `%APPDATA%\LUMINA\fabric-nt-host.log` for `Loading bridge DLL: ...NtBridge...`

Proof files:

- `%APPDATA%\LUMINA\fabric-nt-host.log`
- `%APPDATA%\LUMINA\fabric-nt-host.json` → `"state":"running","historical":"nt"`

## Start SIM host (no NinjaTrader)

```powershell
$env:LUMINA_FABRIC_TOKEN = "<secret>"   # or rely on User env after install_fabric_token.ps1
dotnet run --project integrations/ninjatrader8/Lumina.Execution.Fabric.SimHost -c Release -- --port 50051 --account Sim101
```

## Safety modes

| Mode | Behaviour |
|------|-----------|
| **NORMAL** | Accept place/modify |
| **SAFE_MODE** | Reject new place/modify; cancel/flatten allowed; non-protected cancelled on disconnect/timeout |
| **FULL_SAFE** | Operator/manual only; emergency flatten requires `emergency=true` |

### SIM learning envelope (intentional)

On **Sim101**, capital preservation is **not** the learning bottleneck: the organism may explore. Fabric still enforces:

- localhost bind + shared token
- `MaxPositionSize` / rate limits (config)
- SAFE_MODE + cancel-on-disconnect
- **empty-book flatten skip** for diagnostic thrash (no wipe when no positions/orders)
- REAL / non-Sim account place remains fail-closed pending promotion ADR

`DailyLossLimit` default `0` = disabled on SIM (optional operator set in `fabric.json`).

### Entering SAFE_MODE

- Brain heartbeat timeout (default **5s**)
- Brain TradingStream closed (last session)
- Explicit safety policy

### Clearing SAFE_MODE

- Successful Brain re-auth clears **SAFE → NORMAL** (not FULL_SAFE)
- FULL_SAFE requires operator intervention / process restart (Phase 1)

## Disconnect matrix (operator view)

1. **Heartbeat timeout** → cancel non-protected → SAFE_MODE → after `FlattenGraceMs` emergency flatten (if enabled)
2. **Stream disconnect** → same cancel policy when no sessions remain
3. **Reconnect** → Auth + **StateSync** snapshot; Brain reconciles `state_hash`

## Protected orders

Orders with `protected=true` are **not** auto-cancelled on disconnect/timeout. Review audit log if long disconnects leave protected working orders.

## Audit log

Append-only JSONL lines: `host_start`, `auth_ok`, `place_order`, `order_event`, `disconnect_policy`, `safety_alert`, …

```powershell
Get-Content $env:APPDATA\LUMINA\fabric-audit.jsonl -Tail 50
```

## Troubleshooting

| Symptom | Check |
|---------|--------|
| Auth fails | Token match on Brain env and Fabric host |
| Place rejected SAFE_MODE | Re-auth Brain; inspect audit for disconnect/timeout |
| Degraded on bridge | `get_safety_alerts()` / logs; reconnect Fabric client |
| Port in use | Change `--port` and `broker.ninjatrader.fabric.port` |

## Metrics (PR-E)

### Server (C# host)

On host stop, a `metrics_snapshot` line is written to the audit log. Counters include:

- `fabric_place_orders_total` / `fabric_place_rejected_total` / `fabric_place_filled_total`
- `fabric_safe_mode_entries_total` / `fabric_auth_ok_total`
- `fabric_place_latency_ms_p50|p95|p99`

### Brain (Python)

`NinjaTraderBridgeService.metrics.snapshot()` and `/ws/core/live` → `ninjatrader.metrics`:

- `fabric_client_place_*`, `fabric_client_rtt_ms_p50|p95|p99`, connect/disconnect/alerts

Command Deck **NT8** pill shows connected / SAFE / degraded and tooltip with `safe_mode` + fabric target.

## Gateway mode

Recommended `fabric.json` (created by onboarding / `install_fabric_token.ps1`):

```json
{
  "BindHost": "127.0.0.1",
  "BindPort": 50051,
  "AuthTokenEnv": "LUMINA_FABRIC_TOKEN",
  "AccountName": "Sim101",
  "GatewayMode": "sim",
  "HeartbeatTimeoutMs": 5000,
  "FlattenGraceMs": 15000,
  "FlattenOnTimeout": true,
  "BindLocalhostOnly": true,
  "MaxPositionSize": 2,
  "MaxOrdersPerMinute": 30,
  "DailyLossLimit": 0
}
```

- **sim** — in-memory SIM fills (default, paper validation; use even inside NT until NT gateway is bound)
- **nt** (product default) — `NtAccountOrderGateway` bound to **Sim101** (or configured account); real place/cancel/fills on NT SIM
- **memory** — in-process `SimOrderGateway` only (SimHost / CI); no exchange

## Brain config (concept)

```yaml
broker:
  backend: live
  live_provider: ninjatrader
  ninjatrader:
    enabled: true
    account_name: Sim101
    fabric:
      host: 127.0.0.1
      port: 50051
      auth_token_env: LUMINA_FABRIC_TOKEN
      gateway_mode: sim
```

Plus process/User env: `LUMINA_FABRIC_TOKEN`.

## REAL mode

**Not enabled in PR-E.** REAL requires a separate promotion ADR + bound NT gateway + human approval.
