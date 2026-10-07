#!/usr/bin/env python3
"""Source + mapping audit for ADR-0053 (NT 1-minute Last OHLC SSOT).

Does not connect to NinjaTrader. Live chart parity is an operator check after
the AddOn is loaded: same instrument, same TradingHours, same 1m Last bar.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKS: list[tuple[str, str, bool]] = [
    ("lumina_core/engine/market_data_history.py", r"tz_convert\(None\)", False),
    ("lumina_core/engine/market_data_history.py", r'or bar\.get\("last"\)', False),
    ("lumina_core/engine/market_data_history.py", r"accept_source_bars", True),
    ("lumina_core/engine/market_data_history_fetch.py", r'b\.get\("high"\) or b\.get\("last"\)', False),
    ("lumina_core/engine/market_data_ingest.py", r"_drain_nt_bars", True),
    ("lumina_core/engine/market_data_ingest.py", r"closed_candle = self\.engine\.market_data\.process_quote_tick", False),
    ("lumina_core/engine/market_data_ingest.py", r"tape_is_live", True),
    ("lumina_core/engine/bar_integrity.py", r"is_forming_bar", True),
    ("lumina_core/engine/bar_integrity.py", r"local_in_window", True),
    ("lumina_core/engine/market_data_manager.py", r"still_forming", True),
    ("lumina_core/engine/market_data_manager.py", r"Quotes never write", True),
    ("lumina_core/engine/market_data_manager.py", r"partition_closed_and_forming", True),
    ("lumina_core/engine/market_data_history.py", r"partition_closed_and_forming", True),
    ("lumina_core/engine/market_data_history.py", r"apply_nt_bar\(forming", True),
    ("lumina_core/engine/market_data_history.py", r"_fetch_closed_and_forming", True),
    ("lumina_core/engine/market_data_history.py", r"return pd\.DataFrame\(rows\)", False),
    ("lumina_core/engine/market_data_history.py", r"is_forming_bar", True),
    ("lumina_core/broker/ninjatrader/fabric_client.py", r"include_bars=True", True),
    ("lumina_core/engine/visualization_charts.py", r"\.resample\(", False),
    ("lumina_core/engine/operations_service_market.py", r"\.resample\(", False),
    ("lumina_core/engine/analysis_loop.py", r"\.resample\(", False),
    ("lumina_core/engine/engine_config_helpers.py", r"MES SEP26", False),
    ("integrations/ninjatrader8/LuminaNt8AddOn/NtLiveBarProvider.cs", r"BarsRequest", True),
    ("integrations/ninjatrader8/LuminaNt8AddOn/NtLiveBarProvider.cs", r"series == None", False),
    ("integrations/ninjatrader8/LuminaNt8AddOn/NtLiveBarProvider.cs", r"BarPeriod = canonical", True),
    ("integrations/ninjatrader8/LuminaNt8AddOn/NtHistoricalDataProvider.cs", r'TradingHours\.Get\("Default', False),
    ("integrations/ninjatrader8/LuminaNt8AddOn/NtHistoricalDataProvider.cs", r"BAR_WINDOW_TOO_LARGE", True),
    ("integrations/ninjatrader8/LuminaNt8AddOn/NtHistoricalDataProvider.cs", r"BAR_PERIOD_UNSUPPORTED", True),
]


def main() -> int:
    failed = 0
    for rel, pattern, must_match in CHECKS:
        path = ROOT / rel
        if not path.is_file():
            print(f"FAIL missing file {rel}")
            failed += 1
            continue
        text = path.read_text(encoding="utf-8")
        found = re.search(pattern, text) is not None
        if must_match and not found:
            print(f"FAIL expected /{pattern}/ in {rel}")
            failed += 1
        elif (not must_match) and found:
            print(f"FAIL forbidden /{pattern}/ in {rel}")
            failed += 1
        else:
            print(f"ok {rel} /{pattern}/")
    if failed:
        print(f"audit_nt_ohlc_parity: {failed} failure(s)")
        return 1
    print("audit_nt_ohlc_parity: source path clean")
    print(
        "Live check after NT reload: 1m Last chart O/H/L/C/time == Lumina ohlc_1min "
        "for the same listing and TradingHours."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
