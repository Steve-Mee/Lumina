// ============================================================
// LUMINA Execution Fabric — NinjaTrader 8 AddOn host entry
// Capital Preservation First | Fail-Closed | GatewayMode=sim first
// ============================================================

#region Using declarations
using System;
using System.IO;
using Lumina.Execution.Fabric;
using Lumina.Execution.Fabric.Execution;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    /// <summary>
    /// Starts Execution Fabric gRPC host inside NT8 (ADR-0035).
    /// Prefer GatewayMode=sim until NtOrderGateway is bound to a live Account.
    /// Config: %APPDATA%\LUMINA\fabric.json — token via LUMINA_FABRIC_TOKEN (User env).
    /// </summary>
    public class LuminaNt8AddOn : AddOnBase
    {
        private FabricGrpcHost? _host;
        private bool _hostStarted;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "LUMINA Execution Fabric — Native gRPC bridge. Capital preservation first.";
                Name = "LUMINA Execution Fabric";
            }
            else if (State == State.Active)
            {
                StartFabricHost();
            }
            else if (State == State.Terminated)
            {
                StopFabricHost();
            }
        }

        private void StartFabricHost()
        {
            if (_hostStarted)
                return;

            try
            {
                var config = LoadFabricConfig();
                var tokenPresent = !string.IsNullOrWhiteSpace(config.ResolveToken());

                Print("================================================");
                Print("[FabricHost] LUMINA Execution Fabric starting...");
                Print("[FabricHost] AccountName      = " + config.AccountName);
                Print("[FabricHost] Bind             = " + config.BindHost + ":" + config.BindPort);
                Print("[FabricHost] GatewayMode      = " + config.GatewayMode);
                Print("[FabricHost] HeartbeatTimeout = " + config.HeartbeatTimeoutMs + " ms");
                Print("[FabricHost] FlattenOnTimeout = " + config.FlattenOnTimeout);
                Print("[FabricHost] AuthToken set    = " + (tokenPresent ? "YES" : "NO"));
                Print("================================================");

                if (!tokenPresent)
                {
                    Print("[FabricHost] FATAL: LUMINA_FABRIC_TOKEN not set (User env) and no fabric.json AuthToken.");
                    Print("[FabricHost] Generate the token in Lumina first-boot credentials, then restart NT8.");
                    return;
                }

                IOrderGateway gateway = FabricGrpcHost.CreateGateway(config);
                _host = new FabricGrpcHost(config, gateway, msg => Print(msg));
                _host.Start();
                _hostStarted = true;
                Print("[FabricHost] Host started successfully gateway=" + gateway.GatewayKind
                      + " audit=" + (_host.AuditPath ?? "(default)"));
            }
            catch (Exception ex)
            {
                Print("[FabricHost] FATAL: " + ex);
                try
                {
                    _host?.Dispose();
                }
                catch
                {
                    // ignore dispose after failed start
                }
                _host = null;
                _hostStarted = false;
            }
        }

        private void StopFabricHost()
        {
            if (!_hostStarted && _host == null)
                return;

            try
            {
                Print("[FabricHost] Stopping host (Terminated)...");
                _host?.Stop();
                _host?.Dispose();
                _host = null;
                _hostStarted = false;
                Print("[FabricHost] Host stopped cleanly.");
            }
            catch (Exception ex)
            {
                Print("[FabricHost] Error while stopping: " + ex.Message);
            }
        }

        private FabricConfig LoadFabricConfig()
        {
            try
            {
                var path = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "LUMINA",
                    "fabric.json");

                if (File.Exists(path))
                {
                    Print("[Fabric] Config file found: " + path);
                    return FabricConfig.LoadFromFile(path);
                }

                Print("[Fabric] No fabric.json found — using defaults (GatewayMode=sim).");
            }
            catch (Exception ex)
            {
                Print("[Fabric] Could not load config: " + ex.Message + " — using defaults.");
            }

            return new FabricConfig();
        }
    }
}
