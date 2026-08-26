---

# NinjaTrader process stability (Code Red)

**Date:** 2026-08-09  
**Audience:** operators + engineers  
**Related:** execution-fabric-operator.md, fabric_heal, Credentials soft setup


**Operator clarification (authoritative):** het proces dat stopt is **NinjaTrader.exe**, niet de Lumina UI. Zonder stabiele NT-sessie is de native Fabric-koppeling dood; dit is **P0 / Code Red**.

## Diagnose (evidence-based)

### Oorzaak A — Lumina force-kill (historisch, nu dicht)

| Item | Detail |
|------|--------|
| Pad | `CredentialsStep` mount: als `fabricCertified===false` → `runFabricRepair` → `taskkill /IM NinjaTrader.exe` |
| Waarom loop | `fabricCertified` start altijd `useState(false)` → **elke** Lumina-open killt NT → relaunch → opnieuw inloggen |
| Bewijs | Code + operator “login → alles weg → opnieuw login” |
| Status | **Opgelost in code** |

**Huidige regels (na fix):**

- Mount: bootstrap + **soft** setup = **alleen diagnostic** (geen taskkill).
- Halt (NT-update): **toast only** — geen auto-Repair.
- `POST /api/setup/fabric-heal` default `close_ninjatrader=false`.
- Python `run_fabric_heal(close_nt=False)` default.
- Enige `close_ninjatrader: true`: knop **Repair NinjaTrader connection** (`credentialsFabricActions.ts`).
- Elke Python-close: `%APPDATA%/LUMINA/nt-lifecycle.log` (`nt_lifecycle.py`).
- Guard-test: `tests/launcher/test_no_auto_nt_kill.py`.

**Bewijs dat latere exits geen Lumina-kill waren:** na toevoegen lifecycle-log bestond **geen** `nt-lifecycle.log` terwijl NT al weer weg was → geen gelogde taskkill.

### Oorzaak B — Echte NT process crash (vendor)

| Item | Detail |
|------|--------|
| Tijd | 2026-08-09 10:07:05 (Windows Application Event) |
| Exception | `System.NullReferenceException` |
| Stack | `NinjaTrader.Tradovate.Adapter.ReceiveWebSocketMarketDataMessage` |
| Code | `0xe0434352` (CLR unhandled → process exit) |
| Conclusie | **NinjaTrader/Tradovate-eigen pad**, geen Lumina managed stack in faulting module |

Stressoren die zulke vendor-bugs vaker raken: datafeed nog **Connecting** + zware BarsRequest/history storms; meerdere vendor AddOns; dual bridge DLL load.

### Oorzaak C — Dual bridge assembly thrash

NT vendor log laadde **beide**:

- `Lumina.Fabric.NtBridge` 1.4.0  
- `LuminaNt8AddOn` 1.4.0 (zelfde build, tweede naam)

**Oplossing:**

- Deploy **alleen** `Lumina.Fabric.NtBridge.dll` (geen actieve alias).
- Live quarantine: `LuminaNt8AddOn.dll.DUAL_DISABLE`.
- `fabric_bootstrap.py` + `scripts/deploy_fabric_nt8.ps1`: dual alias verboden; bij NT running alleen `*.dll.new`.

### Oorzaak D — Mid-session DLL overwrite

Overwrite van geladen Custom-DLL’s terwijl NT draait → kan crash/exit geven.

**Oplossing:** NT running → stage `.new`; promote alleen als `is_ninjatrader_running()==false` (heal + deploy script).

### Secundair — Birth “interrupted” / CROSSTRADE_TOKEN

Residual `state/lumina_birth_progress.json` (`loading_history_failed`) + preflight lege hist wanneer Fabric down (connection refused).

**Oplossing:** Fabric-only remediatie; residual demote; short retry; geen cloud-token-eis bij `live_provider=ninjatrader`.

## Elon-regels (SSOT)

1. Nooit `taskkill` behalve **expliciete Repair**.  
2. Nooit dual bridge DLL.  
3. Nooit in-place DLL overwrite / Custom rebuild op auto-pad terwijl NT draait.  
4. Nooit restart-loop als NT dood is — alleen alert + handmatige Launch.  
5. Historical pas na datafeed **Connected** (settle gate).  
6. Elke close → `nt-lifecycle.log` (stack + reason).  
7. **Nooit dual-truth GREEN** — Operator Vault primary color = live host level; paper cert is **proof only** (see [ADR-0039](../adr/0039-fabric-link-health-ssot.md) + execution-fabric-operator Live vs Proof).

## Geïmplementeerde oplossing (code map)

| Component | Wijziging |
|-----------|-----------|
| `CredentialsStep.tsx` | Mount: soft diagnostic; geen auto-Repair |
| `credentialsFabricActions.ts` | Soft = diagnostic only; Repair = close true + toast |
| `setupClient.ts` / `setup_endpoints_fabric.py` | heal default close **false** |
| `fabric_heal.py` | close_nt default false; lifecycle log; promote alleen NT down |
| `nt_lifecycle.py` | append-only close audit |
| `fabric_bootstrap.py` | NtBridge only; quarantine dual; stage if NT running |
| `scripts/deploy_fabric_nt8.ps1` | zelfde Code Red-regels |
| `NtHistoricalDataProvider.cs` | `WaitForMarketDataReady` vóór BarsRequest |
| `birth_runner_preflight.py` | Fabric messaging + residual demote + short retry |
| Tests | `test_no_auto_nt_kill.py`, heal, preflight messaging |

## Operator triage (als NT weer weg is)

1. Noteer **exacte tijd**.  
2. `%APPDATA%\LUMINA\nt-lifecycle.log`  
   - **`close_begin`** → Lumina/Repair-kill (stack in log).  
   - **Geen bestand / geen regel** → geen gelogde Lumina-kill → crash of handmatige/OS exit.  
3. Event Viewer → Application → NinjaTrader / .NET Runtime.  
4. NT log: `…\NinjaTrader 8\log\log.YYYYMMDD.*` Session Break + laatste regels.  
5. Custom: alleen `Lumina.Fabric.NtBridge.dll` actief (geen `LuminaNt8AddOn.dll` zonder DUAL_DISABLE).

## Definition of Done

| # | Criterium |
|---|-----------|
| 1 | ≥60 minzelfde NT PID met Lumina open, geen ongevraagde Session Break door Lumina |
| 2 | Geen `close_begin` behalve bewuste Repair |
| 3 | NT vendor log: **één** Lumina bridge assembly |
| 4 | Birth residual: geen valse cloud-token-eis bij ninjatrader |
| 5 | Guard tests groen |

## Status implementatie

**Code Red-paden (A, C, D) + birth messaging: geïmplementeerd en getest (guard/heal/preflight).**  
**Operator live PID-sessie (DoD #1)** blijft de smoke-test na deploy.

