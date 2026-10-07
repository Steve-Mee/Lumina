using System;
using Lumina.Execution.Fabric.MarketData;
#if !FABRIC_STANDALONE
using NinjaTrader.Data;
#endif

namespace NinjaTrader.NinjaScript.AddOns
{
    /// <summary>Native NT minute periods with session TradingHours (ADR-0054).</summary>
    internal static class NtBarPeriods
    {
        public static int LiveBarsBack(string canonical)
        {
            switch (canonical)
            {
                case "5m": return 1500;
                case "15m": return 1000;
                case "30m": return 800;
                case "60m": return 500;
                case "240m": return 400;
                default: return 2000;
            }
        }

#if !FABRIC_STANDALONE
        public static bool TryParse(string? raw, out BarsPeriodType type, out int value, out string canonical)
        {
            type = BarsPeriodType.Minute;
            value = 1;
            canonical = BarPeriodNames.Canonical(raw) ?? "";
            if (string.IsNullOrEmpty(canonical))
                return false;
            value = canonical switch
            {
                "5m" => 5,
                "15m" => 15,
                "30m" => 30,
                "60m" => 60,
                "240m" => 240,
                _ => 1,
            };
            return true;
        }
#endif
    }
}
