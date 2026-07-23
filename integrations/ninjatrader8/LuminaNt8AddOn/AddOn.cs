// LUMINA Execution Fabric — NT8 AddOn entry point (ADR-0035 / PR-C).
// Hosts gRPC Fabric on localhost. When NinjaTrader.Core is unavailable at build time,
// FABRIC_STANDALONE stubs the AddOnBase lifecycle for compile checks.

using System;
using Lumina.Execution.Fabric;
using Lumina.Execution.Fabric.Execution;

#if !FABRIC_STANDALONE
using NinjaTrader.NinjaScript;
#endif

namespace LuminaNt8AddOn
{
#if FABRIC_STANDALONE
    /// <summary>Compile-time stub when NinjaTrader.Core is not referenced.</summary>
    public abstract class AddOnBaseStub
    {
        protected enum StateKind { SetDefaults, Active, Terminated }
        protected StateKind State { get; set; }
        protected string Name { get; set; } = "";
        protected string Description { get; set; } = "";
        protected abstract void OnStateChange();
    }
#endif

    /// <summary>
    /// NT8 AddOn entry point. Hosts Execution Fabric gRPC on State.Active.
    /// Phase 0 uses <see cref="SimOrderGateway"/> until a live NT order gateway is wired (PR-D).
    /// </summary>
#if FABRIC_STANDALONE
    public class AddOn : AddOnBaseStub
#else
    public class AddOn : AddOnBase
#endif
    {
        private FabricGrpcHost? _host;

        protected override void OnStateChange()
        {
#if FABRIC_STANDALONE
            // Standalone: methods still document lifecycle; host started via SimHost for E2E.
            if (State == StateKind.SetDefaults)
            {
                Name = "LUMINA Execution Fabric";
                Description = "Native gRPC execution plane for LUMINA Brain (localhost only)";
            }
#else
            if (State == State.SetDefaults)
            {
                Name = "LUMINA Execution Fabric";
                Description = "Native gRPC execution plane for LUMINA Brain (localhost only)";
            }
            else if (State == State.Active)
            {
                StartFabricHost();
            }
            else if (State == State.Terminated)
            {
                StopFabricHost();
            }
#endif
        }

        /// <summary>Start Fabric host (also usable from tests / standalone bootstrap).</summary>
        public void StartFabricHost()
        {
            if (_host != null)
                return;
            try
            {
                var config = FabricConfig.LoadDefault();
                // PR-E: GatewayMode sim|nt — NT gateway is fail-closed until Account is bound.
                var gateway = FabricGrpcHost.CreateGateway(config);
                _host = new FabricGrpcHost(config, gateway, msg =>
                {
#if !FABRIC_STANDALONE
                    // Prefer NT Output window when available.
                    try { NinjaTrader.Code.Output.Process(msg, NinjaTrader.NinjaScript.PrintTo.OutputTab1); }
                    catch { System.Diagnostics.Debug.WriteLine(msg); }
#else
                    System.Diagnostics.Debug.WriteLine(msg);
#endif
                });
                _host.Start();
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine("[LUMINA Fabric] failed to start: " + ex);
                _host = null;
                throw;
            }
        }

        public void StopFabricHost()
        {
            try
            {
                _host?.Stop();
            }
            finally
            {
                _host = null;
            }
        }
    }
}
