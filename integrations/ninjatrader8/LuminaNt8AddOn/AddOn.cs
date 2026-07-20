// LUMINA Execution Fabric — NT8 AddOn entry point.
// Wire protocol: gRPC server on localhost (ADR-0035). WebSocket client path is superseded.

namespace LuminaNt8AddOn
{
    /// <summary>
    /// NT8 AddOn entry point. Hosts Execution Fabric gRPC on State.Active (Phase 0 PR-C).
    /// </summary>
    public class AddOn : NinjaTrader.NinjaScript.AddOnBase
    {
        // TODO(PR-C): FabricGrpcHost _host;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "LUMINA Execution Fabric";
                Description = "Native gRPC execution plane for LUMINA Brain (localhost only)";
            }
            else if (State == State.Active)
            {
                // TODO(PR-C): start gRPC server on 127.0.0.1:50051, load fabric.json, auth token.
                // Keep Safety watchdog alive independent of Brain process.
            }
            else if (State == State.Terminated)
            {
                // TODO(PR-C): graceful shutdown; apply disconnect policy (cancel / optional flatten).
            }
        }
    }
}
