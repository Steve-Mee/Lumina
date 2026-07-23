using System;
using Grpc.Core;
using Lumina.Execution.Fabric.Audit;
using Lumina.Execution.Fabric.Execution;
using Lumina.Execution.Fabric.Grpc;
using Lumina.Execution.Fabric.Safety;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric
{
    /// <summary>
    /// Hosts the Execution Fabric gRPC server on localhost (ADR-0035).
    /// Safety watchdog + audit log run independently of the Brain process.
    /// </summary>
    public sealed class FabricGrpcHost : IDisposable
    {
        private readonly FabricConfig _config;
        private readonly IOrderGateway _gateway;
        private readonly Action<string>? _log;
        private Server? _server;
        private SafeModeStateMachine? _safeMode;
        private HeartbeatWatchdog? _watchdog;
        private FabricAuditLog? _audit;
        private ExecutionFabricService? _service;
        private bool _started;

        public FabricGrpcHost(FabricConfig config, IOrderGateway gateway, Action<string>? log = null)
        {
            _config = config ?? throw new ArgumentNullException(nameof(config));
            _gateway = gateway ?? throw new ArgumentNullException(nameof(gateway));
            _log = log;
        }

        public bool IsRunning => _started;
        public SafeModeStateMachine? SafeMode => _safeMode;
        public IOrderGateway Gateway => _gateway;
        public string? AuditPath => _audit?.FilePath;

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
            _audit = new FabricAuditLog(_config.AuditLogPath);
            _audit.Record("host_start", "fabric_grpc_host_starting", new
            {
                host = _config.BindHost,
                port = _config.BindPort,
                account = _gateway.AccountName,
            });

            ExecutionFabricService? serviceRef = null;
            _watchdog = new HeartbeatWatchdog(
                _config,
                _safeMode,
                onTimeoutCancel: reason =>
                {
                    var events = _gateway.CancelNonProtected(reason);
                    serviceRef?.PublishOrderEvents(events);
                    _audit?.Record("watchdog_cancel", reason, new { cancelled = events.Count });
                    Log($"watchdog cancel non-protected: {reason} count={events.Count}");
                },
                onFlatten: reason =>
                {
                    var events = _gateway.Flatten(new FlattenCommand
                    {
                        Emergency = true,
                        CorrelationId = Guid.NewGuid().ToString("D"),
                    });
                    serviceRef?.PublishOrderEvents(events);
                    _audit?.Record("watchdog_flatten", reason, new { events = events.Count });
                    Log($"watchdog flatten: {reason} events={events.Count}");
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
                _audit,
                _log);
            serviceRef = _service;

            _server = new Server
            {
                Services = { ExecutionFabric.BindService(_service) },
                Ports = { new ServerPort(_config.BindHost, _config.BindPort, ServerCredentials.Insecure) },
            };
            _server.Start();
            _started = true;
            Log($"gRPC listening on {_config.BindHost}:{_config.BindPort} account={_gateway.AccountName} audit={_audit.FilePath}");
        }

        public void Stop()
        {
            if (!_started)
                return;
            try
            {
                _audit?.Record("host_stop", "fabric_grpc_host_stopping", null);
                _watchdog?.Dispose();
                _server?.ShutdownAsync().GetAwaiter().GetResult();
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
                _audit?.Dispose();
                _audit = null;
                _started = false;
                Log("gRPC host stopped");
            }
        }

        public void Dispose() => Stop();

        private void Log(string message) => _log?.Invoke("[FabricHost] " + message);
    }
}
