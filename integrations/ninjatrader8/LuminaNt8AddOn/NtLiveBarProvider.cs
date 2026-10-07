// ============================================================
// LUMINA — NT live Last bars (ADR-0053 + ADR-0054)
// Long-lived BarsRequest + Update per native period. Same series as the chart.
// ============================================================

#region Using declarations
using System;
using System.Collections.Concurrent;
using Lumina.Execution.Fabric.MarketData;
using Lumina.Execution.V1;
#if !FABRIC_STANDALONE
using NinjaTrader.Cbi;
using NinjaTrader.Data;
#endif
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    public sealed class NtLiveBarProvider : ILiveBarProvider, IDisposable
    {
        private readonly Action<string>? _log;
#if !FABRIC_STANDALONE
        private readonly ConcurrentDictionary<string, Sub> _subs =
            new ConcurrentDictionary<string, Sub>(StringComparer.OrdinalIgnoreCase);
#endif

        public NtLiveBarProvider(Action<string>? log = null)
        {
            _log = log;
        }

        public string ProviderKind => "nt";

#if FABRIC_STANDALONE
        public string Subscribe(string instrument, string barPeriod, string correlationId, Action<MarketDataUpdate> onUpdate)
            => "HOST_NO_NT_LIVE_DATA";

        public void Unsubscribe(string instrument) { }

        public void UnsubscribeAll() { }
#else
        public string Subscribe(string instrument, string barPeriod, string correlationId, Action<MarketDataUpdate> onUpdate)
        {
            var name = (instrument ?? "").Trim();
            if (string.IsNullOrEmpty(name))
                return "INVALID_INSTRUMENT";
            if (onUpdate == null)
                return "INVALID_HANDLER";
            if (!NtBarPeriods.TryParse(barPeriod, out var periodType, out var periodValue, out var canonical))
                return "BAR_PERIOD_UNSUPPORTED";

            Instrument? inst = null;
            try
            {
                inst = Instrument.GetInstrument(name);
                if (inst == null)
                    inst = Instrument.GetInstrumentFuzzy(name);
            }
            catch (Exception ex)
            {
                Log("bar resolve failed: " + ex.Message);
            }
            if (inst == null)
                return "INSTRUMENT_NOT_FOUND";

            var instKey = inst.FullName ?? name;
            var key = SubKey(instKey, canonical);
            TradingHours? hours = null;
            try { hours = inst.MasterInstrument?.TradingHours; }
            catch (Exception ex)
            {
                Log("trading hours read failed: " + ex.Message);
            }
            if (hours == null)
            {
                Log("TRADING_HOURS_MISSING instrument=" + instKey);
                return "TRADING_HOURS_MISSING";
            }

            UnsubscribeKey(key);

            try
            {
                var sub = new Sub
                {
                    Instrument = inst,
                    OnUpdate = onUpdate,
                    TradingHoursName = hours.Name,
                    CanonicalPeriod = canonical,
                    InstrumentKey = instKey,
                };
                void Handler(object? sender, BarsUpdateEventArgs e)
                {
                    try
                    {
                        if (e == null)
                            return;
                        Bars? series = null;
                        try { series = (sender as BarsRequest)?.Bars; } catch { series = null; }
                        if (series == null)
                            try { series = sub.Request?.Bars; } catch { series = null; }
                        if (series == null)
                            return;
                        for (var i = e.MinIndex; i <= e.MaxIndex; i++)
                            Emit(instKey, canonical, series, i, onUpdate);
                    }
                    catch (Exception ex)
                    {
                        Log("bar update: " + ex.Message);
                    }
                }

                sub.Handler = Handler;
                var request = new BarsRequest(inst, NtBarPeriods.LiveBarsBack(canonical))
                {
                    BarsPeriod = new BarsPeriod { BarsPeriodType = periodType, Value = periodValue },
                    TradingHours = hours,
                };
                try { request.IsResetOnNewTradingDay = true; } catch { /* NT build variance */ }
                request.Update += Handler;
                sub.Request = request;
                _subs[key] = sub;

                request.Request((bars, errorCode, errorMessage) =>
                {
                    if (errorCode != ErrorCode.NoError)
                    {
                        Log("BarsRequest live error " + errorCode + " " + errorMessage + " period=" + canonical);
                        return;
                    }
                    try
                    {
                        var series = bars?.Bars;
                        if (series == null)
                            return;
                        var last = series.Count - 1;
                        if (last >= 0)
                            Emit(instKey, canonical, series, last, onUpdate);
                        Log("live forming instrument=" + instKey + " period=" + canonical
                            + " series_count=" + series.Count
                            + " th=" + hours.Name + " corr=" + correlationId);
                    }
                    catch (Exception ex)
                    {
                        Log("live hydrate: " + ex.Message);
                    }
                });
                Log("subscribed live bars " + instKey + " period=" + canonical + " th=" + hours.Name);
                return "ok";
            }
            catch (Exception ex)
            {
                Log("Subscribe bars failed: " + ex.Message);
                UnsubscribeKey(key);
                return "SUBSCRIBE_ERROR";
            }
        }

        public void Unsubscribe(string instrument)
        {
            var want = (instrument ?? "").Trim();
            if (string.IsNullOrEmpty(want))
                return;
            foreach (var kv in _subs.ToArray())
            {
                var sub = kv.Value;
                var instKey = sub?.InstrumentKey ?? kv.Key;
                if (string.Equals(instKey, want, StringComparison.OrdinalIgnoreCase)
                    || instKey.IndexOf(want, StringComparison.OrdinalIgnoreCase) >= 0
                    || kv.Key.StartsWith(want + "|", StringComparison.OrdinalIgnoreCase))
                {
                    if (_subs.TryRemove(kv.Key, out var removed))
                        DisposeSub(removed, kv.Key);
                }
            }
        }

        public void UnsubscribeAll()
        {
            foreach (var key in _subs.Keys)
                UnsubscribeKey(key);
        }

        private void UnsubscribeKey(string key)
        {
            if (_subs.TryRemove(key, out var sub))
                DisposeSub(sub, key);
        }

        private void Emit(string instrument, string canonical, Bars series, int index, Action<MarketDataUpdate> onUpdate)
        {
            if (series == null || index < 0 || index >= series.Count)
                return;
            var ts = series.GetTime(index);
            var open = series.GetOpen(index);
            var high = series.GetHigh(index);
            var low = series.GetLow(index);
            var close = series.GetClose(index);
            if (open <= 0 || high <= 0 || low <= 0 || close <= 0)
            {
                Log("reject non-positive OHLC idx=" + index + " " + instrument + " " + canonical);
                return;
            }
            if (high < Math.Max(open, close) || low > Math.Min(open, close))
            {
                Log("reject inconsistent OHLC idx=" + index + " " + instrument + " " + canonical);
                return;
            }
            long vol = 0;
            try { vol = (long)series.GetVolume(index); } catch { vol = 0; }
            var update = new MarketDataUpdate
            {
                Instrument = instrument,
                TimestampUnixMs = NtBarClock.ToUnixMs(ts),
                Last = close,
                Open = open,
                High = high,
                Low = low,
                Close = close,
                Volume = vol,
                IsBar = true,
                BarPeriod = canonical,
            };
            onUpdate(update);
        }

        private void DisposeSub(Sub? sub, string key)
        {
            if (sub == null)
                return;
            try
            {
                if (sub.Request != null && sub.Handler != null)
                    sub.Request.Update -= sub.Handler;
            }
            catch { /* ignore */ }
            try { sub.Request?.Dispose(); } catch { /* ignore */ }
            Log("unsubscribed live bars " + key);
        }

        private static string SubKey(string instrument, string period) => instrument + "|" + period;
#endif

        public void Dispose()
        {
            try { UnsubscribeAll(); } catch { /* ignore */ }
        }

        private void Log(string msg) => _log?.Invoke("[FabricLiveBars] " + msg);

#if !FABRIC_STANDALONE
        private sealed class Sub
        {
            public Instrument? Instrument;
            public BarsRequest? Request;
            public EventHandler<BarsUpdateEventArgs>? Handler;
            public Action<MarketDataUpdate>? OnUpdate;
            public string? TradingHoursName;
            public string? CanonicalPeriod;
            public string? InstrumentKey;
        }
#endif
    }
}
