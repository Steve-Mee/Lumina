# Birth zero-human metrics runbook (T14)

**Purpose:** Run production **Birth** on SIM / certified workspace with **minimal operator touch**, using automated gates + honest metrics.  
**Not in scope:** auto REAL capital, hollow Perfect Birth declare, yaml `approval_twin.mode: full_auto` force.

Related contracts: [starship-birth.md](starship-birth.md), [birth-phase-live-validation-runbook.md](birth-phase-live-validation-runbook.md), [ADR-0036 birth exit vs maturation](adr/0036-birth-exit-vs-maturation.md).

---

## 1. Zero-human vs human-required (fail-closed)

| Situation | Engine may auto-recover? | Operator action |
|-----------|--------------------------|-----------------|
| Stage stall / wall / plateau (pre-swarm freeze) | Yes (bounded Organism Autonomy / phoenix budget) | Monitor only |
| Stage-2 **expectancy stall** (flat in band, WR−0.50 below floor) | Yes — quality ladder (rollback → reward → explore_reduce → pattern inject); swarm deferred | Monitor only |
| Recovery theater (spin without lift) | No ladder burn when freeze/theater | Twin or human `accept_champion`; wipe stays human |
| Swarm **no tournament lift** (champion freeze) | **No train** on rejected swarm. Twin may **`accept_champion`** (keep best, conf≥0.80, constitution 0, birth/SIM) when `birth_twin_freeze_resolve_enabled` | Wipe always human; Twin low-conf → Telegram accept/wipe |
| Certificate failed | Remediation path if configured | Review `failure_reasons`; continue / expand / wipe |
| Perfect Birth unlock + declare | Never auto-declare | Explicit `declare_perfect_birth.py` only when evidence green |
| Twin promote to `full_auto` | Never from yaml force | Evidence + twin promote ops path |
| REAL multi-gate / live orders | Never auto-arm REAL | Separate REAL runbooks only |

**Rule:** Zero-human means the organism can **breathe and remediate within bounds**. It does **not** mean silent capital risk, auto-wipe, train-through-freeze, or REAL arming. Twin **accept_champion** keeps the frozen champion and continues the quality ladder — it does not commit a rejected swarm.

---

## 2. Preflight (once per workspace)

```bash
# SIM / certified only — never REAL for unattended birth
python scripts/validation/fabric_safe_mode_gate.py --mock
python scripts/validation/champion_freeze_gate.py --no-pytest
python scripts/validation/recovery_theater_gate.py --no-pytest
python scripts/validation/run_deep_audit_gates.py
```

Optional live workspace scan:

```bash
python scripts/validation/champion_freeze_gate.py --workspace .
python scripts/validation/perfect_birth_campaign.py --workspace .
python scripts/validation/recovery_theater_gate.py --workspace . --no-pytest
```

Backend + Tauri Command Deck running; Birth start from deck or headless birth service.

---

## 3. Metrics SSOT (what to watch)

### 3.1 Progress file

Prefer `state/lumina_birth_progress.json` (fallback `state/first_boot_progress.json`).

| Field | Healthy unattended | Attention |
|-------|--------------------|-----------|
| `phase` / `stage` | curriculum / ppo / ticks_ready | `stage_stalled`, `certificate_failed`, freeze phases |
| `needs_attention` | false | true → read reason + summary |
| `attention_reason_code` | empty | `swarm_no_tournament_lift` (legacy `swarm_no_edgescore_lift` alias) |
| `swarm_rejected_no_lift` | false | true → **hard-stop**; no auto-train |
| `swarm_champion_accepted` | — | true → freeze resolved by operator |
| `swarm_tournament_lift_ok` | true after commit | false after reject |
| `swarm_tournament_at_start` | baseline tournament score | dual-written legacy `swarm_edgescore_*` |
| `edgescore` / hygiene WR | advancing toward stage gate | long flat below hygiene |
| `entropy_alive` | true when sampled | false/missing stalls exploration honesty |
| `recovery` (`recovery_compress_v1`) | `productive` / single active surface | `theater=true` → stop spinning |
| `recovery.next_action` | `let_engine_recover` / `none` | `accept_champion_or_wipe` |

### 3.2 API (operator / automation)

| Endpoint / tool | Use |
|-----------------|-----|
| `GET /api/birth/status` | Live progress + attention (Tauri normalizes tournament keys) |
| `GET /api/birth/perfect-birth-status` | PB checklist honesty |
| `python scripts/validation/perfect_birth_campaign.py` | Campaign gaps + next actions |
| `python scripts/validation/recovery_theater_gate.py` | Theater residual / freeze surface |
| `python scripts/validation/phase2_shadow_campaign.py` | Phase 2 SIM shadow only after PB unlock |

### 3.3 Logs (grep)

```text
birth.engine.version=BRO-v2
birth.stage.passed
birth.stage.wall_budget_exhausted
swarm_no_tournament_lift
rejected_no_lift
champion freeze
recovery_compress
certificate_failed
stage_stalled
preserve_checkpoint
```

---

## 4. Unattended loop (recommended cadence)

**Every 15–60 min** (cron / operator glance):

```bash
python scripts/validation/perfect_birth_campaign.py --workspace . --json > /tmp/pb_campaign.json
python scripts/validation/recovery_theater_gate.py --workspace . --no-pytest --json
```

**Green if:**

- Campaign checklist progressing or unlock path honest (`would_pass` / ordered actions clear)
- Recovery theater `ok` and not stuck in theater without next_action
- No silent REAL mode

**Page human if:**

1. `swarm_rejected_no_lift` or attention `swarm_no_tournament_lift`  
   → **Accept champion** or **Wipe & restart** (no “just resume training”)
2. `recovery.theater == true` and next_action is `accept_champion_or_wipe`
3. Certificate failed with non-actionable empty reasons
4. Wall budget exhausted without plateau/swarm/stall phase transition for many hours

---

## 5. Champion freeze (T7 sacred path)

After swarm reject:

1. Training **must not** resume via auto-resume / autonomous recovery.
2. Progress shows attention + recommended actions `accept_champion` / `wipe_and_retry`.
3. Operator decision card + accept/wipe (app, CLI, **or Telegram**):

```bash
python scripts/validation/champion_freeze_ops.py --workspace . status
# exit 2 = freeze open — choose one:
# python scripts/validation/champion_freeze_ops.py --workspace . accept --confirm --no-start
# python scripts/validation/champion_freeze_ops.py --workspace . wipe --confirm --keep-tick-cache
# Telegram (same questions): ACCEPT | ACCEPT_NO_START | WIPE | WIPE_FULL
```

App choices are **echoed to Telegram**. Telegram replies are applied without sitting at the PC (status poll + autopilot).

4. After fork: follow [birth-stage2-certified-reentry-checklist.md](birth-stage2-certified-reentry-checklist.md).
5. Verify anytime:

```bash
python scripts/validation/champion_freeze_gate.py --workspace . --no-pytest
```

Unit proof pack (CI):

```bash
python scripts/validation/champion_freeze_gate.py
```

---

## 6. Perfect Birth → Phase 2 shadow (evidence only)

```bash
# Status / gaps (never declares)
python scripts/validation/perfect_birth_campaign.py --workspace .

# Declare only when evidence conjunction green (operator intentional)
python scripts/validation/declare_perfect_birth.py --dry-run
# python scripts/validation/declare_perfect_birth.py   # explicit only

# Phase 2 SIM shadow after unlock (not production REAL)
python scripts/validation/phase2_shadow_campaign.py --workspace .
# --enable only when unlock_valid
```

---

## 7. KPI board (zero-human health)

| KPI | Target | Source |
|-----|--------|--------|
| Silent stall hours | 0 (wall/stall/swarm transition) | progress phase + wall fields |
| Champion freeze auto-train | 0 events | freeze gate + tests |
| Recovery theater without action | 0 long-lived | `recovery_compress_v1` |
| Hollow PB declare | 0 | perfect birth gate fail-closed |
| Twin yaml full_auto force | 0 | config policy / twin promote ops |
| REAL auto-arm | 0 | multi-gate + fabric SAFE |

---

## 8. Done criteria for “production birth ready (SIM)”

- [ ] Live validation runbook §1–7 passed once on target data profile  
- [ ] Champion freeze gate green  
- [ ] Recovery theater gate green (soft residual layers reported only)  
- [ ] Deep audit pack green enough for safety floor  
- [ ] Operator understands freeze → accept/wipe is the only human fork  
- [ ] Perfect Birth campaign either progressing or unlocked with honest checklist  

---

## 9. Forbidden shortcuts

- Lowering certificate floors to “finish birth”
- Setting twin `full_auto` in yaml to skip evidence
- Auto-resume training after `swarm_rejected_no_lift`
- Declaring Perfect Birth without conjunction evidence
- Enabling REAL capital from this runbook

---

## Related scripts (deep-audit pack)

| Script | Task |
|--------|------|
| `scripts/validation/fabric_safe_mode_gate.py` | T1 |
| `scripts/validation/aperture_coverage_gate.py` | T2 |
| `scripts/validation/real_multi_gate_dry_run.py` | T3 |
| `scripts/validation/real_broker_recon_gate.py` | T4 |
| `scripts/validation/perfect_birth_campaign.py` | T5 |
| `scripts/validation/twin_promote_ops.py` | T6 |
| `scripts/validation/twin_mode_ssot_audit.py` | T15 |
| `scripts/validation/operator_residuals_gate.py` | OR1–OR6 board |
| `scripts/validation/champion_freeze_gate.py` | T7 |
| `scripts/validation/phase2_shadow_campaign.py` | T8 |
| `scripts/validation/run_deep_audit_gates.py` | T9 |
| `scripts/validation/capital_bus_lineage_gate.py` | T10 |
| `scripts/validation/recovery_theater_gate.py` | T11 |
