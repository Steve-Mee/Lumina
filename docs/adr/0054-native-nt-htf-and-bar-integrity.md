# ADR-0054: Native NT session HTF, bar integrity, open-chart listing

**Status:** Accepted  
**Date:** 2026-10-02  
**Deciders:** LUMINA Engineering + Operator (First Principles review)

## Context

ADR-0053 made NinjaTrader 1-minute Last bars the OHLC SSOT. Higher timeframes
were still pandas `resample("240min")` on those 1m bars. That series is not the
NinjaTrader 4-hour chart (session `TradingHours` + `IsResetOnNewTradingDay`).
The original HH/LL mismatch on the 240m panel was this clock, not a wick bug.

A missed REAL 1m bar desynchronises ATR, regime, fibs, Playground and stops.
Wall-clock gap detection treats the CME ETH halt as a hole. NT is the SSOT for
whether a bar should exist.

`config.yaml` can name an expired listing while the open chart is the live
front month. The chart selector is the book.

Constitution: truth-seeking, fail-closed, no silent invention. Operator law:
decision and display data equal the NinjaTrader chart. No golden mean.
OBSERVATION_DIM stays 43 (ADR-0015 + ADR-0018) until a later ADR after Birth wipe.

## Decision

1. **Native HTF SSOT** = NinjaTrader Minute 5/15/30/60/240 Last bars, same
   instrument `TradingHours` as the 1m series. Live path = one long-lived
   `BarsRequest` per period. `MarketDataUpdate.bar_period` is required on bars.
   pandas resample is not a substitute for decisions, Sense Lab shadows, or
   screen-share panels.
2. **Bar integrity** = request NT historical 1m for `[last_closed, now]`.
   Bars NT has and Lumina does not are filled from NT (never invented).
   After fill, completeness is set-equality of **closed** 1m timestamps on the
   overlapping window (NT barsBack is a tail; older local bars outside that
   tail are not extras). The forming bar (close timestamp still in the future)
   is excluded from the closed set — counting it as missing would lock entries
   for every live minute. Tape is live only when the last print is ≤30s old
   (a leftover quote deque after ETH halt is not live). Tape live + stale NT
   last close is unexplained. Unexplained or unreachable NT locks **new entries**
   via the existing pre-trade gate (`bar_book_incomplete`). Flatten/reduce-only
   stay open. No fifth kill-switch layer.
   A timestamp already past is committed to the closed book on apply (hydrate
   and live). A future timestamp stays `current_candle` only. Historical
   bootstrap (`load_historical_ohlc` / `load_historical_ohlc_for_symbol` /
   `load_historical_ohlc_extended` / `append_ohlc_rows`) excludes the
   still-forming last NT bar from closed history. Live load hydrates that bar
   via `apply_nt_bar` onto `current_candle`. `load_historical_ohlc_for_symbol`
   returns closed rows only. Extended expands closed bars into ticks only.
3. **Evolution feature** = blackboard topic `market.bar_integrity` +
   `state/lumina_bar_integrity.json`. Occupancy (flat/total) is a different
   metric and is not mixed. A future observation slot needs its own ADR.
4. **Forming bar** on screen-share is `current_candle` concatenated onto closed
   native frames. Closed history stays `ohlc_*`; forming is display + live HTF
   last row in snapshots, never a Playground close.
5. **Instrument SSOT** = open chart selector when readable; calendar
   `live_listing` only when no selector. Engine last fallback is calendar MES
   front month, never a hardcoded contract month. `config.yaml` is not rewritten
   to a month.

## Consequences

### Positive

- 15m/240m HH/LL match the NT session charts.
- A missed bar is visible, filled from NT, and blocks new REAL/SIM_REAL_GUARD
  entries until the book is NT-equal.
- Lumina can learn completeness without cheating the 43-dim vector.

### Negative

- Six live `BarsRequest` objects per subscribed listing. Hydrate is forming-only
  plus a bounded historical fill.
- AddOn 1.7.0 must be rebuilt with `NINJATRADER8_BIN` and reloaded after NT close.
- Daily `1440min` is not a native live series here; snapshots report missing
  rather than a wall-clock resample.

## Alternatives considered

1. Keep pandas HTF "for display only" — two truths. Rejected.
2. Invent 1m bars from last quote during a hole — silent lie. Rejected.
3. Fifth kill-switch layer for data gaps — layers are SSOT
   (`GLOBAL_HALT`, `TRADING_LOCK`, `STRATEGY_LOCK`, `INSTRUMENT_LOCK`).
   New entries already fail closed through the admission gate.
4. Bump OBSERVATION_DIM to 44 for completeness — frozen 43-dim Awakening child.
   Blackboard first; slot later via ADR after Birth wipe.

## Related ADRs

- ADR-0053 NT 1-minute Last OHLC SSOT
- ADR-0018 43-dim observation
- ADR-0035 Execution Fabric gRPC
- ADR-0040 Fabric-only foundation
