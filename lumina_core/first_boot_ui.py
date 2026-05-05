"""First-boot UI helpers: trade-count → estimated real-history days (launcher/runtime).

Kept Streamlit-free so pytest can import without initializing the launcher.
"""

from __future__ import annotations

import math

# Aligns with InfiniteSimulator first-boot capacity heuristic (~trades per calendar day of real data).
FIRST_BOOT_EST_TRADES_PER_REAL_DAY = 2500
# Prompt: very high trade counts imply ~800+ days; surface an extra operator warning above this band.
FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS = 700
FIRST_BOOT_TRADE_MIN = 100_000
FIRST_BOOT_TRADE_MAX = 2_000_000
FIRST_BOOT_TRADE_STEP = 100_000
FIRST_BOOT_DEFAULT_TRADES = 500_000
FIRST_BOOT_DEFAULT_MAX_REAL_DAYS = 90


def estimate_first_boot_real_days(training_trades: int) -> int:
    return int(math.ceil(max(1, int(training_trades)) / float(FIRST_BOOT_EST_TRADES_PER_REAL_DAY)))


def normalize_first_boot_training_trades(raw_value: int | float | str | None) -> int:
    try:
        value = int(raw_value) if raw_value is not None else FIRST_BOOT_DEFAULT_TRADES
    except (TypeError, ValueError):
        value = FIRST_BOOT_DEFAULT_TRADES
    value = max(FIRST_BOOT_TRADE_MIN, min(FIRST_BOOT_TRADE_MAX, value))
    snapped = int(round(value / FIRST_BOOT_TRADE_STEP) * FIRST_BOOT_TRADE_STEP)
    return max(FIRST_BOOT_TRADE_MIN, min(FIRST_BOOT_TRADE_MAX, snapped))


def exceeds_max_real_days_window(estimated_days: int, max_real_days: int) -> bool:
    return int(estimated_days) > int(max_real_days)


def is_high_load_estimate(
    estimated_days: int,
    *,
    threshold: int = FIRST_BOOT_HIGH_LOAD_ESTIMATE_DAYS,
) -> bool:
    return int(estimated_days) > int(threshold)
