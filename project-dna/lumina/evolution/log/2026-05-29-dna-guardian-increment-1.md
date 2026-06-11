# 2026-05-29 — DNA Guardian Increment 1: Externalized Structural Rules

**Increment**: 1 of the DNA Guardian Roadmap  
**Version bump**: 0.12.0 → 0.13.0 (internal)

## Hypothesis
Moving the list of required files for structural validation out of the Python source code and into a machine-readable file (`operating-system/rules/structural.yaml`) will make the tool easier to maintain, extend, and audit over time. This is a foundational step toward fully external, versioned rules.

## What was changed
- Created directory `project-dna/lumina/operating-system/rules/`
- Created `rules/structural.yaml` containing the complete list of required paths for DNA 2.0 (with metadata).
- Created `rules/truth-density.yaml` (prepared the structure for the next increments).
- Added `scripts/dna_guardian/rules.py` — a small loader that can read the structural rules.
- Updated `validate_dna.py` to prefer the external structural list, with a safe fallback to the previous hardcoded list (for robustness during transition).
- The tool remains fully functional even if the new rules files are missing or pyyaml is not installed.

## Impact on Evolvability
This change significantly improves the maintainability and extensibility of the DNA Guardian. Future changes to the required DNA structure no longer require touching the main validation logic.

## Reversibility
Fully reversible in this increment:
- The fallback logic ensures the tool behaves exactly as before if the new files are removed.
- No behavior change for normal usage.

## Protocol Compliance
This meta-improvement was executed as a small, documented, reversible step following the Recursive Self-Improvement Protocol.

**Status**: Delivered. Clean first increment with minimal risk.