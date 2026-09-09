using System.Collections.Generic;
using Lumina.Execution.Fabric.Safety;
using Lumina.Execution.V1;
using Xunit;

namespace Lumina.Execution.Fabric.Tests
{
    public sealed class HeartbeatWatchdogTests
    {
        [Fact]
        public void Unarmed_timeout_issues_no_cancel_and_no_flatten()
        {
            var harness = Create(flattenOnTimeout: true, graceMs: 0);
            long now = 1_000_000;
            harness.Watchdog.UnixMsNow = () => now;
            harness.Watchdog.SyncClockForTests();
            harness.Watchdog.NoteHeartbeat(); // ignored: no AuthHello yet

            harness.Watchdog.EvaluateAt(now + 20_000);

            Assert.False(harness.Watchdog.IsArmed);
            Assert.True(harness.Watchdog.UnarmedIdleLatched);
            Assert.Empty(harness.Cancels);
            Assert.Empty(harness.Flattens);
            Assert.Equal(SafeModeState.Normal, harness.SafeMode.State);
            Assert.Contains(harness.Alerts, a => a.RecommendedAction == HeartbeatWatchdog.IdleUnarmedAction);
        }

        [Fact]
        public void AuthHello_without_heartbeat_does_not_arm_or_flatten()
        {
            var harness = Create(flattenOnTimeout: true, graceMs: 0);
            long now = 6_000_000;
            harness.Watchdog.UnixMsNow = () => now;
            harness.Watchdog.NoteAuthenticatedSession();
            Assert.True(harness.Watchdog.HasSeenAuth);
            Assert.False(harness.Watchdog.IsArmed);

            harness.Watchdog.EvaluateAt(now + 20_000);

            Assert.False(harness.Watchdog.IsArmed);
            Assert.Empty(harness.Cancels);
            Assert.Empty(harness.Flattens);
            Assert.Equal(SafeModeState.Normal, harness.SafeMode.State);
        }

        [Fact]
        public void Unarmed_idle_alert_latches_once()
        {
            var harness = Create(flattenOnTimeout: true, graceMs: 0);
            long now = 2_000_000;
            harness.Watchdog.UnixMsNow = () => now;
            harness.Watchdog.SyncClockForTests();

            harness.Watchdog.EvaluateAt(now + 5_000);
            harness.Watchdog.EvaluateAt(now + 40_000);

            Assert.Single(harness.Alerts);
            Assert.Empty(harness.Flattens);
            Assert.Empty(harness.Cancels);
        }

        [Fact]
        public void Armed_without_heartbeat_cancels_then_flattens_once()
        {
            var harness = Create(flattenOnTimeout: true, graceMs: 1_000);
            long now = 3_000_000;
            harness.Watchdog.UnixMsNow = () => now;
            harness.Watchdog.NoteAuthenticatedSession();
            harness.Watchdog.NoteHeartbeat();
            Assert.True(harness.Watchdog.IsArmed);

            harness.Watchdog.EvaluateAt(now + 500);
            Assert.Single(harness.Cancels);
            Assert.Empty(harness.Flattens);
            Assert.Equal(SafeModeState.Safe, harness.SafeMode.State);

            harness.Watchdog.EvaluateAt(now + 1_500);
            Assert.Single(harness.Cancels);
            Assert.Single(harness.Flattens);

            harness.Watchdog.EvaluateAt(now + 9_000);
            Assert.Single(harness.Flattens);
        }

        [Fact]
        public void Armed_with_heartbeats_does_not_flatten()
        {
            var harness = Create(flattenOnTimeout: true, graceMs: 0);
            long now = 4_000_000;
            harness.Watchdog.UnixMsNow = () => now;
            harness.Watchdog.NoteAuthenticatedSession();
            harness.Watchdog.NoteHeartbeat();

            now += 200;
            harness.Watchdog.UnixMsNow = () => now;
            harness.Watchdog.NoteHeartbeat();
            harness.Watchdog.EvaluateAt(now + 200);

            Assert.Empty(harness.Cancels);
            Assert.Empty(harness.Flattens);
            Assert.Equal(SafeModeState.Normal, harness.SafeMode.State);
        }

        [Fact]
        public void FlattenOnTimeout_false_cancels_but_does_not_flatten()
        {
            var harness = Create(flattenOnTimeout: false, graceMs: 0);
            long now = 5_000_000;
            harness.Watchdog.UnixMsNow = () => now;
            harness.Watchdog.NoteAuthenticatedSession();
            harness.Watchdog.NoteHeartbeat();

            harness.Watchdog.EvaluateAt(now + 5_000);

            Assert.Single(harness.Cancels);
            Assert.Empty(harness.Flattens);
            Assert.Equal(SafeModeState.Safe, harness.SafeMode.State);
        }

        private static Harness Create(bool flattenOnTimeout, int graceMs)
        {
            var config = new FabricConfig
            {
                HeartbeatTimeoutMs = 500,
                FlattenGraceMs = graceMs,
                FlattenOnTimeout = flattenOnTimeout,
            };
            var safe = new SafeModeStateMachine();
            var cancels = new List<string>();
            var flattens = new List<string>();
            var alerts = new List<SafetyAlert>();
            var watchdog = new HeartbeatWatchdog(
                config,
                safe,
                onTimeoutCancel: cancels.Add,
                onFlatten: flattens.Add,
                onAlert: alerts.Add,
                enableTimer: false);
            return new Harness(watchdog, safe, cancels, flattens, alerts);
        }

        private sealed class Harness
        {
            public Harness(
                HeartbeatWatchdog watchdog,
                SafeModeStateMachine safeMode,
                List<string> cancels,
                List<string> flattens,
                List<SafetyAlert> alerts)
            {
                Watchdog = watchdog;
                SafeMode = safeMode;
                Cancels = cancels;
                Flattens = flattens;
                Alerts = alerts;
            }

            public HeartbeatWatchdog Watchdog { get; }
            public SafeModeStateMachine SafeMode { get; }
            public List<string> Cancels { get; }
            public List<string> Flattens { get; }
            public List<SafetyAlert> Alerts { get; }
        }
    }
}
