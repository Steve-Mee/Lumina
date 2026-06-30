# Command Deck — Startup & Restart Runbook

**Date:** 2026-06-11  
**Audience:** Operators and support  
**Scope:** LUMINA Neural Command Deck (Tauri) cold start and app restart  
**SSOT:** `GET /api/setup/onboarding` → `app_surface` / `app_surface_reason`  
**Implementation:** [tauri-startup-gate-implementation-plan.md](requests/tauri-startup-gate-implementation-plan.md)

---

## One-line summary

**Setup once → sign Genesis Maturity Charter → train Birth until artifacts exist → grow through maturation phases → REAL only when ladder complete.**

---

## Maturation ladder (Genesis → REAL)

| Phase | Operator action | Blocks REAL? |
|-------|-----------------|--------------|
| **Genesis** | Set training trades, winrate gate (35–45%), data policy on Neural Genesis deck; ACTIVATE BIRTH | No |
| **Birth** | Historical curriculum runs (BRO-v1) | No |
| **Awakening** | Birth Certificate v2 + Evolution Proof (ADR-0026) | Yes |
| **Playground** | NT sim orders; first sim order milestone | No |
| **Apprenticeship** | `sim_real_guard` + 5-day SIM stability (`READY_FOR_REAL`) | Yes |
| **Proving Ground** | Shadow validation + PromotionGate pass | Yes |
| **REAL** | Command Deck REAL toggle after `POST /api/maturity/approve-real` | — |

Progress SSOT: `state/lumina_maturity_progress.json` · API: `GET /api/maturity/progress`

The Command Deck **Maturity strip** shows current phase and blocking reasons. SIM Readiness (Evolution tab) shows stability criteria; use the deck REAL toggle — not the deprecated standalone go-live button.

---

## Three surfaces

| # | Surface (`app_surface`) | Meaning | What you see |
|---|-------------------------|---------|--------------|
| 1 | `setup` | Machine or config not ready | Onboarding wizard |
| 2 | `birth` | Setup done, PPO policy not ready | Birth Phase screen (cinematic) |
| 3 | `deck` | Setup + birth complete | Command Deck |

The backend function `resolve_app_surface()` in `lumina_launcher/core/onboarding.py` decides the surface. The desktop app does not guess from localStorage.

---

## What happens on restart

| Your state before closing the app | After restart | Notes |
|-----------------------------------|---------------|-------|
| Never finished setup | `setup` — wizard | Resumes at first pending step (backend, Ollama, credentials, etc.) |
| Setup complete, birth not started | `birth` — Birth screen | **Not** the wizard birth step; cinematic monitor only |
| Birth training in progress | `birth` — progress live | Training continues or resumes from checkpoint |
| Birth interrupted (checkpoint saved) | `birth` — recovery panel | May auto-continue training; operator can retry from UI |
| Birth error, no artifacts | `birth` — error / retry | Deck stays blocked (fail-closed) |
| Birth complete, artifacts on disk | `deck` — Command Deck | No wizard flash; optional welcome overlay once |
| Backend down but setup was done | `setup` — backend step | Wizard shows backend unreachable; fix FastAPI on `:8000` |

**Artifacts check:** `birth.certificate_ok === true` requires valid Birth Certificate v2 (`state/lumina_birth_certificate.json`) with `integrity_version: 2`, matching policy hash, honest regime coverage (no inflation), and `lumina_agents/ppo/lumina_ppo_policy.zip`.

**Mandatory re-birth:** Any certificate issued before the PR-A integrity fix (regime inflation removed) is invalid. Run `scripts/reset-onboarding-dev.ps1` and complete Birth Phase again.

---

## Fail-closed rules (operator expectations)

1. **No deck without artifacts** — Even if the UI briefly shows the cockpit shell, `DeckBlockingOverlay` blocks interaction until `artifacts_ok` is true.
2. **Backend wins on refresh** — If client phase is stale, `useDeckLifecycleGuard` redirects to birth or wizard when the backend says so.
3. **Interrupted ≠ failed** — Interrupted birth is recoverable; the app returns to Birth Phase, not the setup wizard.
4. **Deck entry is explicit** — After birth completes, the operator confirms **Enter Command Deck** in the cinematic flow (welcome overlay may follow).
5. **REAL is fail-closed** — Command Deck REAL toggle requires maturation milestones (certificate, Evolution Proof, SIM stability, promotion gate). Backend rejects `POST /api/core/mode` with `mode=real` until `maturation_eligible_for_real()` passes.

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Stuck on wizard step 0 (backend) | FastAPI not running | Start `lumina_os/run_backend.ps1` or uvicorn on port 8000 |
| Wizard when you expect birth | Setup incomplete or backend unreachable | Check `GET /api/setup/onboarding` → `required_steps`, `app_surface_reason` |
| Empty dashboard, no controls | Birth incomplete (overlay should show) | Return to birth phase from overlay; verify `birth.artifacts_ok` |
| Birth restarts from scratch | No checkpoint / fresh `-PartialBirth` reset | Use recovery panel; check birth logs |
| Birth certificate failed / Retry does nothing | Stale completion flag without valid v2 cert, or old client retry path | Use **Retry birth** in Command Deck (calls `POST /api/birth/retry`: clears stale artifacts, fresh certified start). Deck stays blocked until `certificate_ok: true`. |
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
| `app_surface` | `"setup" \| "birth" \| "deck"` | Canonical startup surface |
| `app_surface_reason` | string | Why this surface was chosen (diagnostics) |
| `skip_wizard` | boolean | `true` only when `app_surface === "deck"` |
| `birth.artifacts_ok` | boolean | PPO artifacts present and valid |
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

## Telegram notification expectations (ADR-0028)

Configure `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in `.env` or `config.yaml`.

| Channel | Prefix | Examples |
|---------|--------|----------|
| Milestone | `LUMINA MILESTONE —` | Birth stage pass, maturation phase advance |
| Attention | `LUMINA ATTENTION [SEVERITY] —` | Stall, cert fail, Evolution Proof failed, REAL blocked, safe mode |

Category toggles: `telegram.notification_matrix` in `config.yaml` (`maturation`, `birth_milestones`, `birth_attention`, `real_safety`, `evolution`, `ops`).

Test manually:
```powershell
python scripts/send_milestone_test.py
python scripts/send_milestone_test.py --maturation genesis_contract_signed
```

Client-reported REAL safe mode: `POST /api/notifications/attention` with `reason_code: real_safe_mode`.

---

## Related

- ADR: [adr/0011-tauri-lifecycle-gate-ssot.md](adr/0011-tauri-lifecycle-gate-ssot.md)
- ADR: [adr/0017-birth-research-oracle.md](adr/0017-birth-research-oracle.md) (BRO-v1 never-stop curriculum)
- ADR: [adr/0027-lumina-maturation-ladder.md](adr/0027-lumina-maturation-ladder.md)
- ADR: [adr/0028-lumina-operator-notification-matrix.md](adr/0028-lumina-operator-notification-matrix.md)
- Client phase mapping: `tauri-app/src/lib/onboardingPhase.ts`
- Python SSOT: `lumina_launcher/core/onboarding.py` → `resolve_app_surface()`
