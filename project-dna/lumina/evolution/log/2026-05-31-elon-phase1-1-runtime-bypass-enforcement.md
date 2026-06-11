# 2026-05-31 — Phase 1.1: Runtime Enforcement of Known Capital Aperture Bypasses (Make the Leaks Scream)

**Parent Analysis**: `2026-05-31-elon-musk-first-principles-trading-system-analysis.md`  
**Approved Plan**: `plan.md` (session 019e7482-...) — Option A ("Make the Leaks Scream First")  
**Impact Class**: Medium (adds runtime enforcement + observability on existing bypass paths; does not yet remove the mechanisms)  
**Protocol**: This entry is the required formal record before any implementation code is written.

---

## Hypothesis

By adding a small, centralized, mode-aware enforcement helper (`aperture_guard`) that is called at the four known FATAL bypass entry points, and making bypass usage in `real` + `sim_real_guard` modes raise `LuminaError(FATAL_MODE_VIOLATION)` + emit a `ConstitutionViolation` event on the typed Event Bus, we will:

- Immediately convert silent structural erosion into loud, measurable, failing pressure inside the system.
- Generate real telemetry on how often these "optimization" paths are actually exercised.
- Raise the live Aperture Integrity Score from 2.0/10 toward 5.0+/10 without a large risky refactor in the first slice.
- Create the necessary forcing function and data to safely remove the bypass mechanisms in subsequent slices (Phase 1.2+).

This is the smallest step that turns the 2026-05-31 diagnosis into active physics inside the running system.

**Falsifiable Predictions (30 / 60 / 90 days)**:

- **30 days (end of this increment)**: Guardian Aperture Integrity Score ≥ 5.0 (up from 2.0). At least one `safety.constitution.violation` event with a `bypass_*` principle appears during normal SIM + paper-guard test campaigns. Zero unintended FATALs in clean regression runs.
- **60 days**: The telemetry from this enforcement layer has been used to safely remove or neutralize at least two of the four FATAL mechanisms (or reduce their effective usage to near-zero in strict modes).
- **90 days**: No remaining structural bypass usage in REAL or sim_real_guard modes in any production-like run. Aperture Integrity Score ≥ 8.5. The bypass inventory has been superseded with all four items marked "enforced then removed".

**Measurement**: Guardian aperture scoring (extended to also count recent violation events) + structured error logs + Event Bus history for the `safety.constitution.violation` topic.

---

## Evolvability Impact

**Current estimated Evolvability of the risk/aperture layer**: ~7.0–7.5 (islands of excellence + hidden escape hatches).

**Expected delta from this increment**: +0.8 to +1.2 points.

**Why**:
- Makes the cost of the current pragmatic shortcuts explicit and painful → future developers/agents are strongly incentivized to remove them rather than add more.
- Adds the first live order-path ConstitutionViolation events on the bus → improves decision provenance and meta-agent observability.
- Creates a reusable, small enforcement pattern that can be applied to other aperture erosion areas later.

**Risk to evolvability**: Low. The new module is deliberately tiny and lives in the correct bounded context (`risk/`).

---

## Reversibility & Rollback

- Extremely high in the first 4–6 weeks: the enforcement calls can be made warning-only via a single mode/flag change, or the calls themselves can be commented out / feature-flagged.
- The new `aperture_guard.py` is purely additive; deleting the file + 4 call sites reverts the system to the exact pre-increment state.
- All new events and errors are append-only (structured logs + Event Bus history) — no state corruption risk on rollback.

Rollback trigger: Any production incident in paper-guard or REAL caused by the new enforcement during the validation campaign.

---

## Conflict Resolution (if needed)

If legitimate "we already checked" paths in SIM are being incorrectly hit:
- Phase 1.1 design explicitly starts with **warning-only in pure SIM and paper**, fatal only in `real` + `sim_real_guard`.
- Telemetry will be collected for 2–4 weeks before any tightening.

If the Event Bus publish for ConstitutionViolation adds unacceptable latency (unlikely):
- The publish is wrapped in best-effort try/except. The hard fail-closed behavior is driven by the `LuminaError` raise, not the event.

---

## Design Summary (Approved Option A)

- New small module: `lumina_core/risk/aperture_guard.py` (< 150 LOC).
- One function `enforce_no_bypass_in_strict_mode(...)` that:
  - Resolves mode.
  - In strict modes (`real`, `sim_real_guard`): raises `LuminaError(FATAL_MODE_VIOLATION)` + emits `ConstitutionViolation` on bus + structured log.
  - In non-strict modes: extremely loud warning.
- 4 minimal call sites at the earliest point in each known bypass path.
- Reuses existing patterns (`fault_policy.py` conditional fatal + `promotion_policy.py` bus emission).
- Full test coverage using existing contract test style.

Full details are in the approved Plan Mode document.

---

## Next Steps (Protocol-Compliant)

1. Implementation of `aperture_guard.py` + tests (reviewed with `constitution-guard`, `risk-safety-review`, `event-bus-contract`).
2. Addition of the 4 call sites (same reviews).
3. Light Guardian extension to consume the new violation events.
4. Heavy SIM + paper-guard validation.
5. Superseding bypass inventory entry + Phase 1.1 completion log with updated Guardian numbers.

**This increment does not remove any bypass logic.** It only makes continued use of the known defects actively painful and observable in the modes that matter most. Removal work is explicitly deferred to subsequent slices after data is collected.

---

*Medium impact change recorded per Recursive Self-Improvement Protocol v2.0. Plan Mode completed and approved prior to any code. Focus remains: turn the capital aperture into a true, narrow, un-bypassable fort that accelerates safe self-evolution.*

**Hypothesis locked. Execution of Phase 1.1 can now begin.**