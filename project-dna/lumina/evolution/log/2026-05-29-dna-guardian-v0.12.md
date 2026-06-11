# 2026-05-29 — DNA Guardian v0.12.0 — Longer-term Trend Summary

**Increment of**: DNA Validation & Scoring Tool

## What was implemented
- Added `get_longer_trend_summary()` that produces a clear sentence about the trend over the last ~8 scans.
- The longer-term trend is now included in generated evolution log entries under "**Longer-term Trend**".
- Also propagated into the compact agent-context summary when available.
- Version bumped to 0.12.0.

## Why this step
Seeing only the very recent 2-5 point trend is useful for short-term monitoring. A slightly longer view ("over the last 8 scans") gives better signal on whether the DNA quality is sustainably improving or slowly eroding — exactly the kind of insight needed for healthy long-term self-evolution.

**Status**: Delivered. Clean, high-value increment.