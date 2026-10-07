# ADR-0053: NinjaTrader 1-minute Last bars are the OHLC SSOT

**Status:** Accepted  
**Date:** 2026-10-02  
**Deciders:** LUMINA Engineering + Operator (First Principles review)

## Context

Live decision OHLC was rebuilt from a 250 ms poll of Fabric's last quote cache
(`process_quote_tick` + `datetime.now()`). High/low of a Lumina candle was the
extrema of sampled lasts, not NinjaTrader's 1-minute Last series. Proto field
`include_bars` was ignored. Historical load stripped timezones, filled missing
high/low with `last`, and even-sampled bars when a window exceeded `maxBars`.

Constitution: truth-seeking, fail-closed, no silent invention. Operator law:
decision data must equal the NinjaTrader chart. No golden mean.

Official NT8 AddOn API (`BarsRequest`) requests bars **and** subscribes to
real-time bar events (`BarsRequest.Update`). `GetOpen/High/Low/Close/Volume/Time`
is the same series a chart uses for that period and `TradingHours`. NT stamps
a minute bar with its **close** time (9:31 contains 9:30:00–9:30:59).

## Decision

1. **SSOT** = NinjaTrader 1-minute **Last** bars for the subscribed listing,
   same `BarsPeriod` (Minute 1) and `TradingHours` as the instrument master
   (the open chart). Tape (bid/ask/last) is a separate channel and never
   writes `ohlc_1min`.
2. **Live path** = long-lived `BarsRequest` in the NT AddOn + `Update` handler
   emitting `MarketDataUpdate { is_bar=true, OHLCV, timestamp_unix_ms }`.
   Brain applies those bars via `apply_nt_bar`. Quote polling does not close
   candles.
3. **Time** = timezone-aware UTC from NT unix-ms. Naive `datetime.now()` and
   `tz_convert(None)` are forbidden on the OHLC path.
4. **Fail-closed mapping**: missing/zero high or low, `high or last` fill,
   even-sample downsample, and `Default 24 x 7` as a silent TradingHours
   fallback are rejects. Too many rejected rows fail the historical load.
5. **Birth forensic** is a separate receipt against a fresh BarsRequest. This
   ADR does not wipe or lower floors.
6. Live `BarsRequest` callback emits the **forming** bar only. Closed history is
   `RequestHistoricalData`. `Update` emits `MinIndex..MaxIndex`. Playground
   `on_closed_candle` runs only when the closed NT timestamp is within 120s of
   UTC now, so hydrate/backfill cannot replay decisions.

## Consequences

### Positive

- Live 1m O/H/L/C/V/time matches the NT 1m Last chart (same TradingHours).
- Playground, ATR/ADX, regime, fibs, and paper ATR see NT bars.
- Historical Birth loads cannot silently skip intra-window bars.

### Negative

- AddOn must be rebuilt with `NINJATRADER8_BIN` and reloaded after NT close.
- CrossTrade quote streams cannot invent 1m OHLC (fail-closed empty live bars).
- Higher-timeframe screen resample vs NT 240m session bars is closed by ADR-0054.

## Alternatives considered

1. Rebuild 1m from every Last tick in Python — still a second clock; poll/cache
   can drop prints. Rejected.
2. NinjaScript strategy `OnBarUpdate` — extra chart/strategy surface. AddOn
   `BarsRequest.Update` is the documented AddOn path. Chosen.
3. Keep quote candles "for display only" while NT bars drive decisions —
   two truths. Rejected.

## Related ADRs

- ADR-0035 Execution Fabric gRPC
- ADR-0040 Fabric-only foundation (historical_bars dual-plane)
- ADR-0018 Trend features (ATR/ADX from OHLC)
