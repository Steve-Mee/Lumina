# 2026-05-31 — Current Capital Aperture Bypass Inventory (Machine-Actionable)

**Parent**: `2026-05-31-elon-musk-first-principles-trading-system-analysis.md`  
**Purpose**: Explicit, file:line, severity-graded list of every known structural bypass / erosion point in the only paths that can touch capital. This is the baseline that Phase 0 Guardian aperture checks and all future hardening must drive to zero.  
**Status at execution start**: Live baseline. Any change to this file requires a new evolution entry superseding it.

**Classification**: This inventory itself is documentation. Any attempt to "fix" items below must follow full Recursive Self-Improvement Protocol + fresh Plan Mode + constitution-guard + risk-safety-review.

---

## Tier FATAL (Can directly cause unauthorized REAL capital exposure)

| ID | File:Line | Mechanism | How it bypasses | Current Controls (weak) | Evidence Source |
|----|-----------|-----------|-----------------|-------------------------|-----------------|
| B-001 | `lumina_core/engine/policy_engine.py:70-106` | `skip_final_arbitration: bool = False` param + early return | If caller sets True (or engine flag is True), skips the entire `enforce_pre_trade_gate` call before calling broker.submit_order | Only the caller deciding not to set the flag | Static analysis + execution flow in operations_service.py:304 and reasoning_service.py:261 |
| B-002 | `lumina_core/engine/operations_service.py:304` | `skip_final_arbitration = bool(getattr(self.engine, "admission_chain_final_arbitration_approved", False))` | Reads mutable god-state flag on the engine object and passes it to policy_engine | None — any code with access to self.engine can set the attribute | Direct code |
| B-003 | `lumina_core/engine/reasoning_service.py:261` | Same mutable flag pattern as B-002 | Same bypass path from reasoning layer | None | Direct code |
| B-004 | `lumina_core/broker/broker_bridge.py:129` | `if bool(metadata.get("skip_admission_chain_recheck", False))` early return inside `_run_final_arbitration` | Even if broker.submit_order is called, this short-circuits the re-check that PaperBroker / CrossTradeBroker do | Only that the metadata key is not set by "good" callers | Direct code + the fact that policy_engine sets this key at line 106 after skipping |

**Notes on FATAL tier**:
- These four locations form a connected "trusted path" optimization that can completely avoid Final Arbitration + Constitution + full Admission Chain in certain call sequences.
- The existence of a mutable attribute on the shared engine object (`admission_chain_final_arbitration_approved`) that controls safety is a first-principles anti-pattern.

---

## Tier HIGH (Significant erosion of observability / contract strength)

| ID | File:Line / Area | Mechanism | Impact | Evidence |
|----|------------------|-----------|--------|----------|
| B-005 | `lumina_core/agent_orchestration/event_bus.py:68` (`DomainEvent.payload: dict[str, Any]`) + limited `publish` call sites | Core bus still delivers dicts even after validation. Only ~6 visible publish sites across entire lumina_core for the "central" bus. | No universal typed provenance spine. Most agent coordination still happens via blackboard dicts and direct attribute access. | Grep for `\.publish` / `publish_validated`; DomainEvent definition |
| B-006 | Multiple dream_snapshot / blackboard accesses in runtime_workers.py, operations_service.py, order_gatekeeper.py (dict-heavy) | Critical pre-trade "current truth" (confluence, regime, stop/target, proposed_risk) flows as untyped dicts | Any corruption or missing key silently falls back; no schema enforcement at source | Multiple `.get("...", fallback)` patterns |
| B-007 | `lumina_core/runtime_workers.py:1196, 1272` and EOD force-close paths | Direct `Order(...)` construction + broker.submit_order with incomplete metadata in some branches | Metadata hygiene varies; some paths have no `proposed_risk` / `confluence_score` | Code inspection |

---

## Tier MEDIUM (Pragmatic debt that increases cognitive load & future leak surface)

| ID | Area | Description |
|----|------|-------------|
| B-008 | `lumina_core/engine/lumina_engine.py` + `meta_agent_core.py` (large) | Still concentrate too much knowledge about execution + evolution state. Hard to reason about aperture without understanding the whole object graph. |
| B-009 | Historical reset culture + state shape | Repeated full-state nuclear options instead of forward-compatible migrations make it harder to have confidence that hardening changes won't require resets. |

---

## How This Inventory Must Be Used (Non-Negotiable)

1. **Guardian Phase 0 extension** must parse or hardcode this inventory and emit active degradation warnings + counts until every FATAL item is structurally closed.
2. Every new evolution entry that touches risk, execution, or agent orchestration must explicitly state: "Impact on aperture bypass inventory: none / reduces B-XXX / introduces new risk".
3. The 90-day success criteria (Aperture Integrity Score, zero FATAL bypasses in guard modes) are measured against this baseline.
4. When an item is closed, a new superseding inventory entry is created with the date and proof (test + Guardian run + evolution log reference).

**Status after Phase 1.3.2 (2026-05-31)**:
- B-001 (`skip_final_arbitration` in policy_engine) is now in **controlled final deprecation** (Phase 1.3.2).
  - Use triggers loud warnings + ConstitutionViolation events.
  - Fatal in strict modes (via aperture_guard) — status quo safety net.
- All other FATAL structural mechanisms (B-002, B-003, B-004) and the god-flag have been eliminated in previous phases.
- HIGH: 3
- MEDIUM: 2

**Progress note**: B-001, the last remaining active trusted-path mechanism from the original 2026-05-31 diagnosis, is now in its final deprecation window before permanent removal.

**Target for Day 30 gate**: Use telemetry from enforcement to begin safe removal (Phase 1.2 — requires new Plan Mode). FATAL effective risk significantly reduced even if structural count remains until removal.

**Next update to this inventory only via new evolution entry after Phase 1.2 removal work.**

---

*This inventory is the single source of truth for "what the 2026-05-31 Elon analysis actually means in code coordinates". It will be updated only via public evolution entries.*

**Execution start baseline captured**: 2026-05-30 (Guardian report + this file + agent-context.md update + debt.md update). 

Next: Phase 0 Guardian aperture detection that references this inventory.

---

**Protocol adherence (2026-06-11 hygiene backfill)**

**Hypothesis**: This classified entry documents a bounded change that preserves capital-path invariants when gates stay green.

**Prediction (30d)**: Relevant pytest/Guardian gates remain pass; no new FATAL aperture findings.

**Rollback**: Revert the files named in the Executed/Changes section of this log; add a superseding evolution entry if behavior changes.

