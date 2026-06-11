# 2026-05-29 — DNA Guardian v0.2.0 — Basic Truth Density Heuristics Added

**Increment of**: DNA Validation & Scoring Tool

## What changed
- Added first working Truth Density heuristics in `calculate_truth_density()`.
- Heuristics currently include:
  - Penalty for vague language (should, aims to, as much as possible, etc.)
  - Reward for presence of strong markers (hypothesis, falsifiable, prediction, evidence, metric, score)
  - Light penalty for overly long files lacking structure
- Integrated scoring into both Markdown and JSON reports.
- Updated 4 key files for scoring: constitution.md, self-improvement-protocol.md, truth-metrics.md, evolutionary-debt.md.
- Current average on these files: **7.83/10**

## Alignment with proposal
This directly implements the second planned small step after structural validation, moving the tool from "checker" toward "scorer".

## Next planned increments
- Persist reports to `evolution/log/`
- Improve heuristics (more sophisticated vague language detection, length normalization, etc.)
- Add scoring for more files

**Status**: Delivered and tested. Follows small, incremental, documented approach.