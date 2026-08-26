# Starship Birth — Phase A + B Contract

SSOT for Birth learning integrity, swarm tournaments, twin CONTINUE, and certificate honesty.

**Organism framing:**

- **Birth phase exit** = five Foundation `foundation_v2` receipts + fitness vector (ADR-0046) — not artifacts-only, not a WR exam, not OOS 0.48, not Perfect Birth.
- **Inside Birth**, stages 1–5 pass on process-R, occupancy, and first-touch. EdgeScore / WR sliders are HUD diagnostics. WR 20/35/40 is **not** current pass law.
- **Playground / Proving Ground** hold economic viability, Evolution Proof, and OOS certificate walls.

Canonical floors + why (locked): **[birth-curriculum-stage-floors.md](birth-curriculum-stage-floors.md)**.  
Maturation ladder: [organism-maturation-phases.md](adr/organism-maturation-phases.md).

## Locked decisions

| Topic | Rule |
|-------|------|
| **Certificate thresholds** | Frozen. Do **not** lower `min_oos_winrate` (0.48), Sharpe, drawdown, or holdout trade floors in `BirthCertificateThresholds`. |
| **full_auto** | Never force-promote twin mode in yaml. CONTINUE only when twin is already `full_auto` + executable + conf≥0.80 + swarm tournament **resolved** (commit or `champion_accepted`) + constitution clean (`starship_twin_continue_when_full_auto`). Audit: `python scripts/validation/twin_mode_ssot_audit.py` (T15). |
| **Compress** | Thin `BirthControlPlane` + skip plateau ladder **and** stall remediation after freeze/accept. No big-bang rewrite of `plateau_escalator.py`. |

## Phase A (summary)

- Stage-1 pass law = Foundation process-R (median loss R ≤ 1.5, settlement, net RR ≥ 0.80). EdgeScore survival floors remain HUD diagnostics; vanity 45% WR is never `passed`.
- Swarm-first before recovery ladder; commit only on **tournament lift** (`tournament_score`); else restore champion + `rejected_no_lift`.
- Champion freeze / accept-champion path; pause SSOT for birth + first_boot progress.

## Phase B

### B0 — Identical-window swarm + statistical lift

- Freeze `W` tick windows once at swarm start (`PolicySwarmState.frozen_tick_windows`).
- Probe + variants evaluate on the same windows (cursor reset per probe/variant).
- Missing/empty windows while `active=True` → **fail-closed** deactivate + attention (`swarm_frozen_windows_missing`); **never** fall open to a fresh `_stage_tick_pool`.
- Lift threshold: `max(meaningful_delta, 0.5/sqrt(trades))` when trades known; config delta only when trades unknown.

### B1 — Safe twin CONTINUE

- `recovery_no_lift_brake` skipped when swarm already resolved (commit / `champion_accepted`).
- `rejected_no_lift` alone is **not** CONTINUE-eligible (`swarm_tournament_done` ≠ `swarm_tournament_resolved`).
- Twin DNA includes live `edgescore`, `swarm_rejected_no_lift`, `swarm_champion_accepted`, `best_edgescore`.
- CONTINUE eligibility via `birth_control_plane.twin_continue_eligible`.

### B2 — Smarter OOS (thresholds frozen)

- Holdout payload includes `oos_regime_breakdown`.
- With trajectory evidence, claimed regimes with 0 trades → `oos_regime_empty`.
- Micro-OOS / runway may report multi-slice mean WR; **full holdout remains SSOT** for `certificate_passed`.

### B3 — Stage 2/3 HUD EdgeScore (not Foundation pass)

- Flags: `stage2_edgescore_enabled` / `stage3_edgescore_enabled` (default true).
- Scorecard ids: `range_edgescore`, `mixed_edgescore` (Mission Control + Metrics Strip).
- EdgeScore `.passed` / rolling WR may paint HUD blockers; **graduation is `evaluate_stage_pass` only** (process-R + occupancy). Never “Ready to pass” without `stage_pass_now`.
- **Pass (locked, ADR-0046):** Stage 2 occupancy 30–70% + process-R; Stage 3 occupancy 25–75% + edge ≥ −5pp vs first-touch. **Not** WR 35%. **Not** pro OOS 0.48.
- Full doctrine: [birth-curriculum-stage-floors.md](birth-curriculum-stage-floors.md).

### B4 — BirthControlPlane

- Façade: `lumina_core/birth/birth_control_plane.py`.
- After `champion_accepted` or pre-accept `rejected_no_lift`: skip plateau ladder steps **and** stall remediation (attention / operator path only).

### B5 / Gap-fill / Seal contract

- Live identical-window fail-closed (iteration + resume).
- After `rejected_no_lift` (pre-accept): **hard-stop training** — no fresh-pool PPO until accept champion or wipe.
- Swarm winner ranking uses `tournament_score` (same physics as lift gate).
- Stall remediation start **and** in-loop advance gated after freeze/accept.
- Tournament-lift naming: prefer `swarm_no_tournament_lift`; keep `swarm_no_edgescore_lift` as legacy synonym in mapper.
- HUD honesty for S2/S3 EdgeScore decimals (no false-green hygiene tone).

### Seal II

Plan: [starship-birth-seal-ii.md](starship-birth-seal-ii.md).

- Progress/metrics SSOT: `swarm_tournament_at_start` / `swarm_tournament_lift_ok` (legacy `swarm_edgescore_*` still written).
- Lift helper: `swarm_tournament_lift` (legacy `swarm_edgescore_lift` alias).
- Hard-stop progress always sets `needs_attention` via reject flags + accept/wipe actions.
- Ladder tables/step API extracted to `plateau_evolution_ladder.py` (re-exported from escalator).
- Still locked: no cert floor drop, no yaml `full_auto` force.

### Tauri tournament naming (T12)

- Client SSOT: `tauri-app/src/lib/birth/birthTournamentNaming.ts` — prefer `swarm_tournament_*`, normalize `swarm_no_edgescore_lift` → `swarm_no_tournament_lift`, rewrite residual “EdgeScore lift” operator copy.
- Status fetch path applies normalization (`fetchBirthStatusTyped` / birth mutations).
- Stage HUD shows **Tournament lift** field (swarm physics); stage pass metric is Foundation process-R / occupancy (`stage_pass_now`). EdgeScore is diagnostic theater, not graduation.

## Key modules

- `lumina_core/birth/starship_birth.py` — physics predicates
- `lumina_core/birth/birth_control_plane.py` — call-site façade
- `lumina_core/birth/policy_swarm.py` — frozen windows
- `lumina_core/birth/plateau_evolution_ladder.py` — evolution ladder step API
- `lumina_core/birth/certificate_evaluator.py` — regime breakdown / multi-slice

## Operator pointer

See also [birth-phase-live-validation-runbook.md](birth-phase-live-validation-runbook.md) § Starship Birth.  
**Zero-human metrics (T14):** [birth-zero-human-metrics-runbook.md](birth-zero-human-metrics-runbook.md) — unattended SIM birth KPIs, freeze sacred path, campaign gates.  
**Self-play lab (ADR-0037 Phase 0):** [self-play-lab.md](self-play-lab.md) — frozen-window `tournament_score` ranking, default off, no REAL/apply.  
**Operator residuals OR1–OR6:** [operator-residuals-or1-or6.md](operator-residuals-or1-or6.md) · `python scripts/validation/operator_residuals_gate.py`.
