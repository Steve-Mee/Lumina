# Command Deck — Startup & Restart Runbook

**Date:** 2026-06-11  
**Audience:** Operators and support  
**Scope:** LUMINA Neural Command Deck (Tauri) cold start and app restart  
**SSOT:** `GET /api/setup/onboarding` → `app_surface` / `app_surface_reason`  
**Implementation:** [tauri-startup-gate-implementation-plan.md](requests/tauri-startup-gate-implementation-plan.md)

---

## One-line summary

**Setup once → train birth until artifacts exist → then Command Deck every time you restart.**

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

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Stuck on wizard step 0 (backend) | FastAPI not running | Start `lumina_os/run_backend.ps1` or uvicorn on port 8000 |
| Wizard when you expect birth | Setup incomplete or backend unreachable | Check `GET /api/setup/onboarding` → `required_steps`, `app_surface_reason` |
| Empty dashboard, no controls | Birth incomplete (overlay should show) | Return to birth phase from overlay; verify `birth.artifacts_ok` |
| Birth restarts from scratch | No checkpoint / fresh `-PartialBirth` reset | Use recovery panel; check birth logs |
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

Full contract: [lumina-core-api-contracts.md](lumina-core-api-contracts.md) §10.

---

## Related

- ADR: [adr/0011-tauri-lifecycle-gate-ssot.md](adr/0011-tauri-lifecycle-gate-ssot.md)
- Client phase mapping: `tauri-app/src/lib/onboardingPhase.ts`
- Python SSOT: `lumina_launcher/core/onboarding.py` → `resolve_app_surface()`
