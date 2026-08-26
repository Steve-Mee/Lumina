# Operator residuals OR1–OR6

**Purpose:** Close the **human/ops evidence bar** after deep-audit T1–T15 and self-play Phase 0 (SP0–SP2).  
**Board:** `python scripts/validation/operator_residuals_gate.py`

These are **not** missing libraries. Automated gates exist; residuals are live evidence, NT8 host proof, and sacred human forks.

---

## Why this list exists (written early)

1. **T1–T15 code complete** — safety/ops gates, freeze, theater, twin SSOT shipped.  
2. **Self-play Phase 0** must not outrun capital honesty — residuals stay visible.  
3. **SP3–SP4 blocked** until freeze/theater/PB/twin paths are honest (see bottom).  
4. **Fail-closed product** — never silent REAL, hollow Perfect Birth, or train-through-freeze.

---

## Board (one command)

```bash
python scripts/validation/operator_residuals_gate.py
python scripts/validation/operator_residuals_gate.py --workspace .
python scripts/validation/operator_residuals_gate.py --fabric-mock   # slower; runs T1 mock
python scripts/validation/operator_residuals_gate.py --json

# R2 cadence (every 15–60 min): residuals + PB + theater + Phase2 + data SLA
python scripts/validation/birth_zero_human_cadence.py --workspace .
```

| Status | Meaning |
|--------|---------|
| **OK** (green) | Evidence or inactive residual satisfied |
| **..** (yellow) | Soft pending evidence / labels / samples |
| **FAIL** (red) | Automated gate broken — fix code first |
| **STOP** (blocked) | Human fork required now (freeze/theater) |

---

## OR1 — Fabric live SAFE_MODE / HB ≥5s cancel

| | |
|--|--|
| **Why residual** | Brain mock gate is automated (T1). **Live NT8 host cancel after heartbeat drop ≥5s** is still operator-manual (C# watchdog). |
| **Automated** | `python scripts/validation/fabric_safe_mode_gate.py --mock` |
| **Live SIM only** | `python scripts/validation/fabric_safe_mode_gate.py --live` (needs `LUMINA_FABRIC_TOKEN`) |
| **Operator checklist** | [execution-fabric-phase0.md](execution-fabric-phase0.md) § Manual SIM gate |
| **Pass** | Mock green + live checklist completed on **Sim101** (never REAL) |
| **Blocks SP3?** | No (SP3 is SIM self-play apply). **Blocks production REAL capital path.** |

---

## OR2 — Aperture coverage ≥95%

| | |
|--|--|
| **Why residual** | Measurement tool exists (T2). Production sample_size often 0 → soft pass. |
| **Command** | `python scripts/validation/aperture_coverage_gate.py --min-pct 95` |
| **Pass** | `sample_size ≥ 10` and `coverage_pct ≥ 95` |
| **Operator** | Route SIM/live-path orders through single capital aperture; re-measure |
| **Blocks SP3?** | No. **Blocks claiming H1 capital honesty complete.** |

---

## OR3 — Perfect Birth campaign + declare

| | |
|--|--|
| **Why residual** | Campaign CLI exists (T5). Unlock/declare stay **fail-closed** — no hollow flags. |
| **Command** | `python scripts/validation/perfect_birth_campaign.py --workspace .` |
| **Declare (only if unlock green)** | `python scripts/validation/declare_perfect_birth.py --dry-run` then explicit declare |
| **Pass** | `unlock_valid=true` after honest KPI evidence |
| **Blocks SP3?** | **Yes** — Phase 1 self-play apply expects honest maturity path |

---

## OR4 — Twin promote ladder + SSOT

| | |
|--|--|
| **Why residual** | SSOT audit + promote ops exist (T6/T15). Live labels/agreement may be incomplete. |
| **Commands** | `python scripts/validation/twin_mode_ssot_audit.py` · `python scripts/validation/twin_promote_ops.py --isolated` |
| **Pass** | SSOT `ok`; promote only via gate; **never** yaml `mode: full_auto` |
| **Blocks SP3?** | **Yes** — SIM apply under Twin needs healthy twin path |

---

## OR5 — Champion freeze (live accept/wipe)

| | |
|--|--|
| **Why residual** | Unit pack proves hard-stop (T7). **Live freeze requires human** accept or wipe. |
| **Status card** | `python scripts/validation/champion_freeze_ops.py --workspace . status` |
| **Accept (clear freeze, no auto-start)** | `python scripts/validation/champion_freeze_ops.py --workspace . accept --confirm --no-start` |
| **Wipe (keep tick cache)** | `python scripts/validation/champion_freeze_ops.py --workspace . wipe --confirm --keep-tick-cache` |
| **Gate** | `python scripts/validation/champion_freeze_gate.py --workspace . --no-pytest` |
| **If freeze active** | CLI, Tauri, or **Telegram** (`ACCEPT` / `WIPE`) — no auto-train |
| **Telegram** | Same questions as app popup; app answers echoed to chat |
| **After fork** | [birth-stage2-certified-reentry-checklist.md](birth-stage2-certified-reentry-checklist.md) |
| **Pass** | No open freeze, or champion_accepted |
| **Blocks SP3?** | **Yes** while freeze active without accept |

---

## OR6 — Recovery theater (single surface)

| | |
|--|--|
| **Why residual** | Compress/gate done (T11). Live theater still means **stop spinning**. |
| **Command** | `python scripts/validation/recovery_theater_gate.py --workspace . --no-pytest` |
| **If theater + freeze** | `next_action=accept_champion_or_wipe` only |
| **Pass** | Not stuck in theater without action; single active surface |
| **Blocks SP3?** | **Yes** when theater demands accept/wipe |

---

## SP1–SP2 status

| ID | Status |
|----|--------|
| **SP0** | Done — ADR-0037 Accepted (lab) |
| **SP1** | **Implemented** — `lumina_core/birth/self_play/` + tests |
| **SP2** | **Implemented** — `self_play_lab_gate.py` + deep-audit soft entry |
| **SP3** | Deferred — SIM apply under Twin |
| **SP4** | Deferred — birth-loop observe hook |

---

## Phase 2 campaign ladder (R3)

```bash
# Pre-PB: observe only (propose + audit; never mutates; never REAL)
python scripts/validation/phase2_shadow_campaign.py --observe

# After Perfect Birth declare (evidence green):
python scripts/validation/phase2_shadow_campaign.py --enable

# After shadow evidence accumulates:
python scripts/validation/phase2_shadow_campaign.py --promote-apply   # SIM apply only

python scripts/validation/phase2_shadow_campaign.py --disable
```

**Policy:** observe may run without Perfect Birth. Shadow + apply require PB evidence. REAL apply is always forbidden here.

## Before implementing SP3–SP4

Do **not** start SP3/SP4 until:

1. **Board has no red** — `operator_residuals_gate.py` ok (automated failures fixed).  
2. **OR5 not STOP** — no open champion freeze (accept or wipe).  
3. **OR6 not STOP** — no theater demanding accept/wipe.  
4. **OR3 progressing honestly** — PB campaign path clear; unlock preferred before Phase 1 apply.  
5. **OR4 SSOT green** — twin mode not yaml-forced; promote gate usable for SIM apply authority.  
6. **ADR-0037 Phase 1 design accepted** — `allow_apply` still gated; Twin + constitution required; REAL still forbidden.  
7. **SP1–SP2 still green** — `python scripts/validation/self_play_lab_gate.py --no-pytest --fixture --ignore-progress`.

**Still not required for SP3 (SIM-only apply lab):** full OR1 live NT8 checklist or OR2 ≥95% production samples — those remain **capital/REAL honesty** residuals and should be closed before any REAL path, but SP3 must stay SIM/Birth capital only.

**Permanent non-goals:** auto REAL · cert floor drops · yaml twin full_auto · architecture auto-apply · train through freeze.

---

## Related

- [birth-zero-human-metrics-runbook.md](birth-zero-human-metrics-runbook.md)  
- [self-play-lab.md](self-play-lab.md)  
- [adr/0037-self-play-design.md](adr/0037-self-play-design.md)  
- [execution-fabric-phase0.md](execution-fabric-phase0.md)  
