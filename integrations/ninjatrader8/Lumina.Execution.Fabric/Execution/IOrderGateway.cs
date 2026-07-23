using System.Collections.Generic;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Execution
{
    /// <summary>
    /// Abstracts NT8 account order APIs so SIM (in-memory) and live NT gateways share the same Fabric service.
    /// </summary>
    public interface IOrderGateway
    {
        string AccountName { get; }

        AccountMetrics GetAccountMetrics();

        IReadOnlyList<PositionUpdate> GetPositions();

        IReadOnlyList<WorkingOrder> GetWorkingOrders();

        /// <summary>Place order. Returns order events (working/filled/rejected).</summary>
        IReadOnlyList<OrderEvent> PlaceOrder(PlaceOrderCommand command);

        IReadOnlyList<OrderEvent> CancelOrder(CancelOrderCommand command);

        IReadOnlyList<OrderEvent> ModifyOrder(ModifyOrderCommand command);

        IReadOnlyList<OrderEvent> Flatten(FlattenCommand command);

        /// <summary>Cancel all non-protected working orders (disconnect / timeout policy).</summary>
        IReadOnlyList<OrderEvent> CancelNonProtected(string reason);
    }
}
