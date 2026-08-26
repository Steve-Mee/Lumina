using System;
using System.Collections.Generic;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Execution
{
    /// <summary>
    /// Optional async order/fill/position events from a live gateway (NT Account callbacks).
    /// FabricGrpcHost wires this to TradingStream broadcast when present.
    /// </summary>
    public interface IOrderEventSource
    {
        event Action<IReadOnlyList<OrderEvent>>? OrderEventsProduced;

        event Action<IReadOnlyList<PositionUpdate>>? PositionUpdatesProduced;
    }
}
