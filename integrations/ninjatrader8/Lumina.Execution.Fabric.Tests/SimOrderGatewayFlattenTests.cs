using System.Linq;
using Lumina.Execution.Fabric.Execution;
using Lumina.Execution.V1;
using Xunit;

namespace Lumina.Execution.Fabric.Tests
{
    public sealed class SimOrderGatewayFlattenTests
    {
        [Fact]
        public void CancelNonProtected_skips_flatten_and_close_ids()
        {
            var gw = new SimOrderGateway();
            gw.PlaceOrder(Limit("entry-1", OrderAction.Buy, 1));
            gw.PlaceOrder(Limit("flatten-abc", OrderAction.Sell, 1));
            gw.PlaceOrder(Limit("Close", OrderAction.Sell, 1));

            var cancelled = gw.CancelNonProtected("test");

            Assert.Single(cancelled);
            Assert.Equal("entry-1", cancelled[0].ClientOrderId);
            var working = gw.GetWorkingOrders().Select(o => o.ClientOrderId).OrderBy(x => x).ToArray();
            Assert.Equal(new[] { "Close", "flatten-abc" }, working);
        }

        [Fact]
        public void Flatten_cancels_entries_then_closes_position_without_self_cancel()
        {
            var gw = new SimOrderGateway();
            var buy = gw.PlaceOrder(new PlaceOrderCommand
            {
                ClientOrderId = "entry-mkt",
                Instrument = "MES",
                Action = OrderAction.Buy,
                Quantity = 1,
                OrderType = OrderType.Market,
            });
            Assert.Contains(buy, e => e.State == OrderState.Filled);
            Assert.Single(gw.GetPositions());

            gw.PlaceOrder(Limit("working-entry", OrderAction.Buy, 1));

            var events = gw.Flatten(new FlattenCommand { CorrelationId = "c1" });

            Assert.Contains(events, e => e.ClientOrderId == "working-entry" && e.State == OrderState.Cancelled);
            Assert.DoesNotContain(events, e =>
                e.State == OrderState.Cancelled && SimOrderGateway.IsFlattenOrCloseId(e.ClientOrderId));
            Assert.Contains(events, e =>
                e.ClientOrderId.StartsWith("flatten-") && e.State == OrderState.Filled);
            Assert.Empty(gw.GetPositions());
        }

        [Fact]
        public void PlaceOrder_records_session_touched_invalid_does_not()
        {
            var gw = new SimOrderGateway();
            Assert.Empty(gw.SessionTouchedInstruments);

            gw.PlaceOrder(new PlaceOrderCommand
            {
                ClientOrderId = "bad",
                Instrument = "",
                Action = OrderAction.Buy,
                Quantity = 1,
                OrderType = OrderType.Market,
            });
            Assert.Empty(gw.SessionTouchedInstruments);

            gw.PlaceOrder(new PlaceOrderCommand
            {
                ClientOrderId = "ok",
                Instrument = "MES SEP26",
                Action = OrderAction.Buy,
                Quantity = 1,
                OrderType = OrderType.Market,
            });
            Assert.Contains("MES SEP26", gw.SessionTouchedInstruments);
        }

        [Fact]
        public void Flatten_empty_book_is_noop_not_a_close_order()
        {
            var gw = new SimOrderGateway();
            var events = gw.Flatten(new FlattenCommand());
            Assert.Single(events);
            Assert.Equal("flat-noop", events[0].NtOrderId);
            Assert.Equal("flatten_no_open_positions", events[0].RejectionReason);
            Assert.Empty(gw.GetWorkingOrders());
        }

        [Theory]
        [InlineData("Close", true)]
        [InlineData("close", true)]
        [InlineData("flatten-xyz", true)]
        [InlineData("LUMINA|abc", false)]
        [InlineData("entry-1", false)]
        [InlineData("", false)]
        public void IsFlattenOrCloseId_recognizes_risk_reducing_names(string id, bool expected)
        {
            Assert.Equal(expected, SimOrderGateway.IsFlattenOrCloseId(id));
        }

        private static PlaceOrderCommand Limit(string clientId, OrderAction action, int qty)
        {
            return new PlaceOrderCommand
            {
                ClientOrderId = clientId,
                Instrument = "MES",
                Action = action,
                Quantity = qty,
                OrderType = OrderType.Limit,
                Price = 21000,
            };
        }
    }
}
