# 2026-05-29 — DNA Guardian v0.13.0 — Per-file Historical Tracking + Degradation Detection

**Increment of**: DNA Validation & Scoring Tool

## What was implemented
- Extended health history to also store per-file Truth Density scores for every scan.
- Added `detect_per_file_degradation()` function that identifies files that have been the weakest for multiple consecutive scans.
- Degradation warnings are now shown in:
  - Generated evolution log entries
  - Normal human-readable reports
- Version bumped to 0.13.0.

## Why this step
This is the core of Increment 2. Being able to see that one specific file is *structurally* the weakest over time is much more actionable than only looking at the overall score. It helps prioritize real, recurring problems in the DNA.

**Status**: Delivered. This completes the main goal of Increment 2.