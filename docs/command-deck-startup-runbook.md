# Command Deck — Startup & Restart Runbook

**Date:** 2026-08-09  
**Audience:** Operators and support  
**Scope:** LUMINA Neural Command Deck (Tauri) cold start and app restart  
**SSOT:** `GET /api/setup/onboarding` → `app_surface` / `app_surface_reason`  
**Implementation:** [tauri-startup-gate-implementation-plan.md](requests/tauri-startup-gate-implementation-plan.md) · ADR-0011  
**Cold-start UI:** `StartupReadinessScreen` (named steps) while phase is `loading`

---

## One-line summary

**Setup once → sign Genesis Maturity Charter → train Birth until Foundation five-of-five + fitness (`birth_exit_ok`) → land on Phase Hub → open Command Deck when you choose → REAL only when ladder complete.**

### Birth activate flow (one intent, one screen)

| Operator mode | When | What you see |
|---------------|------|--------------|
| **IDLE** | Clean session | Neural Genesis charter → **Activate Birth** |
| **DECISION** | Previous birth stopped / checkpoint / residual fail | One choice: **Continue** (if checkpoint) or **Start clean** — not Activate + dual wipe thrash |
| **LAUNCHING** | After Activate / Continue | Numbered steps: Fabric → Twin → History → Engine (no wipe UI) |
| **TRAINING** | Engine live or cold-start pin | Birth mission control |

Fail closed: activation failure returns to Genesis/Decision with one error banner — never an empty orphan screen or Recovery-tab flash mid-launch.

---

## Maturation ladder (Genesis → REAL)

| Phase | Operator action | Blocks REAL? |
|-------|-----------------|--------------|
| **Genesis** | Set training trades, data policy on Neural Genesis deck; ACTIVATE BIRTH. Pass is process-R + occupancy, not a WR 35–45% slider. | No |
| **Birth** | Historical curriculum runs (BRO-v1) | No |
| **Awakening** | Evolution Proof (ADR-0026) after Foundation exit | Yes |
| **Playground** | NT sim orders; first sim order milestone | No |
| **Apprenticeship** | `sim_real_guard` + 5-day SIM stability (`READY_FOR_REAL`) | Yes |
| **Proving Ground** | Shadow validation + PromotionGate pass | Yes |
| **REAL** | Command Deck REAL toggle after `POST /api/maturity/approve-real` | — |

Progress SSOT: `state/lumina_maturity_progress.json` · API: `GET /api/maturity/progress`

The Command Deck **Maturity strip** shows current phase and blocking reasons. SIM Readiness (Evolution tab) shows stability criteria; use the deck REAL toggle — not the deprecated standalone go-live button.

---

## Four surfaces (cold-start SSOT)

| # | Surface (`app_surface`) | Client phase | What you see |
|---|-------------------------|--------------|--------------|
| 1 | `setup` | `wizard` | Onboarding wizard (install / incomplete setup) |
| 2 | `birth` | `birth` | Birth Phase mission control (train / recover) |
| 3 | `hub` | `hub` | **Phase Hub** — post-birth home (checkpoint, next steps) |
| 4 | `deck` | `cockpit` | Command Deck — **session entry from hub**, not cold-start default |

The backend function `resolve_app_surface()` in `lumina_launcher/core/onboarding.py` decides the surface. After birth is ready it returns **`hub`** (`maturation_hub`). The desktop app maps that via `mapAppPhase()` and does **not** guess from localStorage.

### Cold-start readiness cover (Systems Go)

**Product rule:** *One screen waits. Then the app is usable.*  
No half-loaded Genesis, no 30s charter lock, no surprise “Fabric still loading” in Setup.

On every process start, **one** full-screen `StartupReadinessScreen` (“Systems Go”) runs until **all** of the following complete (or the operator chooses degraded mode):

1. **Backend** — control plane reachable (`GET /api/setup/onboarding`)
2. **NinjaTrader process** — `NinjaTrader.exe` running (dialog: **Start NinjaTrader** or **Continue without link**)
3. **Fabric link** — soft bootstrap + status/light diagnostic until **GREEN** (or degraded continue)
4. **Birth session** (when `app_surface=birth`) — status poll + hydrate **on the cover** (not after landing on Genesis)
5. **Open surface** — only then map to setup / birth / hub

| Operator choice | Result |
|-----------------|--------|
| Start NT + Fabric GREEN | Genesis/Hub **immediately interactive** |
| Continue without link | App opens + degraded banner; Activate Birth / trading stay fail-closed |
| Fabric timeout | Modal: **Retry Fabric** or continue without live link |

**Never auto-kill NT** on this path (Code Red). Sonner is suppressed on the cover.  
Setup & Connections **reuses** cold-start Fabric state (no second long wait if already GREEN).

**Window (option A):** during Systems Go the main Tauri window is temporarily resized to hug the card (~480×760, min lowered), then restored to the Command Deck size (1600×1000, min 1280×720) before Genesis/Hub opens. One window only — no second webview.

### Overlays vs readiness

| UI | When | Role |
|----|------|------|
| `StartupReadinessScreen` + NT dialog | phase `loading` **or** `!ntStartupResolved` | Primary cold-start cover |
| `NinjaTraderDegradedBanner` | Deferred link / NT down | Persistent “no link” warning |
| Onboarding wizard | `app_surface=setup` | First install / incomplete setup |
| Birth Phase | `app_surface=birth` | Train / recover (not unlocked deck) |
| Phase Hub | `app_surface=hub` | Post-birth home |
| `DeckBlockingOverlay` | On deck only | Defense-in-depth if deck opens without readiness |
| Panel loaders | On deck panels | Telemetry hydrate only — not lifecycle gate |

---

## What happens on restart

| Your state before closing the app | After restart | Notes |
|-----------------------------------|---------------|-------|
| Never finished setup | `setup` — wizard | After readiness cover; resumes pending wizard steps |
| Setup complete, birth not started | `birth` — Birth screen | **Not** the wizard birth step |
| Birth training in progress | `birth` — progress live | Recovery / resume UI; no silent auto-train if interrupted requires Resume |
| Birth interrupted (checkpoint saved) | `birth` — recovery panel | Operator Resume/Wipe — not silent continue |
| Birth error, no artifacts | `birth` — error / retry | Deck stays blocked (fail-closed) |
| Birth complete, Foundation exit OK | **`hub` — Phase Hub** | Open Command Deck from hub when ready |
| Operator was on deck (session) | After full restart → **hub** | Deck is not sticky across process restart |
| Backend down (no prior payload) | Readiness cover · backend blocked | Retry until backend up; then SSOT routes |
| Backend down mid-session | Surface preserved where possible | Cached payload marked unreachable |

**Foundation exit:** `birth.birth_exit_ok === true` requires five `foundation_v2` receipts plus fitness vector (`is_birth_exit_sufficient`). PPO artifacts or a certificate file alone **cannot** unlock hub/deck.

**Certificate check (Proving Ground):** `birth.certificate_ok === true` requires valid Birth Certificate v2 (`state/lumina_birth_certificate.json`) with `integrity_version: 2`, matching policy hash, honest regime coverage (no inflation), and `lumina_agents/ppo/lumina_ppo_policy.zip`. This is **not** Birth Foundation exit.

**Mandatory re-birth:** Any certificate issued before the PR-A integrity fix (regime inflation removed) is invalid. Run `scripts/reset-onboarding-dev.ps1` and complete Birth Phase again.

---

## Fail-closed rules (operator expectations)

1. **No hub/deck without Foundation exit** — Cold start lands on **hub** only when `birth_exit_ok` is true; deck only via explicit operator entry. `DeckBlockingOverlay` still blocks interaction if the shell opens without readiness.
2. **Backend wins on refresh** — If client phase is stale, `useDeckLifecycleGuard` redirects when the backend says so.
3. **Interrupted ≠ failed** — Interrupted birth is recoverable; the app returns to Birth Phase, not the setup wizard. Resume/Wipe is operator-driven.
4. **Deck entry is explicit** — From Phase Hub (or post-birth cinematic handoff); not the cold-start default.
5. **REAL is fail-closed** — Command Deck REAL toggle requires maturation milestones (certificate, Evolution Proof, SIM stability, promotion gate). Backend rejects `POST /api/core/mode` with `mode=real` until `maturation_eligible_for_real()` passes.
6. **One cold-start cover** — Lifecycle waits use `StartupReadinessScreen` steps, not mid-deck “please wait” toasts for the same init.

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Stuck on wizard step 0 (backend) | FastAPI not running | Start `lumina_os/run_backend.ps1` or uvicorn on port 8000 |
| Wizard when you expect birth | Setup incomplete or backend unreachable | Check `GET /api/setup/onboarding` → `required_steps`, `app_surface_reason` |
| Empty dashboard, no controls | Birth incomplete (overlay should show) | Return to birth phase from overlay; verify `birth.birth_exit_ok` |
| Birth restarts from scratch | No checkpoint / fresh `-PartialBirth` reset | Use recovery panel; check birth logs |
| Birth certificate failed / Retry does nothing | Stale completion flag without Foundation receipts, or old client retry path | Use **Retry birth** in Command Deck (calls `POST /api/birth/retry`: clears stale artifacts, fresh certified start). Hub stays blocked until `birth_exit_ok: true`. |
| Stale `curriculum_failed` / `trades=1` while birth runs | Old backend bytecode or stale `state/lumina_birth_progress.json` | **Restart backend** after BRO deploy (`birth.engine.version=BRO-v1` in logs). Retry birth; expect phases `curriculum_research` / `curriculum_learning`, rising `patterns_mined`. |
| REAL toggle greyed out on deck | Maturation ladder incomplete | Check `GET /api/maturity/progress` → `real_trading_blockers`; complete Apprenticeship (SIM stability) and Proving Ground (shadow/promotion) |
| Always lands on deck after reset | Artifacts still on disk | Run full dev reset script without `-PartialBirth` |

---

## Dev reset commands

From repo root:

```powershell
# Full fresh install simulation
.\scripts\reset-onboarding-dev.ps1

# Setup complete, birth incomplete (restart → birth surface)
.\scripts\reset-onboarding-dev.ps1 -PartialBirth
```

Then start backend + `npm run tauri dev` in `tauri-app/` (see [tauri-app/README.md](../tauri-app/README.md)).

---

## API quick reference

```http
GET /api/setup/onboarding
```

Key fields:

| Field | Type | Description |
|-------|------|-------------|
| `app_surface` | `"setup" \| "birth" \| "hub" \| "deck"` | Canonical startup surface (`hub` after birth ready) |
| `app_surface_reason` | string | Why this surface was chosen (e.g. `maturation_hub`, `birth_pending`) |
| `skip_wizard` | boolean | `true` when `app_surface` is `hub` or `deck` |
| `birth.artifacts_ok` | boolean | PPO artifacts present and valid (not hub unlock) |
| `birth.certificate_ok` | boolean | Birth Certificate v2 valid — Proving Ground wall, not Birth exit |
| `birth.birth_exit_ok` | boolean | Foundation five receipts + fitness — primary hub-ready gate |
| `birth.status` | string | `idle`, `running`, `interrupted`, `error`, `completed`, … |
| `required_steps` | string[] | Pending onboarding steps |

```http
GET /api/maturity/progress
```

| Field | Type | Description |
|-------|------|-------------|
| `current_phase` | string | `genesis` … `real` |
| `real_trading_eligible` | boolean | Unified fail-closed REAL gate |
| `real_trading_blockers` | string[] | Human-readable missing milestones |

Full contract: [lumina-core-api-contracts.md](lumina-core-api-contracts.md) §10.

---

## Telegram notification expectations (ADR-0028 + ADR-0044 Twin)

Configure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` or `config.yaml`.

| Channel | Prefix | Examples |
|---------|--------|----------|
| Milestone | `LUMINA MILESTONE —` | Birth stage pass, maturation phase advance |
| Attention | `LUMINA ATTENTION [SEVERITY] —` | Stall, cert fail, Evolution Proof failed, REAL blocked, safe mode |
| Twin natraining | `LUMINA · Twin keek mee (natraining)` | Post-hoc Twin judgment; optional feedback |
| Twin escalatie | `LUMINA · Twin is onzeker` | Pre-besluit A/B/C/D — pad wacht |
| DNA-promotie | `LUMINA · DNA-promotie` | APPROVE / VETO (geen antwoord = auto-VETO) |

Category toggles: `telegram.notification_matrix` in `config.yaml` (`maturation`, `birth_milestones`, `birth_attention`, `real_safety`, `evolution`, `ops`).

### Twin reply cheat-sheet (operator)

| Berichttype | Wat jij doet | Voorbeeld |
|-------------|--------------|-----------|
| **Natraining** (Twin keek mee) | Optioneel bijsturen | `OK ab12cd34` · `A ab12cd34` · `B ab12cd34` · `C ab12cd34 strengere limiet` |
| **Escalatie** (Twin is onzeker) | Verplicht A–D | `A` of `TWIN ab12cd34 A` |
| **DNA-promotie** | APPROVE of VETO | `APPROVE <id>` · `VETO <id>` |

Legacy aliases blijven werken: `FIX A|V|M <id>` (= A/B/C).  
Base Twin-training blijft **alleen in de app** (Operator Vault) — nooit Telegram.

Copy SSOT: `lumina_core/evolution/twin_telegram_copy.py` (base_v4, geen engineering dumps).

Test manually:
```powershell
python scripts/send_milestone_test.py
python scripts/send_milestone_test.py --maturation genesis_contract_signed
```

Client-reported REAL safe mode: `POST /api/notifications/attention` with `reason_code: real_safe_mode`.

---

## CLI vs Command Deck vs headless

| Operator path | Command / action | Runtime behavior |
|---------------|------------------|------------------|
| **Command Deck** | Backend `:8000` + Tauri; Start Engine | Full supervisor loop via `ProcessManager` |
| **CLI daemon loop** | `python -m lumina_launcher --mode sim` or `--mode paper` | Same full supervisor stack; prints PID and exits |
| **CLI foreground debug** | `python -m lumina_launcher --mode sim --foreground` | Blocking loop in terminal (Ctrl+C stops) |
| **Headless smoke/CI** | `python -m lumina_launcher --smoke --mode sim --duration 15m` | One-shot `HeadlessRuntime` — **no** live supervisor |
| **Production headless 24/7** | `python -m lumina_launcher --headless --mode sim` | Full supervisor stack with preflight, SLO, recovery |
| **Birth status** | `python -m lumina_launcher birth status --json` | Reads `BirthService` / progress file; optional `LUMINA_LAUNCHER_TELEMETRY=1` for JSONL |

Rule: `--smoke` means one-shot validation runtime. `--headless` means continuous 24/7 production supervisor. Omit both for daemon SIM/Paper trading loops via `--mode`.

---

## Related

- ADR: [adr/0011-tauri-lifecycle-gate-ssot.md](adr/0011-tauri-lifecycle-gate-ssot.md)
- ADR: [adr/0017-birth-research-oracle.md](adr/0017-birth-research-oracle.md) (BRO-v1 never-stop curriculum)
- ADR: [adr/0027-lumina-maturation-ladder.md](adr/0027-lumina-maturation-ladder.md)
- ADR: [adr/0028-lumina-operator-notification-matrix.md](adr/0028-lumina-operator-notification-matrix.md)
- Client phase mapping: `tauri-app/src/lib/onboardingPhase.ts`
- Python SSOT: `lumina_launcher/core/onboarding.py` → `resolve_app_surface()`
