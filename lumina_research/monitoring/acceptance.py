"""Steve's Phase 4 binding acceptance floors (ADR-0058 addendum, 2026-10-28)."""

from __future__ import annotations

# Mutation testing of lumina_research/monitoring (320+ mutants, same harness).
MUTATION_MIN_MUTANTS = 320
MUTATION_KILL_RATE_MIN = 0.80
MUTATION_EQUIVALENT_MAX_FRAC = 0.10

# Multi-seed campaign (300 signals, 10 seeds), measured per kind.
CAMPAIGN_MIN_SIGNALS = 300
CAMPAIGN_MIN_SEEDS = 10
FAR_HEALTHY_MAX = 0.05
FAR_HIGH_VOL_MAX = 0.10
DETECTION_RATE_MIN = 0.85
TTD_MAX_TRADING_DAYS = 15

# Two consecutive ready windows must agree before a stage is applied.
CONFIRM_WINDOWS = 2

# Gradual synthetic paths reach a full 2.8σ mean shift in this many days after onset.
MEANINGFUL_RAMP_DAYS = 12
