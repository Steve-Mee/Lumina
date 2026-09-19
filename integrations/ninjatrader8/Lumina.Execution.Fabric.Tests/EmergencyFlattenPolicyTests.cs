using Lumina.Execution.Fabric.Safety;
using Xunit;

namespace Lumina.Execution.Fabric.Tests
{
    public sealed class EmergencyFlattenPolicyTests
    {
        [Theory]
        [InlineData(false, 1, 0, 1, "unarmed")]
        [InlineData(false, 1, 0, 0, "unarmed")]
        [InlineData(true, 1, 0, 0, "no_session_orders")]
        [InlineData(true, 0, 0, 1, "empty_book")]
        [InlineData(true, 0, 0, 0, "no_session_orders")]
        public void DenyReason_blocks_autonomous_close(
            bool armed, int positions, int working, int touched, string expected)
        {
            Assert.Equal(expected, EmergencyFlattenPolicy.DenyReason(armed, positions, working, touched));
        }

        [Fact]
        public void DenyReason_allows_only_armed_session_owned_open_book()
        {
            Assert.Null(EmergencyFlattenPolicy.DenyReason(true, 1, 0, 1));
            Assert.Null(EmergencyFlattenPolicy.DenyReason(true, 0, 1, 2));
        }

        [Fact]
        public void Leftover_position_without_session_place_is_never_flattened()
        {
            // The incident: MES leftover, NT start, Lumina never placed this process.
            Assert.Equal("unarmed", EmergencyFlattenPolicy.DenyReason(false, 1, 0, 0));
            Assert.Equal("no_session_orders", EmergencyFlattenPolicy.DenyReason(true, 1, 0, 0));
        }
    }
}
