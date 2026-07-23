using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Execution
{
    /// <summary>
    /// In-memory SIM gateway for Phase 0 E2E without NinjaTrader.Core.
    /// Market orders fill immediately at a synthetic price.
    /// </summary>
    public sealed class SimOrderGateway : IOrderGateway
    {
        private readonly object _gate = new object();
        private readonly ConcurrentDictionary<string, WorkingOrder> _working =
            new ConcurrentDictionary<string, WorkingOrder>(StringComparer.Ordinal);
        private readonly ConcurrentDictionary<string, PositionUpdate> _positions =
            new ConcurrentDictionary<string, PositionUpdate>(StringComparer.OrdinalIgnoreCase);
        private int _seq;

        public SimOrderGateway(string accountName = "Sim101")
        {
            AccountName = accountName ?? "Sim101";
            Balance = 100_000.0;
            Equity = 100_000.0;
        }

        public string AccountName { get; }
        public double Balance { get; private set; }
        public double Equity { get; private set; }

        public AccountMetrics GetAccountMetrics()
        {
            return new AccountMetrics
            {
                Balance = Balance,
                Equity = Equity,
                AvailableMargin = Equity * 0.9,
                RealizedPnlToday = Equity - 100_000.0,
                Currency = "USD",
                AccountName = AccountName,
            };
        }

        public IReadOnlyList<PositionUpdate> GetPositions() =>
            _positions.Values.Where(p => p.Quantity != 0).ToList();

        public IReadOnlyList<WorkingOrder> GetWorkingOrders() => _working.Values.ToList();

        public IReadOnlyList<OrderEvent> PlaceOrder(PlaceOrderCommand command)
        {
            if (command == null)
                throw new ArgumentNullException(nameof(command));

            var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            var ntId = "sim-" + System.Threading.Interlocked.Increment(ref _seq);

            if (command.Quantity <= 0 || command.Action == OrderAction.Unspecified ||
                string.IsNullOrWhiteSpace(command.Instrument))
            {
                return new[]
                {
                    new OrderEvent
                    {
                        ClientOrderId = command.ClientOrderId ?? "",
                        NtOrderId = ntId,
                        State = OrderState.Rejected,
                        RejectionReason = "invalid_order_fields",
                        Instrument = command.Instrument ?? "",
                        Action = command.Action,
                        CorrelationId = command.CorrelationId ?? "",
                        TimestampUnixMs = now,
                    },
                };
            }

            var working = new WorkingOrder
            {
                ClientOrderId = command.ClientOrderId ?? "",
                NtOrderId = ntId,
                Instrument = command.Instrument,
                Action = command.Action,
                Quantity = command.Quantity,
                FilledQty = 0,
                OrderType = command.OrderType,
                Price = command.Price,
                StopPrice = command.StopPrice,
                State = OrderState.Working,
                Protected = command.Protected,
                ReduceOnly = command.ReduceOnly,
            };

            // Phase 0 SIM: market (and for simplicity all types) fill immediately.
            var fillPrice = command.Price > 0 ? command.Price : 21000.0 + (_seq % 50) * 0.25;
            working.FilledQty = command.Quantity;
            working.State = OrderState.Filled;
            // Do not keep filled orders in working book.
            ApplyFill(command.Instrument, command.Action, command.Quantity, fillPrice, now);

            var submitted = new OrderEvent
            {
                ClientOrderId = working.ClientOrderId,
                NtOrderId = ntId,
                State = OrderState.Working,
                Instrument = command.Instrument,
                Action = command.Action,
                LeavesQty = command.Quantity,
                CorrelationId = command.CorrelationId ?? "",
                TimestampUnixMs = now,
            };
            var filled = new OrderEvent
            {
                ClientOrderId = working.ClientOrderId,
                NtOrderId = ntId,
                State = OrderState.Filled,
                FilledQty = command.Quantity,
                AvgFillPrice = fillPrice,
                Instrument = command.Instrument,
                Action = command.Action,
                LeavesQty = 0,
                CorrelationId = command.CorrelationId ?? "",
                TimestampUnixMs = now,
            };
            return new[] { submitted, filled };
        }

        public IReadOnlyList<OrderEvent> CancelOrder(CancelOrderCommand command)
        {
            var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            WorkingOrder? found = null;
            if (!string.IsNullOrWhiteSpace(command?.ClientOrderId) &&
                _working.TryRemove(command!.ClientOrderId, out var byClient))
            {
                found = byClient;
            }
            else if (!string.IsNullOrWhiteSpace(command?.NtOrderId))
            {
                var pair = _working.FirstOrDefault(kv => kv.Value.NtOrderId == command!.NtOrderId);
                if (pair.Value != null && _working.TryRemove(pair.Key, out var byNt))
                    found = byNt;
            }

            if (found == null)
            {
                return new[]
                {
                    new OrderEvent
                    {
                        ClientOrderId = command?.ClientOrderId ?? "",
                        NtOrderId = command?.NtOrderId ?? "",
                        State = OrderState.Rejected,
                        RejectionReason = "order_not_found",
                        CorrelationId = command?.CorrelationId ?? "",
                        TimestampUnixMs = now,
                    },
                };
            }

            found.State = OrderState.Cancelled;
            return new[]
            {
                new OrderEvent
                {
                    ClientOrderId = found.ClientOrderId,
                    NtOrderId = found.NtOrderId,
                    State = OrderState.Cancelled,
                    Instrument = found.Instrument,
                    Action = found.Action,
                    CorrelationId = command?.CorrelationId ?? "",
                    TimestampUnixMs = now,
                },
            };
        }

        public IReadOnlyList<OrderEvent> Flatten(FlattenCommand command)
        {
            var events = new List<OrderEvent>();
            var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            var instrumentFilter = command?.Instrument ?? "";

            foreach (var pos in GetPositions().ToList())
            {
                if (!string.IsNullOrEmpty(instrumentFilter) &&
                    !string.Equals(pos.Instrument, instrumentFilter, StringComparison.OrdinalIgnoreCase))
                {
                    continue;
                }

                if (pos.Quantity == 0)
                    continue;

                var closeAction = string.Equals(pos.Side, "LONG", StringComparison.OrdinalIgnoreCase) ||
                                  string.Equals(pos.Side, "BUY", StringComparison.OrdinalIgnoreCase)
                    ? OrderAction.Sell
                    : OrderAction.Buy;

                var place = new PlaceOrderCommand
                {
                    ClientOrderId = "flatten-" + Guid.NewGuid().ToString("D"),
                    Instrument = pos.Instrument,
                    Action = closeAction,
                    Quantity = Math.Abs(pos.Quantity),
                    OrderType = OrderType.Market,
                    ReduceOnly = true,
                    CorrelationId = command?.CorrelationId ?? "",
                    ModeContext = "sim",
                };
                events.AddRange(PlaceOrder(place));
            }

            // Cancel any residual working.
            events.AddRange(CancelNonProtected("flatten"));
            if (events.Count == 0)
            {
                events.Add(new OrderEvent
                {
                    ClientOrderId = "flatten",
                    NtOrderId = "flat-noop",
                    State = OrderState.Submitted,
                    CorrelationId = command?.CorrelationId ?? "",
                    TimestampUnixMs = now,
                });
            }
            return events;
        }

        public IReadOnlyList<OrderEvent> CancelNonProtected(string reason)
        {
            var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            var events = new List<OrderEvent>();
            foreach (var kv in _working.ToArray())
            {
                if (kv.Value.Protected)
                    continue;
                if (_working.TryRemove(kv.Key, out var wo))
                {
                    events.Add(new OrderEvent
                    {
                        ClientOrderId = wo.ClientOrderId,
                        NtOrderId = wo.NtOrderId,
                        State = OrderState.Cancelled,
                        Instrument = wo.Instrument,
                        Action = wo.Action,
                        RejectionReason = reason ?? "cancel_non_protected",
                        TimestampUnixMs = now,
                    });
                }
            }
            return events;
        }

        private void ApplyFill(string instrument, OrderAction action, int qty, double price, long now)
        {
            lock (_gate)
            {
                _positions.TryGetValue(instrument, out var existing);
                var net = existing?.Quantity ?? 0;
                if (existing != null)
                {
                    // Normalize to signed qty: long positive.
                    if (string.Equals(existing.Side, "SHORT", StringComparison.OrdinalIgnoreCase) ||
                        string.Equals(existing.Side, "SELL", StringComparison.OrdinalIgnoreCase))
                    {
                        net = -Math.Abs(existing.Quantity);
                    }
                    else
                    {
                        net = Math.Abs(existing.Quantity);
                    }
                }

                var delta = action == OrderAction.Buy ? qty : -qty;
                var newNet = net + delta;
                if (newNet == 0)
                {
                    _positions.TryRemove(instrument, out _);
                }
                else
                {
                    _positions[instrument] = new PositionUpdate
                    {
                        Instrument = instrument,
                        Quantity = Math.Abs(newNet),
                        AvgPrice = price,
                        Side = newNet > 0 ? "LONG" : "SHORT",
                        TimestampUnixMs = now,
                    };
                }

                // Toy P&amp;L: mark equity slightly.
                Equity = Balance + newNet * 0.25;
            }
        }
    }
}
