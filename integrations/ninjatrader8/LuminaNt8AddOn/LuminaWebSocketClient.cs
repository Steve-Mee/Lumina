// OBSOLETE — WebSocket client to Core /ws/ninjatrader/v1 is superseded by ADR-0035.
// Execution Fabric hosts gRPC on the NT side; Brain is the gRPC client.

using System;

namespace LuminaNt8AddOn
{
    [Obsolete("Superseded by Fabric gRPC host (ADR-0035). Use Lumina.Execution.Fabric.FabricGrpcHost.")]
    public sealed class LuminaWebSocketClient
    {
        public void Connect()
        {
            throw new NotSupportedException(
                "WebSocket bridge superseded by Execution Fabric gRPC. See docs/adr/0035-execution-fabric-grpc.md");
        }

        public void Disconnect()
        {
        }
    }
}
