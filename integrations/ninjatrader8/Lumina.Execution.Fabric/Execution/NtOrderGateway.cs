using System;
using System.Collections.Generic;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Execution
{
    /// <summary>
    /// Live NinjaTrader Account order gateway skeleton (PR-E).
    /// Fail-closed until a real NT Account handle is bound via <see cref="BindAccount"/>.
    /// Phase PR-E does not call NT APIs yet — bind is the extension point for PR-F / NT wiring.
    /// </summary>
    public sealed class NtOrderGateway : IOrderGateway
    {
        private readonly object _gate = new object();
        private object? _accountHandle;
        private string _accountName;

        public NtOrderGateway(string accountName = "Sim101")
        {
            _accountName = accountName ?? "Sim101";
        }

        public string AccountName
        {
            get
            {
                lock (_gate)
                    return _accountName;
            }
        }

        public string GatewayKind => "nt";

        public bool IsBound
        {
            get
            {
                lock (_gate)
                    return _accountHandle != null;
            }
        }

        /// <summary>
        /// Bind a NinjaTrader Account (or adapter) instance. Until bound, all orders reject fail-closed.
        /// </summary>
        public void BindAccount(object account, string? accountName = null)
        {
            if (account == null)
                throw new ArgumentNullException(nameof(account));
            lock (_gate)
            {
                _accountHandle = account;
                if (!string.IsNullOrWhiteSpace(accountName))
                    _accountName = accountName!;
            }
        }

        public void Unbind()
        {
            lock (_gate)
            {
                _accountHandle = null;
            }
        }

        public AccountMetrics GetAccountMetrics()
        {
            // Live snapshot requires NT Account — return empty fail-safe metrics when unbound.
            return new AccountMetrics
            {
                AccountName = AccountName,
                Currency = "USD",
                Balance = 0,
                Equity = 0,
            };
        }

        public IReadOnlyList<PositionUpdate> GetPositions() => Array.Empty<PositionUpdate>();

        public IReadOnlyList<WorkingOrder> GetWorkingOrders() => Array.Empty<WorkingOrder>();

        public IReadOnlyList<OrderEvent> PlaceOrder(PlaceOrderCommand command)
        {
            return new[] { Reject(command?.ClientOrderId, command?.CorrelationId, command?.Instrument, command?.Action ?? OrderAction.Unspecified, NotBoundReason()) };
        }

        public IReadOnlyList<OrderEvent> CancelOrder(CancelOrderCommand command)
        {
            return new[]
            {
                Reject(command?.ClientOrderId, command?.CorrelationId, "", OrderAction.Unspecified, NotBoundReason()),
            };
        }

        public IReadOnlyList<OrderEvent> ModifyOrder(ModifyOrderCommand command)
        {
            return new[]
            {
                Reject(command?.ClientOrderId, command?.CorrelationId, "", OrderAction.Unspecified, NotBoundReason()),
            };
        }

        public IReadOnlyList<OrderEvent> Flatten(FlattenCommand command)
        {
            return new[]
            {
                Reject("flatten", command?.CorrelationId, command?.Instrument ?? "", OrderAction.Unspecified, NotBoundReason()),
            };
        }

        public IReadOnlyList<OrderEvent> CancelNonProtected(string reason)
        {
            // No working book when unbound.
            return Array.Empty<OrderEvent>();
        }

        private string NotBoundReason()
        {
            return IsBound
                ? "nt_gateway_not_implemented"
                : "nt_account_not_bound";
        }

        private static OrderEvent Reject(string? clientOrderId, string? correlationId, string? instrument, OrderAction action, string reason)
        {
            return new OrderEvent
            {
                ClientOrderId = clientOrderId ?? "",
                State = OrderState.Rejected,
                RejectionReason = reason,
                Instrument = instrument ?? "",
                Action = action,
                CorrelationId = correlationId ?? "",
                TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            };
        }
    }
}
