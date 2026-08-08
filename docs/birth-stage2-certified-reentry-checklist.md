# Certified Stage 2 re-entry checklist

**Purpose:** After a champion freeze (swarm no-lift) or a paused Birth session, re-enter **Stage 2 Range** under the same **certified / fail-closed** rules as Stage 1 — without training through freeze, claiming Perfect Birth, or arming REAL.

**Audience:** Operator (SIM / certified workspace only).

**Related:**  
- OR5 — `docs/operator-residuals-or1-or6.md`  
- Freeze CLI — `python scripts/validation/champion_freeze_ops.py`  
- Freeze gate — `python scripts/validation/champion_freeze_gate.py --workspace . --no-pytest`  
- Zero-human runbook — `docs/birth-zero-human-metrics-runbook.md`  
- Birth exit framing — `docs/adr/0036-birth-exit-vs-maturation.md`

---

## 0. What success means for this re-entry

| In scope | Out of scope |
|----------|----------------|
| Clear freeze honestly (accept **or** wipe) | Perfect Birth declare |
| Stage 2 survival pass (flat band 30–70%, EdgeScore/hygiene as configured) | READY_FOR_REAL / live capital |
| Productive recovery (pass metrics, not attempt counters) | Twin `full_auto` via yaml |
| Swarm only after flat-band remediation deferral | Silent champion overwrite |

Score this run as: **Stage 2 survival pass or honest stall** — not professional daytrader skill.

---

## 1. Sacred fork (do first)

**Do not train until this section is done.**

The **same questions** appear in:

| Surface | How |
|---------|-----|
| **App popup** | Birth scorecard Attention banner — Accept champion / Wipe & retry |
| **Telegram** | Critical attention with reply commands (works away from PC) |
| **CLI** | `champion_freeze_ops.py status` |

```bash
# Decision card (exit 2 = freeze open) — also re-asks Telegram if freeze open
python scripts/validation/champion_freeze_ops.py --workspace . status

# Optional: unit/progress gate
python scripts/validation/champion_freeze_gate.py --workspace . --no-pytest
```

### Telegram replies (remote autonomy)

When freeze is open, Telegram asks the same fork. Reply with **one** command:

| Reply | Effect |
|-------|--------|
| `ACCEPT` | Accept champion and continue training |
| `ACCEPT_NO_START` | Accept champion, clear freeze only (then follow this checklist) |
| `WIPE` | Wipe training, **keep tick cache** |
| `WIPE_FULL` | Wipe all birth training data |
| `STATUS` | Re-send decision card |

Backend polls Telegram while freeze is open (birth status poll + maturation autopilot).  
**If you answer in the app**, Lumina **echoes** the decision into Telegram so you can verify on your phone.

### Choose exactly one

#### A) Accept champion (keep Stage 1 receipt + current champion)

```bash
# Recommended: clear freeze, then checklist, then explicit start
python scripts/validation/champion_freeze_ops.py --workspace . accept --confirm --no-start

# Or accept and resume immediately (skips pause-for-checklist)
python scripts/validation/champion_freeze_ops.py --workspace . accept --confirm
```

Or Telegram: `ACCEPT_NO_START` / `ACCEPT` · Or app: **Accept champion**.

Use when: Stage 1 receipt is valuable, champion policy is the best known baseline, and you want to **continue** curriculum after freeze.

#### B) Wipe and re-enter Birth

```bash
# Prefer keep tick cache for faster re-entry (still clears training/champion freeze state)
python scripts/validation/champion_freeze_ops.py --workspace . wipe --confirm --keep-tick-cache

# Full training wipe (redirect toward genesis if setup incomplete)
python scripts/validation/champion_freeze_ops.py --workspace . wipe --confirm
```

Or Telegram: `WIPE` / `WIPE_FULL` · Or app: **Wipe & retry**.

Use when: Stage 2 policy is toxic, you want a clean ladder, or accept would only preserve a known-bad champion.

### Verify fork closed

```bash
python scripts/validation/champion_freeze_ops.py --workspace . status
# expect: freeze_active=false (or decision=freeze_resolved_accepted / no_freeze)
python scripts/validation/champion_freeze_gate.py --workspace . --no-pytest
```

- [ ] Freeze open → status exit 2 resolved  
- [ ] No plan to “just Hervat checkpoint” while freeze was active  
- [ ] Choice recorded (accept vs wipe) by operator  

---

## 2. Preflight (SIM / certified only)

- [ ] Capital mode is **SIM / Birth**, never REAL for this experiment  
- [ ] Workspace is the intended certified Birth workspace  
- [ ] Twin remains shadow / promote-gated (no yaml `full_auto`)  
- [ ] Constitution floors not lowered for “finish Stage 2”  
- [ ] Data / instrument / tick cache preflight OK (after wipe: re-run setup if redirected to genesis)

```bash
# Theater residual (should not demand accept/wipe after fork)
python scripts/validation/recovery_theater_gate.py --workspace . --no-pytest
```

---

## 3. Re-entry mode

### After **accept** (continue Stage 2)

- [ ] Stage 1 still listed in `stages_passed` (or stage1 pass receipt present)  
- [ ] Checkpoint / progress show champion accepted, not `swarm_rejected_no_lift`  
- [ ] Start/resume Birth **explicitly** (Tauri start/resume or service start) with certified flags  
- [ ] Budget remaining understood (do not invent a hollow larger budget to force pass)

### After **wipe** (full Birth re-entry)

- [ ] Genesis / setup complete if `redirect_to_genesis`  
- [ ] Start **certified Birth** from Stage 1 (or curriculum start) — do not claim Stage 2-only without receipts  
- [ ] Prefer same instrument/data profile as the forensic run for comparability  

---

## 4. Watchlist during Stage 2 (what to monitor)

| Signal | Healthy | Unhealthy |
|--------|---------|-----------|
| `position_flat` / flat band | Moves toward **30–70%** | Stuck ≥70% (under-activity) or ≪30% (over-trade) |
| Recovery | `productive=true` early, theater only when honest | `autonomous_recovery_successes` high while blocker unchanged |
| Swarm | Deferred while flat-band fail (early evolution steps) | Immediate swarm theater on 95% flat |
| Freeze | Hard-stop → accept/wipe only | Train / auto-resume under freeze |
| Soft blocks | Capital soft-blocks OK | Hard constitution violations > 0 |

New remediation (post-mortem): under-activity trap → `explore_boost_anti_flat` + flat floor exploration before swarm-first.

- [ ] Flat-band pressure observed if over-flat  
- [ ] No train-through-freeze  
- [ ] If freeze returns → back to §1 only  

---

## 5. Exit scoring (this re-entry only)

| Outcome | Criteria |
|---------|----------|
| **Pass** | Stage 2 pass criteria / EdgeScore path met; volume gate + flat band honest |
| **Honest stall** | Freeze or terminal with clear `next_action`; capital preserved |
| **Fail / invalid** | Train under freeze, hollow pass, REAL arm, or Perfect Birth declare without evidence |

- [ ] Do **not** declare Perfect Birth from Stage 2 survival alone  
- [ ] Do **not** advance continuum to skill/REAL claims without later maturation proofs  

---

## 6. Operator residual board (optional, before SP3)

```bash
python scripts/validation/operator_residuals_gate.py --workspace .
```

OR5 should be green after accept or wipe. OR1–OR4 / H1 remain separate evidence work — they do not block Stage 2 SIM re-entry, but they **do** block production REAL claims and SP3 apply.

---

## 7. Forbidden shortcuts

- Train through `swarm_reject_hard_stop` / champion freeze  
- Lower certificate or constitution floors to force Stage 2  
- Auto-accept champion via twin or unattended script without `--confirm`  
- Declare Perfect Birth / arm REAL from this checklist  
- Treat recovery attempt counters as graduation  

---

## Quick command card

```bash
# 1) See fork
python scripts/validation/champion_freeze_ops.py --workspace . status

# 2a) Accept (clear freeze, checklist, then start yourself)
python scripts/validation/champion_freeze_ops.py --workspace . accept --confirm --no-start

# 2b) Or wipe (keep ticks)
python scripts/validation/champion_freeze_ops.py --workspace . wipe --confirm --keep-tick-cache

# 3) Verify
python scripts/validation/champion_freeze_gate.py --workspace . --no-pytest
python scripts/validation/recovery_theater_gate.py --workspace . --no-pytest

# 4) Start certified Birth via product UI / birth service (explicit)
```
