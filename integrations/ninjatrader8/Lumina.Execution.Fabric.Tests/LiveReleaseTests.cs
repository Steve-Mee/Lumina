using Lumina.Execution.Fabric.Safety;
using Xunit;

namespace Lumina.Execution.Fabric.Tests
{
    public sealed class LiveReleaseTests
    {
        [Fact]
        public void Real_mode_without_brain_attestation_is_rejected_even_on_sim_name()
        {
            Assert.Equal(
                LiveReleaseGuard.LiveReleaseRequired,
                LiveReleaseGuard.DenyRealPlace("real", liveReleaseEnabled: false, brainAttested: false));
            Assert.True(SimAccountWhitelist.IsPaperAccountName("Sim101"));
        }

        [Fact]
        public void Fabric_boolean_without_hmac_attestation_is_not_sufficient()
        {
            Assert.Equal(
                LiveReleaseGuard.LiveAccountPathClosedS1,
                LiveReleaseGuard.DenyRealPlace("real", liveReleaseEnabled: true, brainAttested: false));
        }

        [Fact]
        public void S1_keeps_live_path_closed_even_when_brain_attested()
        {
            Assert.Equal(
                LiveReleaseGuard.LiveAccountPathClosedS1,
                LiveReleaseGuard.DenyRealPlace("real", liveReleaseEnabled: true, brainAttested: true));
        }

        [Fact]
        public void Non_real_modes_are_not_live_release_gated_here()
        {
            Assert.Null(LiveReleaseGuard.DenyRealPlace("sim", liveReleaseEnabled: false, brainAttested: false));
            Assert.Null(LiveReleaseGuard.DenyRealPlace("sim_real_guard", true, true));
        }

        [Fact]
        public void Live_brokerage_name_stays_blocked_pending_promotion_adr()
        {
            Assert.False(SimAccountWhitelist.IsPaperAccountName("APEX12345"));
            Assert.Equal(
                LiveReleaseGuard.LiveAccountPathClosedS1,
                LiveReleaseGuard.DenyRealPlace("real", liveReleaseEnabled: false, brainAttested: true));
        }
    }
}
