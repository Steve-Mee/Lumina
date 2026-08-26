// ============================================================
// LUMINA — NT8 BarsRequest historical provider (data plane)
// Fail-closed. Never invent bars. Capital preservation first.
//
// Critical NT facts (help guide + Core reflection):
// - Read bars.Bars INSIDE Request callback (or before Dispose).
// - Dispose(BarsRequest) invalidates Bars → Count becomes 0 (false NO_BARS).
// - LookupPolicy.Provider forces HDS/provider fetch, not empty local repo.
// - barsBack preferred for sub-day; from/to snap to full local days.
// ============================================================

#region Using declarations
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Threading;
using Lumina.Execution.Fabric.MarketData;
using Lumina.Execution.V1;
#if !FABRIC_STANDALONE
using NinjaTrader.Cbi;
using NinjaTrader.Core;
using NinjaTrader.Data;
#endif
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    public sealed class NtHistoricalDataProvider : IHistoricalDataProvider
    {
        private readonly Action<string>? _log;
        private readonly int _timeoutMs;

        public NtHistoricalDataProvider(Action<string>? log = null, int timeoutMs = 90_000)
        {
            _log = log;
            _timeoutMs = timeoutMs > 0 ? timeoutMs : 90_000;
        }

        public string ProviderKind => "nt";

#if FABRIC_STANDALONE
        public HistoricalDataResponse GetHistoricalBars(HistoricalDataRequest request)
        {
            return new HistoricalDataResponse
            {
                Instrument = request?.Instrument ?? "",
                CorrelationId = request?.CorrelationId ?? "",
                Code = "HOST_NO_NT_DATA",
                Message = "AddOn built without NinjaTrader.Core (FABRIC_STANDALONE).",
            };
        }
#else
        public HistoricalDataResponse GetHistoricalBars(HistoricalDataRequest request)
        {
            var instrumentName = (request?.Instrument ?? "").Trim();
            var correlationId = request?.CorrelationId ?? "";
            if (string.IsNullOrWhiteSpace(instrumentName))
                return Fail(instrumentName, correlationId, "INVALID_INSTRUMENT", "Instrument is required");

            // Code Red: do not storm HDS/Tradovate while primary connection is still Connecting.
            // Vendor crash observed: NullReferenceException in Tradovate.Adapter WebSocket path.
            WaitForMarketDataReady(maxWaitMs: 12_000);
            // Pace successive BarsRequest calls from birth pagination (Brain-side also settles).
            ThrottleBarsRequest(minIntervalMs: 750);

            var instrument = ResolveInstrument(instrumentName, out var resolved, out var tried);
            if (instrument == null)
            {
                return Fail(
                    instrumentName,
                    correlationId,
                    "INSTRUMENT_NOT_FOUND",
                    "NT could not resolve instrument. Tried: " + string.Join(", ", tried)
                    + ". Use full NT name e.g. 'MES 09-26'.");
            }

            // Cap per RPC high enough for ~2 weeks of 1m futures bars (birth chunks).
            var maxBars = request?.MaxBars > 0 ? Math.Min(request.MaxBars, 50_000) : 5_000;
            var (periodType, periodValue) = ParseBarPeriod(request?.BarPeriod);
            var (from, to) = ResolveWindow(request);

            // Birth pages multi-day windows. When from/to are set, NEVER fall back to
            // barsBack — that always returns the latest N bars and poisons pagination
            // (merge stays stuck at ~8 calendar days → training_window_sla 8/56).
            var hasExplicitWindow = request != null
                && request.StartUnixMs > 0
                && request.EndUnixMs > request.StartUnixMs;
            var windowDays = Math.Max(0.0, (to - from).TotalDays);
            var windowedBirthLoad = hasExplicitWindow && windowDays >= 1.0;

            Log($"window from={from:o} to={to:o} days={windowDays:F1} windowed={windowedBirthLoad} maxBars={maxBars}");

            var attemptList = new List<(string label, Func<BarsSnapshot> run)>();
            void add(string label, Func<BarsSnapshot> run) => attemptList.Add((label, run));

            if (windowedBirthLoad)
            {
                // Only from/to strategies — filter results to [from,to].
                add("fromTo+Provider+24x7+1m", () => FetchSnapshot(
                    instrument, periodType, periodValue, maxBars,
                    useBarsBack: false, barsBack: 0,
                    from: from, to: to,
                    tradingHoursName: "Default 24 x 7",
                    lookupProvider: true,
                    filterToWindow: true));
                add("fromTo+Provider+instrTH+1m", () => FetchSnapshot(
                    instrument, periodType, periodValue, maxBars,
                    useBarsBack: false, barsBack: 0,
                    from: from, to: to,
                    tradingHoursName: null,
                    lookupProvider: true,
                    filterToWindow: true));
                add("fromTo+Repository+24x7+1m", () => FetchSnapshot(
                    instrument, periodType, periodValue, maxBars,
                    useBarsBack: false, barsBack: 0,
                    from: from, to: to,
                    tradingHoursName: "Default 24 x 7",
                    lookupProvider: false,
                    filterToWindow: true));
                add("fromTo+Provider+24x7+1d", () => FetchSnapshot(
                    instrument, BarsPeriodType.Day, 1, Math.Max(maxBars, 60),
                    useBarsBack: false, barsBack: 0,
                    from: from, to: to,
                    tradingHoursName: "Default 24 x 7",
                    lookupProvider: true,
                    filterToWindow: true));
            }
            else
            {
                // Diagnostics / short loads: barsBack is fine.
                add("barsBack+Provider+24x7+1m", () => FetchSnapshot(
                    instrument, periodType, periodValue, maxBars,
                    useBarsBack: true, barsBack: Math.Max(maxBars, 200),
                    from: from, to: to,
                    tradingHoursName: "Default 24 x 7",
                    lookupProvider: true,
                    filterToWindow: false));
                add("fromTo+Provider+24x7+1m", () => FetchSnapshot(
                    instrument, periodType, periodValue, maxBars,
                    useBarsBack: false, barsBack: 0,
                    from: from, to: to,
                    tradingHoursName: "Default 24 x 7",
                    lookupProvider: true,
                    filterToWindow: true));
                add("barsBack+Repository+24x7+1m", () => FetchSnapshot(
                    instrument, periodType, periodValue, maxBars,
                    useBarsBack: true, barsBack: Math.Max(maxBars, 500),
                    from: from, to: to,
                    tradingHoursName: "Default 24 x 7",
                    lookupProvider: false,
                    filterToWindow: false));
            }

            var attempts = attemptList.ToArray();

            BarsSnapshot? last = null;
            foreach (var attempt in attempts)
            {
                Log($"try {attempt.label} instrument={resolved}");
                BarsSnapshot snap;
                try
                {
                    snap = attempt.run();
                }
                catch (Exception ex)
                {
                    Log($"try {attempt.label} exception: {ex.Message}");
                    last = new BarsSnapshot { Failed = true, ErrorMessage = ex.Message, Label = attempt.label };
                    continue;
                }

                Log($"try {attempt.label} code={snap.ErrorCode} bars={snap.Rows.Count} msg={snap.ErrorMessage} span={snap.SpanHint}");
                if (!snap.Failed && snap.ErrorCode == ErrorCode.NoError && snap.Rows.Count > 0)
                    return ToResponse(resolved, correlationId, snap, maxBars, attempt.label);

                last = snap;
                last.Label = attempt.label;
            }

            var detail = last == null
                ? "no attempts"
                : $"last={last.Label} code={last.ErrorCode} msg={last.ErrorMessage} bars={last.Rows.Count}";

            return Fail(
                resolved,
                correlationId,
                "NO_BARS",
                "NT returned zero bars after multi-strategy BarsRequest. " + detail
                + ". Ensure Control Center shows Connected (price feed); open a MES chart once; "
                + "verify historical data server / Continuum-Kinetick subscription.");
        }

        private static long _lastBarsRequestUtcTicks;

        /// <summary>
        /// Brief wait so Connection.Status is Connected before BarsRequest.
        /// Reduces pressure on Tradovate/HDS while still Connecting (vendor NRE observed).
        /// </summary>
        private void WaitForMarketDataReady(int maxWaitMs)
        {
            try
            {
                var deadline = DateTime.UtcNow.AddMilliseconds(Math.Max(0, maxWaitMs));
                while (DateTime.UtcNow < deadline)
                {
                    if (AnyConnectionConnected())
                    {
                        // Small settle after Connected so WebSocket paths finish init.
                        Thread.Sleep(400);
                        return;
                    }
                    Thread.Sleep(250);
                }
                Log("market data settle timeout — proceeding (may fail if still Connecting)");
            }
            catch (Exception ex)
            {
                Log("WaitForMarketDataReady: " + ex.Message);
            }
        }

        /// <summary>
        /// Code Red: birth history pages many RPCs; without pacing, Tradovate/HDS storms
        /// have correlated with NinjaTrader.exe process exit (vendor path).
        /// </summary>
        private static void ThrottleBarsRequest(int minIntervalMs)
        {
            if (minIntervalMs <= 0)
                return;
            try
            {
                var now = DateTime.UtcNow.Ticks;
                var last = Interlocked.Read(ref _lastBarsRequestUtcTicks);
                if (last > 0)
                {
                    var elapsedMs = (now - last) / TimeSpan.TicksPerMillisecond;
                    var wait = minIntervalMs - (int)elapsedMs;
                    if (wait > 0 && wait < 10_000)
                        Thread.Sleep(wait);
                }
                Interlocked.Exchange(ref _lastBarsRequestUtcTicks, DateTime.UtcNow.Ticks);
            }
            catch
            {
                // never block historical path on throttle failure
            }
        }

        private static bool AnyConnectionConnected()
        {
            try
            {
                // Connection.ConnectionStatus enum: Connected is the live state.
                foreach (Connection c in Connection.Connections)
                {
                    if (c == null)
                        continue;
                    try
                    {
                        if (c.Status == ConnectionStatus.Connected)
                            return true;
                    }
                    catch
                    {
                        /* ignore single connection */
                    }
                }
            }
            catch
            {
                /* Connection.Connections may throw early in session */
            }
            return false;
        }

        private Instrument? ResolveInstrument(string instrumentName, out string resolved, out List<string> tried)
        {
            resolved = instrumentName;
            tried = new List<string>();

            foreach (var candidate in BuildInstrumentCandidates(instrumentName))
            {
                tried.Add(candidate);
                try
                {
                    var found = TryGetInstrument(candidate);
                    if (found != null)
                    {
                        resolved = !string.IsNullOrWhiteSpace(found.FullName) ? found.FullName : candidate;
                        Log($"resolved '{instrumentName}' -> '{resolved}' (via '{candidate}') master={found.MasterInstrument?.Name}");
                        return found;
                    }
                }
                catch (Exception ex)
                {
                    Log($"lookup failed '{candidate}': {ex.Message}");
                }
            }

            try
            {
                var fuzzy = Instrument.GetInstrumentFuzzy(instrumentName);
                if (fuzzy != null && (!string.IsNullOrWhiteSpace(fuzzy.FullName) || fuzzy.MasterInstrument != null))
                {
                    resolved = fuzzy.FullName;
                    Log($"resolved '{instrumentName}' -> '{resolved}' via GetInstrumentFuzzy");
                    return fuzzy;
                }
            }
            catch (Exception ex)
            {
                Log("GetInstrumentFuzzy failed: " + ex.Message);
            }

            try
            {
                var scanned = TryResolveViaMasterInstrument(instrumentName);
                if (scanned != null)
                {
                    resolved = scanned.FullName;
                    Log($"resolved '{instrumentName}' -> '{resolved}' via MasterInstrument");
                    return scanned;
                }
            }
            catch (Exception ex)
            {
                Log("MasterInstrument scan failed: " + ex.Message);
            }

            return null;
        }

        private sealed class BarRow
        {
            public long TimestampUnixMs;
            public double Open, High, Low, Close;
            public long Volume;
        }

        private sealed class BarsSnapshot
        {
            public List<BarRow> Rows = new List<BarRow>();
            public ErrorCode ErrorCode = ErrorCode.NoError;
            public string ErrorMessage = "";
            public string Label = "";
            public string SpanHint = "";
            public bool Failed;
        }

        private BarsSnapshot FetchSnapshot(
            Instrument instrument,
            BarsPeriodType periodType,
            int periodValue,
            int maxBars,
            bool useBarsBack,
            int barsBack,
            DateTime from,
            DateTime to,
            string? tradingHoursName,
            bool lookupProvider,
            bool filterToWindow)
        {
            BarsSnapshot? result = null;
            Exception? err = null;

            RunOnNtDispatcher(() =>
            {
                try
                {
                    result = FetchSnapshotCore(
                        instrument, periodType, periodValue, maxBars,
                        useBarsBack, barsBack, from, to, tradingHoursName, lookupProvider, filterToWindow);
                }
                catch (Exception ex)
                {
                    err = ex;
                }
            });

            if (err != null)
                throw err;
            return result ?? new BarsSnapshot { Failed = true, ErrorMessage = "null snapshot" };
        }

        private BarsSnapshot FetchSnapshotCore(
            Instrument instrument,
            BarsPeriodType periodType,
            int periodValue,
            int maxBars,
            bool useBarsBack,
            int barsBack,
            DateTime from,
            DateTime to,
            string? tradingHoursName,
            bool lookupProvider,
            bool filterToWindow)
        {
            var snap = new BarsSnapshot();
            using (var done = new ManualResetEventSlim(false))
            {
                BarsRequest? barsRequest = null;
                try
                {
                    if (useBarsBack)
                        barsRequest = new BarsRequest(instrument, Math.Max(1, barsBack));
                    else
                    {
                        // Official NT sample: plain local DateTimes (full trading days).
                        var dayFrom = from.Date;
                        var dayTo = to.Date;
                        if (dayTo < dayFrom)
                            dayTo = dayFrom;
                        // Ensure at least 1 calendar day span for NT day-snap.
                        if (dayTo == dayFrom)
                            dayTo = dayFrom.AddDays(1);
                        barsRequest = new BarsRequest(instrument, dayFrom, dayTo);
                    }

                    barsRequest.BarsPeriod = new BarsPeriod
                    {
                        BarsPeriodType = periodType,
                        Value = periodValue,
                    };

                    try
                    {
                        barsRequest.LookupPolicy = lookupProvider
                            ? LookupPolicies.Provider
                            : LookupPolicies.Repository;
                    }
                    catch (Exception ex)
                    {
                        Log("LookupPolicy set failed: " + ex.Message);
                    }

                    try { barsRequest.IsResetOnNewTradingDay = true; }
                    catch { /* ignore */ }

                    try
                    {
                        TradingHours? th = null;
                        if (!string.IsNullOrWhiteSpace(tradingHoursName))
                            th = TradingHours.Get(tradingHoursName!);
                        if (th == null)
                            th = instrument.MasterInstrument?.TradingHours;
                        if (th == null)
                            th = TradingHours.Get("Default 24 x 7");
                        if (th != null)
                            barsRequest.TradingHours = th;
                    }
                    catch (Exception ex)
                    {
                        Log("TradingHours set failed: " + ex.Message);
                    }

                    Log($"BarsRequest fire barsBack={useBarsBack}/{barsBack} period={periodType}/{periodValue} lookup={(lookupProvider ? "Provider" : "Repository")} th={tradingHoursName ?? "default"} from={from:yyyy-MM-dd} to={to:yyyy-MM-dd}");

                    // Window filter pad: allow 12h skew for TZ / session edges.
                    var winLo = from.AddHours(-12);
                    var winHi = to.AddHours(12);

                    barsRequest.Request((req, code, message) =>
                    {
                        try
                        {
                            snap.ErrorCode = code;
                            snap.ErrorMessage = message ?? "";

                            Bars? bars = null;
                            try { bars = req?.Bars; } catch { bars = null; }
                            if (bars == null || bars.Count == 0)
                            {
                                try { bars = barsRequest?.Bars; } catch { /* ignore */ }
                            }

                            if (bars != null && bars.Count > 0)
                            {
                                // Take ALL bars in series up to maxBars (oldest→newest).
                                // Do NOT take only the tail — that re-centers every chunk on "now".
                                var count = bars.Count;
                                var take = Math.Min(count, Math.Max(1, maxBars));
                                // If more bars than maxBars, keep the portion inside the requested window;
                                // for barsBack mode keep the newest take bars.
                                var startIdx = useBarsBack ? Math.Max(0, count - take) : Math.Max(0, count - take);
                                if (!useBarsBack && filterToWindow)
                                    startIdx = 0; // scan all, filter, then cap

                                var endIdx = count;
                                if (!useBarsBack && filterToWindow)
                                {
                                    // Collect filtered first
                                    var tmp = new List<BarRow>(Math.Min(count, maxBars));
                                    for (var i = 0; i < count; i++)
                                    {
                                        var ts = bars.GetTime(i);
                                        if (ts < winLo || ts > winHi)
                                            continue;
                                        long vol = 0;
                                        try { vol = (long)bars.GetVolume(i); } catch { vol = 0; }
                                        tmp.Add(new BarRow
                                        {
                                            TimestampUnixMs = new DateTimeOffset(DateTime.SpecifyKind(ts, DateTimeKind.Local))
                                                .ToUniversalTime().ToUnixTimeMilliseconds(),
                                            Open = bars.GetOpen(i),
                                            High = bars.GetHigh(i),
                                            Low = bars.GetLow(i),
                                            Close = bars.GetClose(i),
                                            Volume = vol,
                                        });
                                    }
                                    // Cap if needed — keep chronological order
                                    if (tmp.Count > maxBars)
                                    {
                                        // Prefer keeping coverage across the window (even sample) for SLA span
                                        var step = (double)tmp.Count / maxBars;
                                        for (var k = 0; k < maxBars; k++)
                                            snap.Rows.Add(tmp[(int)(k * step)]);
                                    }
                                    else
                                    {
                                        snap.Rows.AddRange(tmp);
                                    }
                                }
                                else
                                {
                                    for (var i = startIdx; i < endIdx && snap.Rows.Count < maxBars; i++)
                                    {
                                        var ts = bars.GetTime(i);
                                        if (filterToWindow && (ts < winLo || ts > winHi))
                                            continue;
                                        long vol = 0;
                                        try { vol = (long)bars.GetVolume(i); } catch { vol = 0; }
                                        snap.Rows.Add(new BarRow
                                        {
                                            TimestampUnixMs = new DateTimeOffset(DateTime.SpecifyKind(ts, DateTimeKind.Local))
                                                .ToUniversalTime().ToUnixTimeMilliseconds(),
                                            Open = bars.GetOpen(i),
                                            High = bars.GetHigh(i),
                                            Low = bars.GetLow(i),
                                            Close = bars.GetClose(i),
                                            Volume = vol,
                                        });
                                    }
                                }

                                if (snap.Rows.Count > 0)
                                {
                                    var t0 = DateTimeOffset.FromUnixTimeMilliseconds(snap.Rows[0].TimestampUnixMs).UtcDateTime;
                                    var t1 = DateTimeOffset.FromUnixTimeMilliseconds(snap.Rows[snap.Rows.Count - 1].TimestampUnixMs).UtcDateTime;
                                    snap.SpanHint = $"{t0:yyyy-MM-dd}→{t1:yyyy-MM-dd}";
                                }
                                else if (filterToWindow && bars.Count > 0)
                                {
                                    // Bars existed but none in window — NT returned out-of-range series.
                                    var tFirst = bars.GetTime(0);
                                    var tLast = bars.GetTime(bars.Count - 1);
                                    snap.ErrorMessage =
                                        $"filtered_empty rawBars={bars.Count} rawSpan={tFirst:yyyy-MM-dd}→{tLast:yyyy-MM-dd} want={from:yyyy-MM-dd}→{to:yyyy-MM-dd}";
                                    Log(snap.ErrorMessage);
                                }
                            }
                            else
                            {
                                Log($"callback empty bars code={code} msg={message} reqNull={req == null}");
                            }
                        }
                        catch (Exception ex)
                        {
                            snap.Failed = true;
                            snap.ErrorMessage = "callback: " + ex.Message;
                        }
                        finally
                        {
                            try { done.Set(); } catch { /* ignore */ }
                        }
                    });

                    if (!done.Wait(_timeoutMs))
                    {
                        snap.Failed = true;
                        snap.ErrorMessage = $"BarsRequest timed out after {_timeoutMs} ms";
                    }
                }
                catch (Exception ex)
                {
                    snap.Failed = true;
                    snap.ErrorMessage = ex.Message;
                }
                finally
                {
                    try { barsRequest?.Dispose(); } catch { /* ignore */ }
                }
            }

            return snap;
        }

        private static void RunOnNtDispatcher(Action action)
        {
            try
            {
                if (Globals.RandomDispatcher != null)
                {
                    using (var done = new ManualResetEventSlim(false))
                    {
                        Exception? err = null;
                        Globals.RandomDispatcher.InvokeAsync(() =>
                        {
                            try { action(); }
                            catch (Exception ex) { err = ex; }
                            finally { try { done.Set(); } catch { /* ignore */ } }
                        });
                        if (!done.Wait(120_000))
                            throw new TimeoutException("NT dispatcher timeout (BarsRequest)");
                        if (err != null)
                            throw err;
                        return;
                    }
                }
            }
            catch (TimeoutException)
            {
                throw;
            }
            catch
            {
                // fall through
            }

            action();
        }

        private HistoricalDataResponse ToResponse(
            string resolved,
            string correlationId,
            BarsSnapshot snap,
            int maxBars,
            string strategy)
        {
            var response = new HistoricalDataResponse
            {
                Instrument = resolved,
                CorrelationId = correlationId,
                Code = "ok",
                Message = $"bars={snap.Rows.Count} provider=nt strategy={strategy}",
            };

            var rows = snap.Rows;
            var start = Math.Max(0, rows.Count - maxBars);
            for (var i = start; i < rows.Count; i++)
            {
                var r = rows[i];
                response.Bars.Add(new MarketDataUpdate
                {
                    Instrument = resolved,
                    TimestampUnixMs = r.TimestampUnixMs,
                    Last = r.Close,
                    Open = r.Open,
                    High = r.High,
                    Low = r.Low,
                    Close = r.Close,
                    Volume = r.Volume,
                    IsBar = true,
                });
            }

            Log($"BarsRequest ok instrument={resolved} bars={response.Bars.Count} strategy={strategy}");
            return response;
        }

        private static (DateTime from, DateTime to) ResolveWindow(HistoricalDataRequest? request)
        {
            var to = DateTime.Now;
            while (to.DayOfWeek == DayOfWeek.Saturday || to.DayOfWeek == DayOfWeek.Sunday)
                to = to.AddDays(-1);

            var from = to.AddDays(-14);
            if (request != null)
            {
                if (request.EndUnixMs > 0)
                    to = DateTimeOffset.FromUnixTimeMilliseconds(request.EndUnixMs).LocalDateTime;
                if (request.StartUnixMs > 0)
                    from = DateTimeOffset.FromUnixTimeMilliseconds(request.StartUnixMs).LocalDateTime;
            }
            if (from >= to)
                from = to.AddDays(-7);
            if ((to - from).TotalDays > 120)
                from = to.AddDays(-120);
            return (from, to);
        }

        private static (BarsPeriodType type, int value) ParseBarPeriod(string? barPeriod)
        {
            var raw = (barPeriod ?? "1m").Trim().ToLowerInvariant();
            if (string.IsNullOrEmpty(raw) || raw == "1m" || raw == "1min" || raw == "minute" || raw == "1")
                return (BarsPeriodType.Minute, 1);
            if (raw.EndsWith("m") && int.TryParse(raw.TrimEnd('m'), NumberStyles.Integer, CultureInfo.InvariantCulture, out var mins) && mins > 0)
                return (BarsPeriodType.Minute, Math.Min(mins, 60));
            if (raw == "1d" || raw == "day" || raw == "daily")
                return (BarsPeriodType.Day, 1);
            return (BarsPeriodType.Minute, 1);
        }

        private static Instrument? TryGetInstrument(string name)
        {
            if (string.IsNullOrWhiteSpace(name))
                return null;

            // Prefer GetInstrument(name, false) overload when available via reflection-friendly call.
            Instrument? inst = null;
            try { inst = Instrument.GetInstrument(name.Trim()); } catch { inst = null; }
            if (inst != null && (!string.IsNullOrWhiteSpace(inst.FullName) || inst.MasterInstrument != null))
                return inst;

            try
            {
                // Second bool overload exists on some builds (createIfNotExists / load options).
                inst = Instrument.GetInstrument(name.Trim(), false);
            }
            catch { inst = null; }

            if (inst != null && (!string.IsNullOrWhiteSpace(inst.FullName) || inst.MasterInstrument != null))
                return inst;
            return null;
        }

        private static Instrument? TryResolveViaMasterInstrument(string raw)
        {
            var root = ExtractRoot(raw);
            if (string.IsNullOrEmpty(root))
                return null;

            try
            {
                foreach (MasterInstrument mi in MasterInstrument.All)
                {
                    if (mi == null) continue;
                    if (!string.Equals(mi.Name, root, StringComparison.OrdinalIgnoreCase))
                        continue;
                    foreach (var full in ExpandQuarterlyContracts(root))
                    {
                        var inst = TryGetInstrument(full);
                        if (inst != null)
                            return inst;
                    }
                    return TryGetInstrument(root + " ##-##");
                }
            }
            catch { /* ignore */ }
            return null;
        }

        private static string ExtractRoot(string raw)
        {
            var parts = (raw ?? "").Trim().Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
            return parts.Length == 0 ? "" : parts[0].ToUpperInvariant();
        }

        private static List<string> BuildInstrumentCandidates(string raw)
        {
            var list = new List<string>();
            void add(string s)
            {
                s = (s ?? "").Trim();
                if (s.Length == 0) return;
                if (!list.Exists(x => string.Equals(x, s, StringComparison.OrdinalIgnoreCase)))
                    list.Add(s);
            }

            add(raw);
            var parts = raw.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length >= 2)
            {
                var root = parts[0].ToUpperInvariant();
                var rest = string.Join(" ", parts, 1, parts.Length - 1).ToUpperInvariant().Replace(" ", "");
                var nt = TryMonthYearToNt(root, rest);
                if (nt != null) add(nt);
                if (parts.Length == 2 && parts[1].Contains("-"))
                    add(root + " " + parts[1]);
            }

            if (parts.Length == 1 && parts[0].Length <= 5)
            {
                var root = parts[0].ToUpperInvariant();
                foreach (var q in ExpandQuarterlyContracts(root))
                    add(q);
                add(root + " ##-##");
                add(root);
            }

            return list;
        }

        private static List<string> ExpandQuarterlyContracts(string root)
        {
            var result = new List<string>();
            int[] months = { 3, 6, 9, 12 };
            var now = DateTime.Now;
            var cursor = new DateTime(now.Year, now.Month, 1).AddMonths(-1);
            var added = 0;
            for (var i = 0; i < 24 && added < 8; i++)
            {
                var dt = cursor.AddMonths(i);
                if (Array.IndexOf(months, dt.Month) < 0)
                    continue;
                if (dt.AddDays(45) < now)
                    continue;
                result.Add($"{root} {dt.Month:D2}-{(dt.Year % 100):D2}");
                added++;
            }
            return result;
        }

        private static string? TryMonthYearToNt(string root, string monthYear)
        {
            if (monthYear.Contains("-"))
                return root + " " + monthYear;
            string[] months = { "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC" };
            for (var m = 0; m < months.Length; m++)
            {
                if (!monthYear.StartsWith(months[m], StringComparison.Ordinal))
                    continue;
                var yearPart = monthYear.Substring(months[m].Length);
                if (yearPart.Length == 2 && int.TryParse(yearPart, out _))
                    return $"{root} {(m + 1):D2}-{yearPart}";
                if (yearPart.Length == 4 && int.TryParse(yearPart, out var yyyy))
                    return $"{root} {(m + 1):D2}-{(yyyy % 100):D2}";
            }
            return null;
        }
#endif

        private static HistoricalDataResponse Fail(string instrument, string correlationId, string code, string message)
        {
            return new HistoricalDataResponse
            {
                Instrument = instrument ?? "",
                CorrelationId = correlationId ?? "",
                Code = code,
                Message = message ?? "",
            };
        }

        private void Log(string message) => _log?.Invoke("[FabricData] " + message);
    }
}
