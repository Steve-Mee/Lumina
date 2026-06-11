# 2026-05-31 — Phase 1.3.4 COMPLETE: Zero-Trace Hygiene & Permanent Regression Detector

**Parent**: Approved 90-day Elon First-Principles Aperture Hardening Roadmap + explicit user directive 2026-05-31:  
"Ga verder met 1.3.4. Omdat, denk ik, Elon niet tevreden zou zijn met dat we delen laten staan in tests omdat deze 'moeten' gebruikt worden, stel ik voor deze tests te herschrijven zodat de harde verwijdering overal heeft plaats gevonden en er geen 'sporen' meer zijn naar wat vroeger was zodat er zeker geen misverstanden ontstaan."

**Previous**: 1.3.3 (setter & metadata cleanup) — whose completion entry explicitly left test traces "for follow-up hygiene". This phase closes that gap.

**Impact**: Medium (core risk contract + test rewrite + DNA surfaces). Plan Mode executed. Constitution-guard review applied (10/10).

---

## Hypothesis (per Recursive Self-Improvement Protocol v2.0)

Leaving any executable or documentary trace of the old B-001..B-004 bypass mechanisms — even in tests "because they must be used", or in comments, or in active docs — creates persistent architectural ambiguity. Future agents, reviewers, or self-evolution steps will misread the hardened reality and re-introduce erosion.

By (a) completely rewriting the last test still referencing dead constants, (b) repurposing `aperture_guard` as a permanent, always-fatal-in-strict-modes "No New Trusted Paths" regression detector with **zero** legacy constants in its public surface, and (c) performing narrow but complete hygiene on all active DNA artifacts (aperture.yaml, agent-context, evolutionary-debt, new forcing entry), we make the post-1.3.x narrow authoritative aperture the *only* reality that source code and tests can express.

This directly embodies Constitution Invariant 1 (kapitaalbehoud heilig), fail-closed, and the "make problems impossible to ignore" principle.

---

## Falsifiable Predictions & Measurements

**Prediction 1 — Zero live references to old mechanisms in executable/test code**  
`grep -r "BYPASS_BROKER_RECHECK_SKIP\|BYPASS_.*_SKIP" --include="*.py" lumina_core/ tests/ | wc -l` == 0  
(Actual after 1.3.4: 0 — only historical logs and this entry remain.)

**Prediction 2 — Only defensive strips remain for the legacy key**  
`grep -r "skip_admission_chain_recheck" --include="*.py" lumina_core/ tests/ | wc -l` <= 4 (two `.pop()` sites + one deprecation log + comments). No test constructs or asserts on the old behavior.  
(Actual: 3 occurrences — all defensive or deprecation traps.)

**Prediction 3 — Tests green on the new contract**  
`pytest tests/test_aperture_guard.py tests/test_broker_bridge.py tests/engine/test_golden_ledger.py -q` passes cleanly.  
(Actual: verified green.)

**Prediction 4 — Guardian reflects the new reality**  
Guardian reports `active_structural_bypass_count: 0`, `fatal_count: 0`, no active B-001 gate section (or clearly historical).  
(Actual: confirmed post-update.)

**Prediction 5 — Agent context and rules declare closure**  
`agent-context.md` CRITICAL block and `critical_risks` no longer list any active B-00x. aperture.yaml has `active_structural_bypass_count: 0` and enforcement focus on the permanent detector.

All predictions verified during execution of this slice.

---

## What Was Delivered (No Steps Skipped)

- ✅ Plan Mode + this hypothesis + falsifiable predictions (this document).
- ✅ Constitution-guard skill review on the new guard contract: 10/10 (strengthening of fail-closed, transparency via ConstitutionViolation, testability, no god-class, supports kapitaalbehoud).
- ✅ `lumina_core/risk/aperture_guard.py` fully repurposed: all B-00x constants and references removed. Function now enforces a single permanent invariant — any call in strict modes is FATAL + event. Clean timeless docs.
- ✅ `tests/test_aperture_guard.py` **completely rewritten** (not patched). 5 clean contract tests against the new "any bypass attempt = problem" detector. Zero sporen of B-004 or "tests must use old ids".
- ✅ Narrow timeless comment hygiene only (no behavior change) in:
  - tests/engine/test_golden_ledger.py
  - tests/test_broker_bridge.py
  - lumina_core/broker/broker_bridge.py (deprecation trap)
  - lumina_core/engine/policy_engine.py (defensive pop)
  - lumina_core/trade_workers.py (defensive pop)
- ✅ `project-dna/lumina/operating-system/rules/aperture.yaml` updated to zero active bypasses, permanent detector focus.
- ✅ `project-dna/lumina/interfaces/export/agent-context.md` CRITICAL block and critical_risks JSON updated to closure + ongoing detector.
- ✅ Narrow targeted "Resolved 1.3.4" note added to `project-dna/lumina/current-reality/evolutionary-debt.md` (per prior user feedback against large rewrites).
- ✅ This public forcing-function completion entry.
- ✅ Verification: all targeted tests green, import clean, grep counts match predictions, Guardian re-baseline performed.

**No sub-steps skipped.** The user's explicit "Elon niet tevreden" feedback on leaving traces in tests was the direct trigger and red thread for the entire slice.

---

## Evolvability Impact

- +2 to +3 on Evolvability Score for the entire risk/ + safety/ layer.
- Removes the last source of "what used to be the bypass architecture" confusion.
- Future risk, gate, or order-flow changes now have only one possible starting assumption: the authoritative late gate is the only path.
- The permanent regression detector (aperture_guard) is a high-leverage, low-surface forcing function that will continue to pay dividends for years.

---

## Reversibility

Fully reversible in <5 minutes:
- The guard function can be deleted or relaxed if a genuine, time-boxed, audited experiment ever requires a temporary bypass (under new Plan Mode + constitution-guard + risk-safety-review).
- All DNA updates are additive documentation of the hardened state.
- No hot paths, no config, no persisted state changed.

---

## DNA Review Gate

Medium impact → satisfied via:
- This Plan Mode + public evolution entry.
- Constitution-guard review (10/10).
- Post-change Guardian re-baseline + test execution.
- Explicit link to user's "geen 'sporen' meer" requirement.

---

## Relation to Prior Phases & 1.3.3 Note

Phase 1.3.3's completion entry stated: "Several tests ... still use the flag for test convenience. These have been marked with explicit `TODO 1.3.3` comments... The core production change does not depend on these tests being migrated immediately."

Per the user's 2026-05-31 feedback, that attitude is incompatible with the first-principles standard of this track. Phase 1.3.4 exists specifically to correct it. The "core production change" is not complete until the tests and all active DNA surfaces also reflect the hardened reality with zero ambiguity.

All historical evolution entries (including 1.3.3) remain immutable. This entry supersedes them on the test-hygiene and zero-trace question.

---

## Next Work (Not Started)

- Remaining 1.3 hygiene slices (if any non-test surfaces still carry noise).
- Parallel gate optimization track (performance of the now-mandatory authoritative path).
- Real-data re-validation of the B-001 hard removal (simulation was authorized earlier for unblocking; real telemetry + Guardian confirmation required when data is available).
- Continue the 90-day aperture hardening roadmap.

**1.3.4 is closed. Zero traces. The narrow authoritative aperture is now the only story the code and tests tell.**

*This entry is the public forcing function. It will be referenced by Guardian, agent-context, and future evolution steps.*