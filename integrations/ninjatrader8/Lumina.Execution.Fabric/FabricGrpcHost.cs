using System;
using System.Collections.Generic;
using Grpc.Core;
using Lumina.Execution.Fabric.Audit;
using Lumina.Execution.Fabric.Execution;
using Lumina.Execution.Fabric.Grpc;
using Lumina.Execution.Fabric.MarketData;
using Lumina.Execution.Fabric.Observability;
using Lumina.Execution.Fabric.Safety;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric
{
    /// <summary>
    /// Hosts the Execution Fabric gRPC server on localhost (ADR-0035).
    /// Safety watchdog + audit + metrics run independently of the Brain process.
    /// </summary>
    public sealed class FabricGrpcHost : IDisposable
    {
        private readonly FabricConfig _config;
        private readonly IOrderGateway _gateway;
        private readonly IHistoricalDataProvider _historical;
        private readonly ILiveMarketDataProvider _liveMarket;
        private readonly Action<string>? _log;
        private Server? _server;
        private SafeModeStateMachine? _safeMode;
        private HeartbeatWatchdog? _watchdog;
        private FabricAuditLog? _audit;
        private FabricMetrics? _metrics;
        private ExecutionFabricService? _service;
        private bool _started;

        public FabricGrpcHost(
            FabricConfig config,
            IOrderGateway gateway,
            Action<string>? log = null,
            IHistoricalDataProvider? historical = null,
            ILiveMarketDataProvider? liveMarket = null)
        {
            _config = config ?? throw new ArgumentNullException(nameof(config));
            _gateway = gateway ?? throw new ArgumentNullException(nameof(gateway));
            _historical = historical ?? new NullHistoricalDataProvider();
            _liveMarket = liveMarket ?? new NullLiveMarketDataProvider();
            _log = log;
        }

        public bool IsRunning => _started;
        public SafeModeStateMachine? SafeMode => _safeMode;
        public IOrderGateway Gateway => _gateway;
        public string? AuditPath => _audit?.FilePath;
        public FabricMetrics? Metrics => _metrics;

        /// <summary>
        /// Create gateway for hosts without NinjaTrader.Core (SimHost / tests).
        /// Memory modes → SimOrderGateway. NT modes → fail-closed <see cref="NtOrderGateway"/>
        /// (real Account bind is <c>NtAccountOrderGateway</c> inside the NT AddOn).
        /// </summary>
        public static IOrderGateway CreateGateway(FabricConfig config)
        {
            if (config == null)
                throw new ArgumentNullException(nameof(config));
            if (config.UseNtGateway)
                return new NtOrderGateway(config.AccountName);
            return new SimOrderGateway(config.AccountName);
        }

        public void Start()
        {
            if (_started)
                return;

            _config.EnforceLocalhostOnly();
            var token = _config.ResolveToken();
            if (string.IsNullOrEmpty(token))
                throw new InvalidOperationException(
                    "Fabric auth token not configured. Set LUMINA_FABRIC_TOKEN or fabric.json AuthToken.");

            _safeMode = new SafeModeStateMachine();
            var sessions = new SessionHub();
            var idempotency = new IdempotencyStore();
            var rateLimiter = new OrderRateLimiter(_config.MaxOrdersPerMinute);
            var preTrade = new PreTradeRiskEngine(_config);
            _metrics = new FabricMetrics();
            _audit = new FabricAuditLog(_config.AuditLogPath);
            _audit.Record("host_start", "fabric_grpc_host_starting", new
            {
                host = _config.BindHost,
                port = _config.BindPort,
                account = _gateway.AccountName,
                gateway = _gateway.GatewayKind,
            });

            ExecutionFabricService? serviceRef = null;
            _watchdog = new HeartbeatWatchdog(
                _config,
                _safeMode,
                onTimeoutCancel: reason =>
                {
                    var events = _gateway.CancelNonProtected(reason);
                    serviceRef?.PublishOrderEvents(events);
                    _metrics?.IncSafeMode();
                    _audit?.Record("watchdog_cancel", reason, new { cancelled = events.Count });
                    Log($"watchdog cancel non-protected: {reason} count={events.Count}");
                },
                onFlatten: reason =>
                {
                    // Probe/diagnostic thrash: never emergency-flatten an empty book.
                    // Capital-safe: still flatten when any position or working order exists.
                    int posCount = 0;
                    int workCount = 0;
                    try { posCount = _gateway.GetPositions()?.Count ?? 0; } catch { /* ignore */ }
                    try { workCount = _gateway.GetWorkingOrders()?.Count ?? 0; } catch { /* ignore */ }
                    if (posCount <= 0 && workCount <= 0)
                    {
                        _audit?.Record("watchdog_flatten_skipped", reason, new { positions = 0, working = 0 });
                        Log($"watchdog flatten skipped (empty book): {reason}");
                        return;
                    }
                    var events = _gateway.Flatten(new FlattenCommand
                    {
                        Emergency = true,
                        CorrelationId = Guid.NewGuid().ToString("D"),
                    });
                    serviceRef?.PublishOrderEvents(events);
                    _metrics?.IncFlatten();
                    _audit?.Record("watchdog_flatten", reason, new { events = events.Count, positions = posCount, working = workCount });
                    Log($"watchdog flatten: {reason} events={events.Count} positions={posCount} working={workCount}");
                },
                onAlert: alert =>
                {
                    serviceRef?.PublishAlert(alert);
                    Log($"safety alert: {alert.AlertType} {alert.Message}");
                });

            _service = new ExecutionFabricService(
                _config,
                _gateway,
                _safeMode,
                _watchdog,
                idempotency,
                sessions,
                rateLimiter,
                preTrade,
                _metrics,
                _audit,
                _log,
                _historical,
                _liveMarket);
            serviceRef = _service;

            // Live NT Account callbacks → TradingStream (fills/cancels/positions after place ack).
            if (_gateway is IOrderEventSource eventSource)
            {
                eventSource.OrderEventsProduced += events =>
                {
                    try
                    {
                        serviceRef?.PublishOrderEvents(events);
                    }
                    catch (Exception ex)
                    {
                        Log("OrderEventsProduced publish failed: " + ex.Message);
                    }
                };
                eventSource.PositionUpdatesProduced += positions =>
                {
                    try
                    {
                        serviceRef?.PublishPositionUpdates(positions);
                    }
                    catch (Exception ex)
                    {
                        Log("PositionUpdatesProduced publish failed: " + ex.Message);
                    }
                };
            }

            _server = new Server
            {
                Services = { ExecutionFabric.BindService(_service) },
                Ports = { new ServerPort(_config.BindHost, _config.BindPort, ServerCredentials.Insecure) },
            };
            _server.Start();
            _started = true;

            _safeMode.StateChanged += OnSafeModeChanged;
            FabricRuntimeStatus.Instance.NoteSafeMode(FormatSafeMode(_safeMode.State));
            var bound = true;
            try
            {
                // NtAccountOrderGateway exposes IsBound; reflection-friendly for status.
                var prop = _gateway.GetType().GetProperty("IsBound");
                if (prop != null && prop.PropertyType == typeof(bool))
                    bound = (bool)(prop.GetValue(_gateway) ?? true);
            }
            catch { bound = true; }

            FabricRuntimeStatus.Instance.SetHostRunning(
                hostKind: DetectHostKind(),
                bindHost: _config.BindHost,
                port: _config.BindPort,
                gateway: _gateway.GatewayKind,
                account: _gateway.AccountName,
                historicalProvider: _historical.ProviderKind,
                code: bound ? "ok" : "account_unbound",
                detail: bound ? null : "NT Account not bound");
            // Match-proof fingerprint (never the raw token) for Brain dual-truth detection.
            try
            {
                FabricRuntimeStatus.Instance.SetTokenFingerprint(_config.ResolveToken());
            }
            catch { /* never block start on fingerprint */ }
            FabricRuntimeStatus.Instance.NoteBound(bound);

            Log($"gRPC listening on {_config.BindHost}:{_config.BindPort} account={_gateway.AccountName} gateway={_gateway.GatewayKind} bound={bound} historical={_historical.ProviderKind} audit={_audit.FilePath}");
        }

        private void OnSafeModeChanged(SafeModeState state, string reason)
        {
            FabricRuntimeStatus.Instance.NoteSafeMode(FormatSafeMode(state));
            Log($"safe_mode → {state} reason={reason}");
        }

        private static string FormatSafeMode(SafeModeState state)
        {
            switch (state)
            {
                case SafeModeState.Safe: return "SAFE";
                case SafeModeState.FullSafe: return "FULL_SAFE";
                case SafeModeState.Normal: return "NORMAL";
                default: return state.ToString().ToUpperInvariant();
            }
        }

        private static string DetectHostKind()
        {
            try
            {
                var proc = System.Diagnostics.Process.GetCurrentProcess().ProcessName ?? "";
                if (proc.IndexOf("NinjaTrader", StringComparison.OrdinalIgnoreCase) >= 0)
                    return "nt_addon";
                if (proc.IndexOf("SimHost", StringComparison.OrdinalIgnoreCase) >= 0)
                    return "simhost";
            }
            catch { /* ignore */ }
            return "unknown";
        }

        public IReadOnlyDictionary<string, object> GetMetricsSnapshot()
        {
            return _metrics?.Snapshot() ?? new Dictionary<string, object>();
        }

        public void Stop()
        {
            if (!_started)
                return;
            try
            {
                if (_safeMode != null)
                    _safeMode.StateChanged -= OnSafeModeChanged;
                if (_metrics != null)
                    _audit?.Record("metrics_snapshot", "host_stop", _metrics.Snapshot());
                _audit?.Record("host_stop", "fabric_grpc_host_stopping", null);
                try { _watchdog?.Dispose(); } catch { /* ignore */ }
                // NEVER block forever on ShutdownAsync().GetResult() — that deadlocks the
                // NT UI/thread when clients still hold TradingStream, leaving :50051 half-dead
                // (no LISTEN, ESTABLISHED zombies) and fabric-nt-host.json stuck on "running".
                var server = _server;
                if (server != null)
                {
                    try
                    {
                        var shutdown = server.ShutdownAsync();
                        if (!shutdown.Wait(TimeSpan.FromSeconds(2.5)))
                        {
                            Log("gRPC ShutdownAsync timeout — KillAsync");
                            try
                            {
                                var kill = server.KillAsync();
                                if (!kill.Wait(TimeSpan.FromSeconds(1.5)))
                                    Log("gRPC KillAsync timeout — abandoning server");
                            }
                            catch (Exception kex)
                            {
                                Log("KillAsync error: " + kex.Message);
                            }
                        }
                    }
                    catch (Exception sex)
                    {
                        Log("Shutdown error: " + sex.Message);
                        try { server.KillAsync().Wait(TimeSpan.FromSeconds(1)); } catch { /* ignore */ }
                    }
                }
            }
            catch (Exception ex)
            {
                Log("Stop error: " + ex.Message);
            }
            finally
            {
                _watchdog = null;
                _server = null;
                _service = null;
                _metrics = null;
                try { _audit?.Dispose(); } catch { /* ignore */ }
                _audit = null;
                _started = false;
                // Always persist stopped — SSOT must not claim running when port is dead.
                try { FabricRuntimeStatus.Instance.SetHostStopped("clean"); } catch { /* ignore */ }
                Log("gRPC host stopped");
            }
        }

        public void Dispose() => Stop();

        private void Log(string message) => _log?.Invoke("[FabricHost] " + message);
    }
}
