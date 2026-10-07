using System;
using System.Collections.Generic;

namespace Lumina.Execution.Fabric.MarketData
{
    /// <summary>
    /// Canonical live bar periods (ADR-0054). String SSOT for Fabric (no NT types).
    /// </summary>
    public static class BarPeriodNames
    {
        public static readonly string[] CanonicalLive =
        {
            "1m", "5m", "15m", "30m", "60m", "240m",
        };

        public static string? Canonical(string? raw)
        {
            var token = (raw ?? "").Trim().ToLowerInvariant().Replace(" ", "");
            switch (token)
            {
                case "":
                case "1":
                case "1m":
                case "1min":
                case "minute":
                    return "1m";
                case "5":
                case "5m":
                case "5min":
                    return "5m";
                case "15":
                case "15m":
                case "15min":
                    return "15m";
                case "30":
                case "30m":
                case "30min":
                    return "30m";
                case "60":
                case "60m":
                case "60min":
                case "1h":
                    return "60m";
                case "240":
                case "240m":
                case "240min":
                case "4h":
                    return "240m";
                default:
                    return null;
            }
        }

        public static IReadOnlyList<string> ResolveSubscribePeriods(IEnumerable<string>? repeated, string? single)
        {
            var list = new List<string>();
            if (repeated != null)
            {
                foreach (var item in repeated)
                {
                    var canonical = Canonical(item);
                    if (canonical != null && !list.Contains(canonical))
                        list.Add(canonical);
                }
            }
            if (list.Count > 0)
                return list;
            var one = Canonical(single);
            if (one != null && one != "1m")
                return new[] { one };
            return CanonicalLive;
        }
    }
}
