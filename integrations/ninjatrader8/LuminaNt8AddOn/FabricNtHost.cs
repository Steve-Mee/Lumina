// ============================================================
// LUMINA — shared start/stop for NT8 Fabric host (callable from AddOn)
// Capital Preservation First | Fail-Closed | File log always
// ============================================================

#region Using declarations
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Lumina.Execution.Fabric;
using Lumina.Execution.Fabric.Execution;
using Lumina.Execution.Fabric.MarketData;
using Lumina.Execution.Fabric.Observability;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    /// <summary>
    /// Starts FabricGrpcHost inside the NT process with NT historical data.
    /// Invoked by the NinjaScript-compiled AddOn entry (guaranteed Active lifecycle).
    /// </summary>
    public static class FabricNtHost
    {
        private static readonly object Gate = new object();
        private static FabricGrpcHost? _host;
        private static bool _started;
        private static Action<string>? _print;

        public static bool IsRunning
        {
            get { lock (Gate) return _started && _host != null && _host.IsRunning; }
        }

        public static void SetPrint(Action<string>? print) => _print = print;

        /// <summary>
        /// JSON health snapshot for LUMINA Link window (reflection-friendly).
        /// Prefer in-process FabricRuntimeStatus; file is a fallback for external tools.
        /// </summary>
        public static string GetStatusJson()
        {
            try
            {
                // Keep host running flag honest if process state diverges.
                if (!IsRunning)
                {
                    var snap = FabricRuntimeStatus.Instance.Snapshot();
                    if (snap.TryGetValue("state", out var st) &&
                        string.Equals(st as string, "running", StringComparison.OrdinalIgnoreCase))
                    {
                        // Host claims running but local gate says no — report stopped.
                        return JsonSerializer.Serialize(new Dictionary<string, object?>
                        {
                            ["state"] = "stopped",
                            ["code"] = "not_running",
                            ["level"] = "RED",
                            ["meaning"] = "Bridge not running — open Lumina → Setup → Repair connection",
                            ["host"] = "nt_addon",
                            ["updated_utc"] = DateTime.UtcNow.ToString("o"),
                            ["pid"] = System.Diagnostics.Process.GetCurrentProcess().Id,
                        });
                    }
                }
                return FabricRuntimeStatus.Instance.ToJson();
            }
            catch (Exception ex)
            {
                return JsonSerializer.Serialize(new Dictionary<string, object?>
                {
                    ["state"] = "error",
                    ["code"] = "status_read_failed",
                    ["level"] = "RED",
                    ["meaning"] = "Status unavailable",
                    ["detail"] = ex.Message,
                    ["updated_utc"] = DateTime.UtcNow.ToString("o"),
                });
            }
        }

        public static bool Start()
        {
            lock (Gate)
            {
                // If a previous Stop hung mid-shutdown, _started may be true while port is dead.
                // Force clean restart so Systems Go / diagnostics can bind again.
                if (_started && _host != null && _host.IsRunning)
                {
                    Log("already running");
                    WriteStatusFromRuntime();
                    return true;
                }
                if (_host != null || _started)
                {
                    Log("stale host state — forcing stop before restart");
                    try
                    {
                        _host?.Stop();
                        _host?.Dispose();
                    }
                    catch (Exception ex)
                    {
                        Log("stale stop: " + ex.Message);
                    }
                    _host = null;
                    _started = false;
                    try { FabricRuntimeStatus.Instance.SetHostStopped("restart"); } catch { /* ignore */ }
                }

                try
                {
                    var config = LoadFabricConfig();
                    var tokenPresent = !string.IsNullOrWhiteSpace(config.ResolveToken());

                    Log("================================================");
                    Log("LUMINA Execution Fabric starting (NT AddOn)...");
                    Log("AccountName      = " + config.AccountName);
                    Log("Bind             = " + config.BindHost + ":" + config.BindPort);
                    Log("GatewayMode      = " + config.GatewayMode);
                    Log("HeartbeatTimeout = " + config.HeartbeatTimeoutMs + " ms");
                    Log("AuthToken set    = " + (tokenPresent ? "YES" : "NO"));
                    Log("HistoricalData   = nt BarsRequest");
                    Log("================================================");

                    if (!tokenPresent)
                    {
                        Log("FATAL: LUMINA_FABRIC_TOKEN not set (User env) and no fabric.json AuthToken.");
                        FabricRuntimeStatus.Instance.SetHostError(
                            "no_token",
                            "Set LUMINA_FABRIC_TOKEN User env and restart NT8");
                        WriteStatusFromRuntime();
                        return false;
                    }

                    // Product path: bind real NT Account (Sim101). Memory only when GatewayMode=memory|simhost|mock.
                    // Legacy GatewayMode=sim is upgraded here to NT Account (mission: live exchange + Sim account).
                    IOrderGateway gateway;
                    var mode = (config.GatewayMode ?? "").Trim();
                    var forceMemory =
                        string.Equals(mode, "memory", StringComparison.OrdinalIgnoreCase)
                        || string.Equals(mode, "simhost", StringComparison.OrdinalIgnoreCase)
                        || string.Equals(mode, "mock", StringComparison.OrdinalIgnoreCase);

                    if (forceMemory)
                    {
                        Log("GatewayMode=" + mode + " → in-memory SimOrderGateway (no NT Account)");
                        gateway = new SimOrderGateway(config.AccountName);
                    }
                    else
                    {
                        if (string.Equals(mode, "sim", StringComparison.OrdinalIgnoreCase)
                            || string.IsNullOrEmpty(mode))
                        {
                            Log("GatewayMode=" + (string.IsNullOrEmpty(mode) ? "(default)" : mode)
                                + " upgraded to NT Account bind (use GatewayMode=memory for in-process fills)");
                        }

                        var ntGw = new NtAccountOrderGateway(config.AccountName, Log);
                        if (!ntGw.TryBindFromNtAccounts())
                        {
                            Log("FATAL: could not bind NT Account '" + config.AccountName
                                + "'. Open Control Center, ensure Sim101 (or configured) is connected.");
                            FabricRuntimeStatus.Instance.SetHostError(
                                "account_not_bound",
                                "Bind Sim101 in NinjaTrader Control Center, then Repair / restart AddOn");
                            WriteStatusFromRuntime();
                            try { ntGw.Dispose(); } catch { /* ignore */ }
                            return false;
                        }

                        gateway = ntGw;
                    }

                    IHistoricalDataProvider historical = new NtHistoricalDataProvider(Log);
                    ILiveMarketDataProvider live = new NtLiveMarketDataProvider(Log);
                    _host = new FabricGrpcHost(config, gateway, Log, historical, live);
                    _host.Start();
                    _started = true;
                    Log("Host started successfully gateway=" + gateway.GatewayKind
                        + " account=" + gateway.AccountName
                        + " historical=nt live=nt"
                        + " audit=" + (_host.AuditPath ?? "(default)"));
                    WriteStatusFromRuntime();
                    return true;
                }
                catch (Exception ex)
                {
                    Log("FATAL: " + ex);
                    var msg = ex.Message ?? "";
                    if (msg.IndexOf("address already in use", StringComparison.OrdinalIgnoreCase) >= 0
                        || msg.IndexOf("Only one usage of each socket", StringComparison.OrdinalIgnoreCase) >= 0
                        || msg.IndexOf("failed to bind", StringComparison.OrdinalIgnoreCase) >= 0
                        || msg.IndexOf("EADDRINUSE", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        Log("PORT CONFLICT: another process holds 50051 (usually Lumina.Execution.Fabric.SimHost).");
                        Log("Stop SimHost (Lumina diagnostic auto-starts it) then restart this AddOn / NT8.");
                        FabricRuntimeStatus.Instance.SetHostError("port_in_use", msg);
                    }
                    else
                    {
                        FabricRuntimeStatus.Instance.SetHostError("start_failed", msg);
                    }

                    try { _host?.Dispose(); } catch { /* ignore */ }
                    _host = null;
                    _started = false;
                    WriteStatusFromRuntime();
                    return false;
                }
            }
        }

        public static void Stop()
        {
            lock (Gate)
            {
                if (!_started && _host == null)
                    return;
                try
                {
                    Log("Stopping host...");
                    var host = _host;
                    // Run stop off the calling path with a hard timeout so NT UI never deadlocks
                    // on gRPC ShutdownAsync (root of "Cannot reach 127.0.0.1:50051" after stop).
                    var stopDone = System.Threading.Tasks.Task.Run(() =>
                    {
                        try { host?.Stop(); } catch { /* logged inside */ }
                        try { host?.Dispose(); } catch { /* ignore */ }
                    });
                    if (!stopDone.Wait(TimeSpan.FromSeconds(5)))
                    {
                        Log("Stop timed out after 5s — marking stopped for SSOT");
                        try { FabricRuntimeStatus.Instance.SetHostStopped("stop_timeout"); } catch { /* ignore */ }
                    }
                    _host = null;
                    _started = false;
                    Log("Host stopped cleanly.");
                    WriteStatusFromRuntime();
                }
                catch (Exception ex)
                {
                    Log("Error while stopping: " + ex.Message);
                    try { FabricRuntimeStatus.Instance.SetHostError("stop_failed", ex.Message); } catch { /* ignore */ }
                    _host = null;
                    _started = false;
                    WriteStatusFromRuntime();
                }
            }
        }

        private static FabricConfig LoadFabricConfig()
        {
            try
            {
                var path = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "LUMINA",
                    "fabric.json");
                if (File.Exists(path))
                {
                    Log("Config file found: " + path);
                    return FabricConfig.LoadFromFile(path);
                }
                Log("No fabric.json found — using defaults (GatewayMode=nt).");
            }
            catch (Exception ex)
            {
                Log("Could not load config: " + ex.Message + " — using defaults.");
            }
            return new FabricConfig();
        }

        private static void Log(string message)
        {
            var line = "[FabricHost] " + message;
            try { _print?.Invoke(line); } catch { /* ignore */ }
            try
            {
                var dir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "LUMINA");
                Directory.CreateDirectory(dir);
                var path = Path.Combine(dir, "fabric-nt-host.log");
                File.AppendAllText(path, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff") + " " + line + Environment.NewLine, Encoding.UTF8);
            }
            catch { /* never throw from log */ }
        }

        private static void WriteStatusFromRuntime()
        {
            try
            {
                FabricRuntimeStatus.Instance.Persist();
            }
            catch { /* ignore */ }
        }
    }
}
