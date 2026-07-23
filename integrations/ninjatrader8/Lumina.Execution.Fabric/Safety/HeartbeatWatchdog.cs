using System;
using System.Threading;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Safety
{
    /// <summary>
    /// Brain heartbeat watchdog. On timeout: cancel non-protected → SAFE_MODE → optional flatten after grace.
    /// </summary>
    public sealed class HeartbeatWatchdog : IDisposable
    {
        private readonly FabricConfig _config;
        private readonly SafeModeStateMachine _safeMode;
        private readonly Action<string> _onTimeoutCancel;
        private readonly Action<string> _onFlatten;
        private readonly Action<SafetyAlert> _onAlert;
        private readonly Timer _timer;
        private long _lastHeartbeatUnixMs;
        private int _timeoutLatched;
        private int _flattenScheduled;

        public HeartbeatWatchdog(
            FabricConfig config,
            SafeModeStateMachine safeMode,
            Action<string> onTimeoutCancel,
            Action<string> onFlatten,
            Action<SafetyAlert> onAlert)
        {
            _config = config ?? throw new ArgumentNullException(nameof(config));
            _safeMode = safeMode ?? throw new ArgumentNullException(nameof(safeMode));
            _onTimeoutCancel = onTimeoutCancel ?? throw new ArgumentNullException(nameof(onTimeoutCancel));
            _onFlatten = onFlatten ?? throw new ArgumentNullException(nameof(onFlatten));
            _onAlert = onAlert ?? throw new ArgumentNullException(nameof(onAlert));
            _lastHeartbeatUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            _timer = new Timer(Tick, null, 250, 250);
        }

        public void NoteHeartbeat()
        {
            Interlocked.Exchange(ref _lastHeartbeatUnixMs, DateTimeOffset.UtcNow.ToUnixTimeMilliseconds());
            Interlocked.Exchange(ref _timeoutLatched, 0);
            Interlocked.Exchange(ref _flattenScheduled, 0);
        }

        public void NoteAuthenticatedSession()
        {
            NoteHeartbeat();
        }

        private void Tick(object? state)
        {
            var last = Interlocked.Read(ref _lastHeartbeatUnixMs);
            var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            var elapsed = now - last;
            var timeoutMs = Math.Max(500, _config.HeartbeatTimeoutMs);

            if (elapsed < timeoutMs)
                return;

            if (Interlocked.Exchange(ref _timeoutLatched, 1) == 0)
            {
                _safeMode.EnterSafe("brain_heartbeat_timeout");
                _onTimeoutCancel("brain_heartbeat_timeout");
                _onAlert(new SafetyAlert
                {
                    AlertType = SafetyAlertType.HeartbeatTimeout,
                    Severity = SafetySeverity.Critical,
                    Message = $"Brain heartbeat timeout after {elapsed}ms (limit={timeoutMs}ms)",
                    RecommendedAction = "cancel_non_protected_enter_safe_mode",
                    TimestampUnixMs = now,
                    CorrelationId = Guid.NewGuid().ToString("D"),
                });
            }

            if (!_config.FlattenOnTimeout)
                return;

            var grace = Math.Max(0, _config.FlattenGraceMs);
            if (elapsed < timeoutMs + grace)
                return;

            if (Interlocked.Exchange(ref _flattenScheduled, 1) == 0)
            {
                _onFlatten("brain_heartbeat_timeout_flatten_grace");
                _onAlert(new SafetyAlert
                {
                    AlertType = SafetyAlertType.FlattenIssued,
                    Severity = SafetySeverity.Critical,
                    Message = $"Flatten issued after heartbeat timeout + grace ({timeoutMs + grace}ms)",
                    RecommendedAction = "flatten_positions",
                    TimestampUnixMs = now,
                    CorrelationId = Guid.NewGuid().ToString("D"),
                });
            }
        }

        public void Dispose()
        {
            _timer.Dispose();
        }
    }
}
