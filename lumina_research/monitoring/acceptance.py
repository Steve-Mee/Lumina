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

# Phase 5 addendum (2026-10-28). Additive. Does not loosen the Phase 4 constants above.
# Short-horizon TTD_MAX_TRADING_DAYS=15 and FAR_HIGH_VOL_MAX=0.10 stay the hard floors.
# 12% high-vol FAR is an absolute extreme tolerance, never a pass.
TTD_MEDIUM_MAX_TRADING_DAYS = 45
TTD_MEDIUM_TARGET_TRADING_DAYS = 40
FAR_HIGH_VOL_TARGET = 0.08
FAR_HIGH_VOL_EXTREME_NOT_A_PASS = 0.12
MEDIUM_WINDOW = 40
MATERIAL_IC_RATIO = 0.50
MATERIAL_SHARPE_RATIO = 0.50
MATERIAL_DD_MULT = 1.50
HIGH_VOL_VIX = 25.0
HIGH_VOL_TRAILING_PCT = 0.75
HIGH_VOL_REALIZED_MULT = 1.50
HIGH_VOL_REALIZED_WINDOW = 20
HIGH_VOL_TRAILING_WINDOW = 252
