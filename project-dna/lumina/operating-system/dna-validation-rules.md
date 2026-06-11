# DNA Validation Rules (v1)

This document defines the rules used by the DNA Guardian tool (`scripts/dna_guardian/validate_dna.py`).

## 1. Structural Validation Rules

The authoritative list of required paths is maintained in `operating-system/rules/structural.yaml`.

The following must exist under `project-dna/lumina/`:

### Core Layer (non-negotiable)
- `core/constitution.md`
- `core/north-star.md`
- `core/invariants.json`

### Operating System Layer
- `operating-system/self-improvement-protocol.md`
- `operating-system/truth-metrics.md`
- `operating-system/decision-framework.md`
- `operating-system/anti-patterns.md`
- `operating-system/dna-validation-rules.md` (this file)

### Current Reality Layer
- `current-reality/architecture.md`
- `current-reality/evolutionary-debt.md`

### Interfaces Layer
- `interfaces/README.md`
- `interfaces/export/agent-context.md`

### Evolution Layer
- `evolution-log.md` (summary file at lumina root)
- `evolution/log/` (directory containing structured entries)
- `evolution/experiments/` (directory)

## 2. Truth Density Heuristics (v1)

The concrete heuristics are **externalized** in:
- `operating-system/rules/truth-density.yaml` (vague_words, positive_markers, scoring_parameters)

Basic principles (0-10 scale):

- **Information Density**: Long sections with few concrete statements lower the score.
- **Vague Language**: Words like "should", "aims to", "as much as possible" without measurable criteria reduce the score.
- **Missing Hypotheses**: Claims about future improvement without a falsifiable prediction lower the score.
- **Consistency with Constitution**: Direct contradictions with `core/constitution.md` or `core/invariants.json` are critical failures.
- **Agent Usability**: Content that is unnecessarily verbose for an agent reading it in one prompt reduces the score.

## 2b. Phase 3 D5 — Capital aperture constitution enforcement (2026-06-04)

On every Guardian run (`validate_dna.py --report` or default):

1. **Invariant alignment**: `core/invariants.json` must contain `no_structural_bypass_capital_paths` with `severity: fatal`.
2. **Constitution cross-reference**: `core/constitution.md` must reference structural bypass prohibition (anchor: `no_structural_bypass_capital_paths` or `no structural bypass`).
3. **Static scan**: `scripts/dna_guardian/capital_aperture_scan.py` scans `lumina_core/**/*.py` against `operating-system/rules/capital-aperture-forbidden-patterns.yaml`. Any match outside allowlisted paths **fails the run** (non-zero exit).

This makes Phase 3 deliverable 5 (near-immutable no-bypass rule) a daily forcing function alongside `aperture.yaml` and `aperture_guard.py`.

## 2c. Phase 3 D6 — Guardian self-score (2026-06-04)

Each Guardian run attaches `guardian_self_score` to the JSON report (heuristic weighted score across structural DNA, aperture integrity, D5, D3 forcing panel, D4 bundle surface, D1 ctx pool). See `operating-system/rules/guardian-self-score-contract.yaml`.

- Default: print D6 section; warn if overall self-score < 8.0.
- `--strict-self-score`: exit non-zero if self-score < 6.0.

The DNA Guardian (`scripts/dna_guardian/validate_dna.py`) loads these rules with safe fallback. LLM-assisted / hybrid scoring is planned for a later increment (see dna-guardian-roadmap.md).

## 3. Reporting Requirements

Every run of the tool must produce:
- A human-readable Markdown report
- A machine-readable JSON summary
- Optional: A suggested entry for `evolution/log/`

## 4. Versioning

This rules file follows semantic versioning for the validation logic.
Changes to this file that affect scoring or validation must be logged as meta-improvements.

---

*Initial version created as part of the DNA Validation & Scoring Tool introduction (2026-05-29).*

**Updates**:
- 2026-05-29: External rules location documented (structural.yaml + truth-density.yaml). Heuristics are no longer hardcoded in the Guardian.