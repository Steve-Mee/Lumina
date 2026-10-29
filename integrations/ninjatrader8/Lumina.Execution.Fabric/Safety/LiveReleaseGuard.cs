using System;

namespace Lumina.Execution.Fabric.Safety
{
    /// <summary>
    /// Fabric-side LIVE_RELEASE defense in depth (ADR-0061 / S1).
    /// HMAC verification lives in the Python Risk Core. A Fabric boolean is
    /// never sufficient. S1 keeps the live account path closed.
    /// </summary>
    public static class LiveReleaseGuard
    {
        public const string LiveAccountPathClosedS1 = "live_account_path_closed_s1";
        public const string LiveReleaseRequired = "live_release_required";
        public const string RealAccountBlocked = "real_account_blocked_pending_promotion_adr";

        public static bool IsRealMode(string? modeContext)
        {
            return string.Equals((modeContext ?? string.Empty).Trim(), "real", StringComparison.OrdinalIgnoreCase);
        }

        /// <summary>
        /// Deny a REAL place. <paramref name="liveReleaseEnabled"/> without
        /// Brain HMAC attestation never allows. S1 never opens live orders
        /// even when both flags are true.
        /// </summary>
        public static string? DenyRealPlace(string? modeContext, bool liveReleaseEnabled, bool brainAttested)
        {
            if (!IsRealMode(modeContext))
                return null;
            if (brainAttested && liveReleaseEnabled)
                return LiveAccountPathClosedS1;
            if (!brainAttested)
                return liveReleaseEnabled ? LiveAccountPathClosedS1 : LiveReleaseRequired;
            return LiveAccountPathClosedS1;
        }
    }
}
