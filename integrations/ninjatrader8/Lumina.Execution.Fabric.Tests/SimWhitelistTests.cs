using Lumina.Execution.Fabric.Safety;
using Xunit;

namespace Lumina.Execution.Fabric.Tests
{
    public sealed class SimWhitelistTests
    {
        [Fact]
        public void Empty_whitelist_denies_Sim101()
        {
            Assert.Equal(SimAccountWhitelist.Empty, SimAccountWhitelist.DenyReason("Sim101", null));
            Assert.Equal(SimAccountWhitelist.Empty, SimAccountWhitelist.DenyReason("Sim101", System.Array.Empty<string>()));
        }

        [Fact]
        public void Name_not_on_list_is_rejected()
        {
            Assert.Equal(
                SimAccountWhitelist.NotWhitelisted,
                SimAccountWhitelist.DenyReason("Sim202", new[] { "Sim101" }));
        }

        [Fact]
        public void Prefix_Sim999_not_on_list_is_rejected()
        {
            Assert.Equal(
                SimAccountWhitelist.NotWhitelisted,
                SimAccountWhitelist.DenyReason("Sim999", new[] { "Sim101" }));
            Assert.True(SimAccountWhitelist.IsLocalSimName("Sim999"));
        }

        [Fact]
        public void Sim101_on_list_passes_this_check()
        {
            Assert.Null(SimAccountWhitelist.DenyReason("Sim101", new[] { "Sim101" }));
            Assert.Null(SimAccountWhitelist.DenyReason("sim101", new[] { "Sim101" }));
        }

        [Fact]
        public void Live_name_is_rejected_even_if_operator_lists_it()
        {
            Assert.Equal(
                SimAccountWhitelist.NotWhitelisted,
                SimAccountWhitelist.DenyReason("LiveAcct", new[] { "LiveAcct" }));
        }

        [Fact]
        public void Unknown_account_is_rejected()
        {
            Assert.Equal(SimAccountWhitelist.AccountUnknown, SimAccountWhitelist.DenyReason("  ", new[] { "Sim101" }));
        }

        [Fact]
        public void Prefix_on_list_does_not_admit_longer_name()
        {
            Assert.Equal(
                SimAccountWhitelist.NotWhitelisted,
                SimAccountWhitelist.DenyReason("Sim101", new[] { "Sim" }));
            Assert.Equal(
                SimAccountWhitelist.NotWhitelisted,
                SimAccountWhitelist.DenyReason("Sim1010", new[] { "Sim101" }));
        }

        [Fact]
        public void Homoglyph_and_zero_width_do_not_match()
        {
            Assert.Equal(
                SimAccountWhitelist.NotWhitelisted,
                SimAccountWhitelist.DenyReason("\u0405im101", new[] { "Sim101" }));
            Assert.Equal(
                SimAccountWhitelist.NotWhitelisted,
                SimAccountWhitelist.DenyReason("Sim101\u200b", new[] { "Sim101" }));
        }

        [Fact]
        public void Surrounding_whitespace_is_trimmed_not_used_as_prefix()
        {
            Assert.Null(SimAccountWhitelist.DenyReason(" Sim101 ", new[] { "Sim101" }));
        }
    }
}
