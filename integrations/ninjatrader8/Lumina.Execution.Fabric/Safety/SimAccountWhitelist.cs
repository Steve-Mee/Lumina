using System;
using System.Collections.Generic;

namespace Lumina.Execution.Fabric.Safety
{
    /// <summary>
    /// Explicit SIM account membership. Prefix helpers never allow.
    /// Empty or omitted list denies every account (ADR-0061 / S1).
    /// </summary>
    public static class SimAccountWhitelist
    {
        public const string AccountUnknown = "ninjatrader_account_unknown";
        public const string Empty = "sim_whitelist_empty";
        public const string NotWhitelisted = "sim_account_not_whitelisted";

        public static string[] Canonical(IEnumerable<string>? names)
        {
            if (names == null)
                return Array.Empty<string>();
            var seen = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var ordered = new List<string>();
            foreach (var raw in names)
            {
                var label = (raw ?? string.Empty).Trim();
                if (label.Length == 0)
                    continue;
                if (seen.Add(label))
                    ordered.Add(label);
            }
            return ordered.ToArray();
        }

        public static bool IsBrokerDemoName(string name)
        {
            var label = (name ?? string.Empty).Trim();
            return label.StartsWith("DEMO", StringComparison.OrdinalIgnoreCase);
        }

        public static bool IsLocalSimName(string name)
        {
            var label = (name ?? string.Empty).Trim();
            if (label.Length == 0)
                return false;
            return label.StartsWith("Sim", StringComparison.OrdinalIgnoreCase)
                || label.IndexOf("Sim101", StringComparison.OrdinalIgnoreCase) >= 0
                || label.IndexOf("Playback", StringComparison.OrdinalIgnoreCase) >= 0
                || label.IndexOf("Backtest", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        public static bool IsPaperAccountName(string name)
        {
            return IsLocalSimName(name) || IsBrokerDemoName(name);
        }

        public static bool OnList(string name, IEnumerable<string>? whitelist)
        {
            var label = (name ?? string.Empty).Trim();
            if (label.Length == 0)
                return false;
            var items = Canonical(whitelist);
            if (items.Length == 0)
                return false;
            foreach (var item in items)
            {
                if (string.Equals(item, label, StringComparison.OrdinalIgnoreCase))
                    return true;
            }
            return false;
        }

        /// <summary>
        /// Fail-closed admit for a place on the NT account gateway.
        /// Prefix match is never an allow.
        /// </summary>
        public static string? DenyReason(string accountName, IEnumerable<string>? whitelist)
        {
            var label = (accountName ?? string.Empty).Trim();
            if (label.Length == 0)
                return AccountUnknown;
            var items = Canonical(whitelist);
            if (items.Length == 0)
                return Empty;
            if (!IsPaperAccountName(label))
                return NotWhitelisted;
            if (!OnList(label, items))
                return NotWhitelisted;
            return null;
        }
    }
}
