# 2026-05-29 — Introduction of DNA Validation & Scoring Tool (DNA Guardian)

**Impact Classification**: Medium

## Hypothesis + Falsifiable Predictions

**Hypothesis**:
The DNA 2.0 layered structure is a significant improvement, but lacks an active mechanism to guard and measure its own quality. Introducing a lightweight "DNA Validation & Scoring Tool" will increase the truth density and evolvability of the Project DNA by making weaknesses visible early and providing objective feedback on meta-changes.

**Falsifiable Predictions**:
- Within 60 days: Average Truth Density score of files under `project-dna/lumina/` rises from ~6.5 to ≥ 8.0 (measured via the tool + human review).
- Within 90 days: At least 70% of meta-improvements logged in `evolution/log/` contain an explicit reference to output from the DNA Validation Tool.
- Within 180 days: The Evolvability Score of the DNA (as defined in `truth-metrics.md`) increases by at least 1.5 points compared to the immediate post-DNA-2.0 baseline.
- Within 12 months: Concrete cases exist where the tool detected DNA weaknesses that would otherwise have gone unnoticed or been discovered much later.

## What is being implemented

A new tool under the name **DNA Guardian** (initial implementation: `scripts/dna_guardian/validate_dna.py`).

Core capabilities in v1 (intentionally limited):
- Structural validation of the DNA 2.0 directory layout and required files.
- Basic Truth Density heuristics (with clear, auditable rules).
- Generation of a structured report (Markdown + JSON).
- CLI interface for easy local use.
- Accompanying rules document: `operating-system/dna-validation-rules.md`.

The tool will be built iteratively in small steps, with each meaningful increment logged as a separate meta-improvement.

## Alignment with DNA 2.0

- Directly operationalizes `operating-system/truth-metrics.md`.
- Enforces and protects the structure defined in `core/`.
- Lives in the `operating-system/` layer as a self-improvement mechanism.
- Will write reports into `evolution/log/` to create a feedback loop.

## Evolvability Impact

This addition is expected to meaningfully increase the long-term evolvability of Lumina by:
- Making the quality of the DNA itself observable and improvable.
- Raising the standard for future meta-changes.
- Providing data that future meta-agents (and humans) can use to prioritize DNA improvements.

## Reversibility

Fully reversible:
- The tool is additive; removing it has no structural impact on the DNA.
- All generated reports remain in `evolution/log/`, preserving knowledge.
- Backups of the pre-tool state exist from the DNA 2.0 redesign.

## Protocol Compliance

This change is being executed according to the Recursive Self-Improvement Protocol v2.0:
- Started with a full proposal containing hypothesis and predictions.
- This log entry serves as the formal record.
- Implementation will proceed in small, documented increments.
- Extra checks (constitution-guard / risk-safety-review) are not required as this touches only meta-governance tooling.

**Status**: Implementation started immediately after approval on 2026-05-29.