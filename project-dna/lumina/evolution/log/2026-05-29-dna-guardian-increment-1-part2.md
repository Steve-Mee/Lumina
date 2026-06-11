# 2026-05-29 — DNA Guardian Increment 1 (Part 2): Externalized Truth Density Heuristics

**Part of Increment 1**: Externaliseer scoring rules + maak configureerbaar

## What was done
- The `VAGUE_WORDS` and `POSITIVE_MARKERS` lists have been moved out of the main code into `operating-system/rules/truth-density.yaml`.
- `scripts/dna_guardian/rules.py` was extended with `get_vague_words()` and `get_positive_markers()`.
- `validate_dna.py` now loads these lists from the external file (with safe fallback to the previous hardcoded values).
- The tool continues to function identically for end users.

## Impact
This completes the first major part of making the DNA Guardian's rules fully external and versionable. Future changes to scoring heuristics no longer require modifying the core validation logic.

## Status
Increment 1 is now substantially complete for the current heuristic-based scoring.

Next logical work (still within the spirit of Increment 1 or as a direct follow-up):
- Improve the loader to also expose the `scoring_parameters` from truth-density.yaml (currently not yet used in code).
- Start moving the actual scoring formula / parameters out of the function into the rules file.