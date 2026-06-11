# 2026-06-04 — Phase 3 D5.1: Constitution / invariant touch-point inventory

**Parent**: Phase 3 D5 plan (`phase_3_d5_constitution`); 05-31 deliverable 5.

## DNA consumers

| Consumer | Path | Role |
|----------|------|------|
| Guardian structural | `scripts/dna_guardian/validate_dna.py` | Requires `core/constitution.md`, `core/invariants.json` exist |
| Structural rules | `project-dna/lumina/operating-system/rules/structural.yaml` | Authoritative required paths |
| Validation rules | `project-dna/lumina/operating-system/dna-validation-rules.md` | Consistency with constitution/invariants |
| Agent export | `project-dna/lumina/interfaces/export/agent-context.md` | Human/agent forcing |
| MC | `aperture-hardening-mission-control.md` | D5 row tracking |
| Truth density | Guardian `generate_report` | Scores `core/constitution.md` |

## Runtime enforcement (unchanged by D5 DNA)

| Component | Path |
|-----------|------|
| Regression detector | `lumina_core/risk/aperture_guard.py` |
| Static bypass baseline | `project-dna/lumina/operating-system/rules/aperture.yaml` |
| Closed inventory | `evolution/log/2026-05-31-current-capital-aperture-bypass-inventory.md` |
| ADR | `docs/adr/0010-death-of-trusted-path-optimization.md` |

## Allowlisted residual references (not violations)

| File | Reason |
|------|--------|
| `lumina_core/risk/aperture_guard.py` | Detector comments (B-001..B-004) |
| `lumina_core/broker/broker_bridge.py` | B-004 legacy flag trap (logs, no short-circuit) |
| `lumina_core/engine/policy_engine.py` | Removal comment + metadata.pop hygiene |
| `lumina_core/trade_workers.py` | metadata.pop hygiene |
| `lumina_core/engine/runtime_state.py` | Removal comment |
| `lumina_core/trading_engine/engine_state_facade.py` | Removal comment |

## Hygiene (D5.1b)

- Removed stale `admission_chain_final_arbitration_approved` from `lumina_core/engine/lumina_engine.pyi` (type stub drift post 1.3.1).

## New D5 enforcement (D5.3+)

- `project-dna/lumina/operating-system/rules/capital-aperture-forbidden-patterns.yaml`
- `scripts/dna_guardian/capital_aperture_scan.py`
- Guardian fail-hard on scan + invariant alignment
