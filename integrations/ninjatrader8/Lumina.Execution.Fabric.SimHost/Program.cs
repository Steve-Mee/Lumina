using System;
using System.Threading;
using Lumina.Execution.Fabric;
using Lumina.Execution.Fabric.Execution;

namespace Lumina.Execution.Fabric.SimHost
{
    /// <summary>
    /// Standalone SIM Fabric gRPC host for Phase 0 E2E without NinjaTrader.
    /// Usage:
    ///   set LUMINA_FABRIC_TOKEN=test-token
    ///   Lumina.Execution.Fabric.SimHost.exe
    /// </summary>
    internal static class Program
    {
        private static int Main(string[] args)
        {
            var config = FabricConfig.LoadDefault();
            for (var i = 0; i < args.Length; i++)
            {
                if (args[i] == "--port" && i + 1 < args.Length && int.TryParse(args[i + 1], out var p))
                {
                    config.BindPort = p;
                    i++;
                }
                else if (args[i] == "--account" && i + 1 < args.Length)
                {
                    config.AccountName = args[i + 1];
                    i++;
                }
                else if (args[i] == "--token" && i + 1 < args.Length)
                {
                    config.AuthToken = args[i + 1];
                    i++;
                }
                else if (args[i] == "--heartbeat-timeout-ms" && i + 1 < args.Length &&
                         int.TryParse(args[i + 1], out var hb))
                {
                    config.HeartbeatTimeoutMs = hb;
                    i++;
                }
            }

            // Dev convenience: if no token configured, use a fixed SIM token.
            if (string.IsNullOrEmpty(config.ResolveToken()))
            {
                config.AuthToken = "sim-dev-token";
                Console.WriteLine("[SimHost] WARNING: using default AuthToken=sim-dev-token (dev only)");
            }

            var gateway = new SimOrderGateway(config.AccountName);
            using var host = new FabricGrpcHost(config, gateway, msg => Console.WriteLine(msg));
            try
            {
                host.Start();
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("Failed to start Fabric host: " + ex);
                return 1;
            }

            Console.WriteLine("Press Ctrl+C to stop.");
            var exit = new ManualResetEventSlim(false);
            Console.CancelKeyPress += (_, e) =>
            {
                e.Cancel = true;
                exit.Set();
            };
            exit.Wait();
            host.Stop();
            return 0;
        }
    }
}
