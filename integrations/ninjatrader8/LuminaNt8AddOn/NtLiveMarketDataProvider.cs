// ============================================================
// LUMINA — NT live market data (data plane, no CrossTrade)
// ============================================================

#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using Lumina.Execution.Fabric.MarketData;
using Lumina.Execution.V1;
#if !FABRIC_STANDALONE
using NinjaTrader.Cbi;
using NinjaTrader.Data;
#endif
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    public sealed class NtLiveMarketDataProvider : ILiveMarketDataProvider, IDisposable
    {
        private readonly Action<string>? _log;
        private readonly ConcurrentDictionary<string, Sub> _subs =
            new ConcurrentDictionary<string, Sub>(StringComparer.OrdinalIgnoreCase);

        public NtLiveMarketDataProvider(Action<string>? log = null)
        {
            _log = log;
        }

        public string ProviderKind => "nt";

#if FABRIC_STANDALONE
        public string Subscribe(string instrument, string correlationId, Action<MarketDataUpdate> onUpdate)
            => "HOST_NO_NT_LIVE_DATA";

        public void Unsubscribe(string instrument) { }

        public void UnsubscribeAll() { }
#else
        public string Subscribe(string instrument, string correlationId, Action<MarketDataUpdate> onUpdate)
        {
            var name = (instrument ?? "").Trim();
            if (string.IsNullOrEmpty(name))
                return "INVALID_INSTRUMENT";
            if (onUpdate == null)
                return "INVALID_HANDLER";

            Instrument? inst = null;
            try
            {
                inst = Instrument.GetInstrument(name);
                if (inst == null)
                    inst = Instrument.GetInstrumentFuzzy(name);
            }
            catch (Exception ex)
            {
                Log("resolve failed: " + ex.Message);
            }

            if (inst == null)
                return "INSTRUMENT_NOT_FOUND";

            var key = inst.FullName ?? name;
            Unsubscribe(key);

            try
            {
                void Handler(object? sender, MarketDataEventArgs e)
                {
                    try
                    {
                        if (e == null)
                            return;
                        var update = new MarketDataUpdate
                        {
                            Instrument = key,
                            TimestampUnixMs = new DateTimeOffset(DateTime.SpecifyKind(e.Time, DateTimeKind.Local))
                                .ToUniversalTime().ToUnixTimeMilliseconds(),
                            Last = e.Last > 0 ? e.Last : e.Price,
                            Bid = e.Bid,
                            Ask = e.Ask,
                            Volume = e.Volume,
                            IsBar = false,
                        };
                        try
                        {
                            var md = inst.MarketData;
                            if (md != null)
                            {
                                if (md.Last != null && md.Last.Price > 0)
                                    update.Last = md.Last.Price;
                                if (md.Bid != null && md.Bid.Price > 0)
                                    update.Bid = md.Bid.Price;
                                if (md.Ask != null && md.Ask.Price > 0)
                                    update.Ask = md.Ask.Price;
                            }
                        }
                        catch { /* use event prices */ }

                        onUpdate(update);
                    }
                    catch (Exception ex)
                    {
                        Log("live md handler: " + ex.Message);
                    }
                }

                inst.MarketDataUpdate += Handler;
                _subs[key] = new Sub { Instrument = inst, Handler = Handler, OnUpdate = onUpdate };
                Log("subscribed live " + key + " corr=" + correlationId);
                return "ok";
            }
            catch (Exception ex)
            {
                Log("Subscribe failed: " + ex.Message);
                return "SUBSCRIBE_ERROR";
            }
        }

        public void Unsubscribe(string instrument)
        {
            var key = (instrument ?? "").Trim();
            if (string.IsNullOrEmpty(key))
                return;
            if (!_subs.TryRemove(key, out var sub))
            {
                // Try match by any key ending
                foreach (var kv in _subs.ToArray())
                {
                    if (string.Equals(kv.Key, key, StringComparison.OrdinalIgnoreCase)
                        || kv.Key.IndexOf(key, StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        if (_subs.TryRemove(kv.Key, out sub))
                            break;
                    }
                }
            }

            if (sub?.Instrument != null && sub.Handler != null)
            {
                try { sub.Instrument.MarketDataUpdate -= sub.Handler; } catch { /* ignore */ }
                Log("unsubscribed live " + key);
            }
        }

        public void UnsubscribeAll()
        {
            foreach (var key in _subs.Keys)
                Unsubscribe(key);
        }

        private sealed class Sub
        {
            public Instrument? Instrument;
            public EventHandler<MarketDataEventArgs>? Handler;
            public Action<MarketDataUpdate>? OnUpdate;
        }
#endif

        public void Dispose()
        {
            try { UnsubscribeAll(); } catch { /* ignore */ }
        }

        private void Log(string msg) => _log?.Invoke("[FabricLive] " + msg);
    }
}
