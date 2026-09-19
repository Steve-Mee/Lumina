using System;
using System.Threading;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Safety
{
    /// <summary>
    /// Brain heartbeat watchdog. Stays disarmed until AuthHello AND at least one heartbeat.
    /// Auth-only probes (Repair / Test connection) must never enable cancel or flatten.
    /// When armed and timed out: cancel non-protected → SAFE_MODE → optional flatten after grace.
    /// </summary>
    public sealed class HeartbeatWatchdog : IDisposable
    {
        public const string IdleUnarmedAction = "idle_unarmed_no_orders";

        private readonly FabricConfig _config;
        private readonly SafeModeStateMachine _safeMode;
        private readonly Action<string> _onTimeoutCancel;
        private readonly Action<string> _onFlatten;
        private readonly Action<SafetyAlert> _onAlert;
        private readonly Timer _timer;
        private long _lastHeartbeatUnixMs;
        private int _timeoutLatched;
        private int _flattenScheduled;
        private int _seenAuth;
        private int _armed;
        private int _unarmedIdleLatched;

        public HeartbeatWatchdog(
            FabricConfig config,
            SafeModeStateMachine safeMode,
            Action<string> onTimeoutCancel,
            Action<string> onFlatten,
            Action<SafetyAlert> onAlert,
            bool enableTimer = true)
        {
            _config = config ?? throw new ArgumentNullException(nameof(config));
            _safeMode = safeMode ?? throw new ArgumentNullException(nameof(safeMode));
            _onTimeoutCancel = onTimeoutCancel ?? throw new ArgumentNullException(nameof(onTimeoutCancel));
            _onFlatten = onFlatten ?? throw new ArgumentNullException(nameof(onFlatten));
            _onAlert = onAlert ?? throw new ArgumentNullException(nameof(onAlert));
            UnixMsNow = () => DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            _lastHeartbeatUnixMs = UnixMsNow();
            if (enableTimer)
                _timer = new Timer(Tick, null, 250, 250);
            else
                _timer = new Timer(_ => { }, null, Timeout.Infinite, Timeout.Infinite);
        }

        /// <summary>True only after AuthHello plus at least one heartbeat on this host instance.</summary>
        public bool IsArmed => Volatile.Read(ref _armed) != 0;

        /// <summary>True after AuthHello (probe or live). Does not by itself allow flatten.</summary>
        public bool HasSeenAuth => Volatile.Read(ref _seenAuth) != 0;

        /// <summary>True after one idle-unarmed alert this arm-cycle (no orders issued).</summary>
        public bool UnarmedIdleLatched => Volatile.Read(ref _unarmedIdleLatched) != 0;

        /// <summary>Clock injection for tests. Production uses UTC unix ms.</summary>
        internal Func<long> UnixMsNow { get; set; }

        /// <summary>Snap last-heartbeat to the test clock without arming.</summary>
        internal void SyncClockForTests()
        {
            Interlocked.Exchange(ref _lastHeartbeatUnixMs, UnixMsNow());
        }

        public void NoteHeartbeat()
        {
            // Heartbeats before AuthHello are ignored (stream also rejects them).
            if (Volatile.Read(ref _seenAuth) == 0)
                return;
            Interlocked.Exchange(ref _armed, 1);
            ResetClockAndLatches();
        }

        public void NoteAuthenticatedSession()
        {
            Interlocked.Exchange(ref _seenAuth, 1);
            // Do NOT arm here — Repair/Test AuthHello must not enable flatten.
            ResetClockAndLatches();
        }

        private void ResetClockAndLatches()
        {
            Interlocked.Exchange(ref _lastHeartbeatUnixMs, UnixMsNow());
            Interlocked.Exchange(ref _timeoutLatched, 0);
            Interlocked.Exchange(ref _flattenScheduled, 0);
            Interlocked.Exchange(ref _unarmedIdleLatched, 0);
        }

        /// <summary>Evaluate timeout/flatten at an explicit timestamp (tests + timer).</summary>
        internal void EvaluateAt(long nowMs)
        {
            var last = Interlocked.Read(ref _lastHeartbeatUnixMs);
            var elapsed = nowMs - last;
            var timeoutMs = Math.Max(500, _config.HeartbeatTimeoutMs);

            if (elapsed < timeoutMs)
                return;

            if (Volatile.Read(ref _armed) == 0)
            {
                if (Interlocked.Exchange(ref _unarmedIdleLatched, 1) == 0)
                {
                    _onAlert(new SafetyAlert
                    {
                        AlertType = SafetyAlertType.Unspecified,
                        Severity = SafetySeverity.Info,
                        Message = $"Watchdog idle after {elapsed}ms — Brain never sent a live heartbeat; no cancel/flatten",
                        RecommendedAction = IdleUnarmedAction,
                        TimestampUnixMs = nowMs,
                        CorrelationId = Guid.NewGuid().ToString("D"),
                    });
                }
                return;
            }

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
                    TimestampUnixMs = nowMs,
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
                    TimestampUnixMs = nowMs,
                    CorrelationId = Guid.NewGuid().ToString("D"),
                });
            }
        }

        private void Tick(object? state)
        {
            try
            {
                EvaluateAt(UnixMsNow());
            }
            catch
            {
                // Timer callbacks must never throw; next tick retries.
            }
        }

        public void Dispose()
        {
            _timer.Dispose();
        }
    }
}
