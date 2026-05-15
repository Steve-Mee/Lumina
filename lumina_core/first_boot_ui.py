"""First-boot UI helpers: trade-count → estimated real-history days (launcher/runtime).

Kept Streamlit-free so pytest can import without initializing the launcher.
"""

from __future__ import annotations

import math

# Aligns with InfiniteSimulator first-boot capacity heuristic (~trades per calendar day of real data).
FIRST_BOOT_EST_TRADES_PER_REAL_DAY = 2500
# Prompt: very high trade counts imply ~800+ days; surface an extra operator warning above this band.
FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS = 700

# Bounds for user-configurable first-boot volume (launcher + YAML). Values are clamped here only;
# we do not snap to coarse steps — the stored number matches what the user asked for within bounds.
FIRST_BOOT_TRAINING_TRADES_MIN = 500
FIRST_BOOT_TRAINING_TRADES_MAX = 2_000_000
# Suggested granularity in the launcher number_input only (does not rewrite saved values).
FIRST_BOOT_LAUNCHER_TRADE_STEP = 500

# Default when config omits `first_boot.training_trades` entirely (explicit YAML always wins via normalize input).
FIRST_BOOT_DEFAULT_TRADES = 5_000
FIRST_BOOT_DEFAULT_MAX_REAL_DAYS = 90

# Back-compat names used in older snippets / docs — map to launcher-aligned bounds above.
FIRST_BOOT_TRADE_MIN = FIRST_BOOT_TRAINING_TRADES_MIN
FIRST_BOOT_TRADE_MAX = FIRST_BOOT_TRAINING_TRADES_MAX
FIRST_BOOT_TRADE_STEP = FIRST_BOOT_LAUNCHER_TRADE_STEP


def estimate_first_boot_real_days(training_trades: int) -> int:
    return int(math.ceil(max(1, int(training_trades)) / float(FIRST_BOOT_EST_TRADES_PER_REAL_DAY)))


def normalize_first_boot_training_trades(raw_value: int | float | str | None) -> int:
    try:
        value = int(raw_value) if raw_value is not None else FIRST_BOOT_DEFAULT_TRADES
    except (TypeError, ValueError):
        value = FIRST_BOOT_DEFAULT_TRADES
    return max(FIRST_BOOT_TRAINING_TRADES_MIN, min(FIRST_BOOT_TRAINING_TRADES_MAX, value))


def exceeds_max_real_days_window(estimated_days: int, max_real_days: int) -> bool:
    return int(estimated_days) > int(max_real_days)


def is_high_load_estimate(
    estimated_days: int,
    *,
    threshold: int = FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS,
) -> bool:
    return int(estimated_days) > int(threshold)
