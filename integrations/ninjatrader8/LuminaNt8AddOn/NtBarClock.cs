using System;

namespace NinjaTrader.NinjaScript.AddOns
{
    /// <summary>
    /// NT GetTime is typically Unspecified local wall clock of the NT process.
    /// Convert honestly to unix-ms UTC. Do not assume the stamp is already UTC.
    /// </summary>
    internal static class NtBarClock
    {
        public static long ToUnixMs(DateTime ts)
        {
            if (ts.Kind == DateTimeKind.Utc)
                return new DateTimeOffset(ts, TimeSpan.Zero).ToUnixTimeMilliseconds();
            if (ts.Kind == DateTimeKind.Local)
                return new DateTimeOffset(ts).ToUnixTimeMilliseconds();
            var offset = TimeZoneInfo.Local.GetUtcOffset(ts);
            return new DateTimeOffset(DateTime.SpecifyKind(ts, DateTimeKind.Unspecified), offset)
                .ToUnixTimeMilliseconds();
        }
    }
}
