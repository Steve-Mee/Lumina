# 2026-05-31 — Detailed Proposal: Hard Removal of B-001 (Final Elimination of the Last Active Trusted-Path Mechanism)

**Parent Documents**:
- `2026-05-31-elon-phase1-3-2-b001-final-resolution.md` (hypothesis)
- `2026-05-31-elon-phase1-3-2-deprecation-start.md` (deprecation window now active)
- Approved Phase 1.3.2 implementation plan

**Status**: This document is the concrete, executable proposal for the **hard removal** of B-001. It is written to serve as direct input for the next Plan Mode session.

---

## 1. Executive Summary (Elon Lens)

B-001 is the last remaining functional trusted-path bypass in the entire capital execution architecture.

We have successfully:
- Eliminated B-002, B-003, B-004 structurally.
- Removed the god-flag.
- Placed B-001 in a controlled, observable deprecation window with strong signaling.

The hard removal of the `skip_final_arbitration` parameter is the final structural act that makes the late authoritative Admission Chain + Final Arbitration the **only** effective path to the broker in strict modes.

This proposal describes exactly how to execute that removal safely, reversibly, and with maximum forcing function value.

---

## 2. Current State (Post Deprecation Start)

**Active mechanism**:
- `policy_engine.execute_order(..., skip_final_arbitration: bool = False)`

**When True is passed**:
- `enforce_no_bypass_in_strict_mode(B-001)` is called → fatal in `real` + `sim_real_guard`.
- Additional deprecation warning + ConstitutionViolation event (with `deprecated: true`).

**Call sites**:
- `operations_service.py` and `reasoning_service.py`: explicitly pass `False` (with 1.3.2 comments).

**Enforcement surface**:
- `aperture_guard.py` still lists B-001 as the only active entry.
- `BYPASS_POLICY_ENGINE_SKIP = "B-001"` constant still exists.

**Telemetry available**:
- Logs containing "DEPRECATED: skip_final_arbitration=True"
- `safety.constitution.violation` events with `deprecated: true` and `mechanism: "B-001"`.

---

## 3. Pre-requisites / Gates Before Hard Removal

We will **only** execute the hard removal when **all** of the following gates are green:

**Gate 1 – Telemetry (Mandatory)**
- Zero occurrences of `skip_final_arbitration=True` (in logs or events) in SIM + paper-guard for at least **14 consecutive days** under representative load.
- Zero ConstitutionViolation events with `deprecated: true` for B-001 in the same period.

**Gate 2 – Static Analysis**
- Full codebase search + review confirms no other production call sites pass `True` (beyond the two we already control).

**Gate 3 – Risk Review**
- Explicit sign-off from a fresh `risk-safety-review` + `constitution-guard` before the removal change set is merged.

**Gate 4 – Validation Readiness**
- Test plan and validation campaign prepared and reviewed.

If any of these gates are not met, we extend the deprecation window and increase visibility (e.g. stronger warnings, Guardian alerts).

---

## 4. Recommended Phasing of the Hard Removal

**One focused, high-signal change set** (not spread over multiple PRs), executed only after all gates are green.

### Phase A – Core Removal (Single Coherent Change)

**Files to change**:

1. **`lumina_core/engine/policy_engine.py`**
   - Remove the `skip_final_arbitration` parameter from the method signature.
   - Delete the entire `if bool(skip_final_arbitration):` deprecation block.
   - Delete the `if not bool(skip_final_arbitration):` guard.
   - Always execute the full gate logic.
   - Remove the `skip_final_arbitration` field from the final log statement.
   - Add a clear comment block explaining the removal and referencing this proposal + 1.3.2 entries.

2. **`lumina_core/engine/operations_service.py`**
   - Change the call to: `policy_engine.execute_order(order)` (remove the argument).
   - Update the comment.

3. **`lumina_core/engine/reasoning_service.py`**
   - Same as above.

4. **`lumina_core/risk/aperture_guard.py`**
   - Remove `"B-001"` from `BYPASS_IDS`.
   - Remove the constant `BYPASS_POLICY_ENGINE_SKIP`.
   - Update the module docstring and comments to reflect that B-001 has been permanently resolved.

5. **`tests/test_aperture_guard.py`**
   - Remove or heavily rewrite the B-001 specific tests.
   - Add a comment documenting the removal.

### Phase B – Documentation & Inventory (Immediate follow-up)

- Update `current-reality/evolutionary-debt.md`
- Update `current-reality/architecture.md` (if references remain)
- Final update of the bypass inventory (mark B-001 as "permanently removed – 2026-05-31")
- Consider a short closing note in relevant ADRs or a new summary entry.

---

## 5. Test & Validation Strategy

**Pre-removal**:
- Ensure the deprecation tests are still passing and actively exercised.

**During removal**:
- The existing contract tests for the admission chain and broker paths must continue to pass without the skip parameter.
- Add or update tests that explicitly prove that the old bypass path no longer exists (even if someone tries to call it).

**Post-removal validation campaign** (mandatory):
- Full regression in SIM + paper-guard with high agent load.
- Specific focus on paths that previously could have used the skip (reasoning-driven orders, supervisor orders).
- Emergency / force-close scenarios.
- Performance delta measurement of the now-always-running late check (input for optimization track).

---

## 6. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|----------|
| Undiscovered call site still passes the parameter | Low (after deprecation window) | High | Strict telemetry gates + static analysis before removal |
| Test or internal harness breaks | Medium | Low | Expected and included in the change set |
| Performance regression in supervisor loop | Medium | Medium | Measure during validation; accelerate gate optimization track if needed |
| Someone tries to re-introduce similar logic later | Medium | High | Strong documentation + the fact that the entire trusted-path pattern is now publicly dismantled and stigmatized |

---

## 7. Success Criteria (Hard Removal)

- The parameter `skip_final_arbitration` no longer exists in the `policy_engine.execute_order` signature.
- No remaining references to `BYPASS_POLICY_ENGINE_SKIP` or B-001 as an active mechanism in production code.
- All tests pass.
- Post-removal validation campaign completes with zero bypass attempts and acceptable performance characteristics.
- Bypass inventory updated to "0 active FATAL structural mechanisms".
- Public completion entry published that formally closes 1.3.2 and the structural removal chapter of the 2026-05-31 Elon aperture track.
- Clear transition plan to the remaining 1.3 work (especially documentation) or the gate optimization track.

---

## 8. Recommended Timeline & Decision Gates

1. **Now – Deprecation Window Active**
   - Strong monitoring (recommend: extend Guardian to surface B-001 deprecation usage prominently).

2. **Decision Gate** (when all four gates from section 3 are green)
   - Enter a new, focused Plan Mode session specifically for the hard removal change set (using this proposal as primary input).

3. **Execution**
   - One coherent change set (or very tightly coupled small PRs).
   - Immediate validation campaign.

4. **Closure**
   - Publish 1.3.2 final completion entry.
   - Update overall aperture status.

---

## 9. My Recommendation (First-Principles)

Execute the hard removal as soon as the telemetry gates are met — do **not** artificially wait the full 30-60 days if the data is already clean for 14+ days.

This aligns with the physics: once we have high-confidence evidence that the mechanism is no longer used, keeping it any longer only increases technical debt and attack surface without adding value.

Simultaneously (or immediately after), we should seriously activate the **parallel gate optimization track**, because "always run the full authoritative check" is now the permanent reality.

---

**This proposal is ready to be used as the primary input for the next Plan Mode session** when the telemetry gates are satisfied.

It is written to be executable, reviewable, and fully aligned with the Recursive Self-Improvement Protocol, the Trading Constitution, and the original Elon first-principles diagnosis.

**Ready when the data is ready.** 

Physics does not negotiate. When the evidence is clear, we remove the last piece of the old architecture cleanly and permanently.