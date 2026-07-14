# ADR-0031: ApprovalTwinAgent on Central Event Bus + Primary Auto-Approval

**Status**: Accepted (2026-07-13)

**Context**
ApprovalTwin (RLHF-light from SteveValues) existed and was used in evolution gates/guard, but decisions were not published as typed events to the canonical EventBus and were not explicitly the default auto-approver in birth/SIM promotion paths or meta/plateau/remediation.

**Decision**
- Add TwinDecisionEvent + TwinTrainingUpdateEvent (extra=allow) to schemas + register "evolution.twin.*" topics.
- TwinAgent accepts optional EventBus and publishes on every evaluate_* / rlhf (best-effort, non-breaking).
- Wire via existing orchestrator bind + container.
- Treat twin recommendation (when clean + >= internal threshold) as primary auto-approval signal for birth/SIM; REAL remains gated by PromotionGate + shadow + guard.
- Add proactive evaluate calls (synthetic/minimal DNA proxies) in birth meta_controller, plateau, remediation, autonomy, dna_handoff — all optional + best effort.
- Tests extend existing patterns; events visible to subscribers + audit.

**Consequences**
- Twin decisions now appear on EventBus (success metric met).
- Increased autonomy in SIM/birth with typed audit trail.
- No change to hard REAL gates or constitution boundaries.
- Radically simple: no new gods, reuse bus/schemas/PolicyDNA.

See plan in session + changes in approval_twin_agent, schemas, guard/policy, birth/*.

---

## Training the Twin (2026-07-13 follow-up)

The ApprovalTwin learns what Steve would decide via explicit labels.

**Working training path (radical simple CLI):**
```
python -m lumina_launcher twin review --limit 5
# shows recent decisions (monitoring_twin_decisions.jsonl)
# user answers A / V → creates SteveValueRecord → rlhf_light_update
python -m lumina_launcher twin train
python -m lumina_launcher twin metrics
```

After training:
- `avg_prediction_error`, `reward`, `training_steps` are printed, written to monitoring jsonl, emitted on bus (TwinTrainingUpdateEvent), and visible in `/api/monitoring/metrics/json` under `_lumina_ui`.
- Dashboard shows reward + err + steps.
- Calibrated confidence (shrinks when error high) is returned by evaluate and used as default gate in birth autonomy loops.

**Richer mimicry:** `_features_from_*` now incorporate emotional_twin_profile + lineage_hash signals + more Steve vocabulary. Weights learn Steve's values directly from registry.

High-confidence twin decisions (`confidence >= 0.80 + recommendation + clean`) make the twin the default in `organism_autonomy` (no human needed). Hard guards (constitution, risk shadow, promotion gate) are never bypassed.

See: lumina_core/evolution/approval_twin_agent.py (docstring + _calibrate), lumina_launcher/twin_cli.py, birth/organism_autonomy.py, lumina_os/api/monitoring.py + frontend.
