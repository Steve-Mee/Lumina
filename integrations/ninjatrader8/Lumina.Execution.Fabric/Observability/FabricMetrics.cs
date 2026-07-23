using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Threading;

namespace Lumina.Execution.Fabric.Observability
{
    /// <summary>
    /// In-process Fabric metrics (Prometheus-style names; JSON export for operators).
    /// </summary>
    public sealed class FabricMetrics
    {
        private long _placeTotal;
        private long _placeRejected;
        private long _placeFilled;
        private long _cancelTotal;
        private long _modifyTotal;
        private long _flattenTotal;
        private long _safeModeEntries;
        private long _authOk;
        private long _authFail;
        private long _disconnectPolicies;
        private long _idempotentReplays;
        private readonly ConcurrentQueue<double> _placeLatencyMs = new ConcurrentQueue<double>();
        private const int LatencyWindow = 500;

        public void IncPlace() => Interlocked.Increment(ref _placeTotal);
        public void IncPlaceRejected() => Interlocked.Increment(ref _placeRejected);
        public void IncPlaceFilled() => Interlocked.Increment(ref _placeFilled);
        public void IncCancel() => Interlocked.Increment(ref _cancelTotal);
        public void IncModify() => Interlocked.Increment(ref _modifyTotal);
        public void IncFlatten() => Interlocked.Increment(ref _flattenTotal);
        public void IncSafeMode() => Interlocked.Increment(ref _safeModeEntries);
        public void IncAuthOk() => Interlocked.Increment(ref _authOk);
        public void IncAuthFail() => Interlocked.Increment(ref _authFail);
        public void IncDisconnectPolicy() => Interlocked.Increment(ref _disconnectPolicies);
        public void IncIdempotentReplay() => Interlocked.Increment(ref _idempotentReplays);

        public void ObservePlaceLatencyMs(double ms)
        {
            if (ms < 0)
                return;
            _placeLatencyMs.Enqueue(ms);
            while (_placeLatencyMs.Count > LatencyWindow && _placeLatencyMs.TryDequeue(out _))
            {
            }
        }

        public IReadOnlyDictionary<string, object> Snapshot()
        {
            var lat = _placeLatencyMs.ToArray();
            Array.Sort(lat);
            double p50 = 0, p95 = 0, p99 = 0, mean = 0;
            if (lat.Length > 0)
            {
                mean = lat.Average();
                p50 = Percentile(lat, 0.50);
                p95 = Percentile(lat, 0.95);
                p99 = Percentile(lat, 0.99);
            }

            return new Dictionary<string, object>
            {
                ["fabric_place_orders_total"] = Interlocked.Read(ref _placeTotal),
                ["fabric_place_rejected_total"] = Interlocked.Read(ref _placeRejected),
                ["fabric_place_filled_total"] = Interlocked.Read(ref _placeFilled),
                ["fabric_cancel_total"] = Interlocked.Read(ref _cancelTotal),
                ["fabric_modify_total"] = Interlocked.Read(ref _modifyTotal),
                ["fabric_flatten_total"] = Interlocked.Read(ref _flattenTotal),
                ["fabric_safe_mode_entries_total"] = Interlocked.Read(ref _safeModeEntries),
                ["fabric_auth_ok_total"] = Interlocked.Read(ref _authOk),
                ["fabric_auth_fail_total"] = Interlocked.Read(ref _authFail),
                ["fabric_disconnect_policy_total"] = Interlocked.Read(ref _disconnectPolicies),
                ["fabric_idempotent_replays_total"] = Interlocked.Read(ref _idempotentReplays),
                ["fabric_place_latency_ms_mean"] = mean,
                ["fabric_place_latency_ms_p50"] = p50,
                ["fabric_place_latency_ms_p95"] = p95,
                ["fabric_place_latency_ms_p99"] = p99,
                ["fabric_place_latency_samples"] = lat.Length,
            };
        }

        public string PrometheusText()
        {
            var snap = Snapshot();
            var lines = new List<string>
            {
                "# HELP fabric_place_orders_total Place order attempts accepted for gateway",
                "# TYPE fabric_place_orders_total counter",
                $"fabric_place_orders_total {snap["fabric_place_orders_total"]}",
                "# TYPE fabric_place_rejected_total counter",
                $"fabric_place_rejected_total {snap["fabric_place_rejected_total"]}",
                "# TYPE fabric_safe_mode_entries_total counter",
                $"fabric_safe_mode_entries_total {snap["fabric_safe_mode_entries_total"]}",
                "# TYPE fabric_place_latency_ms summary",
                $"fabric_place_latency_ms{{quantile=\"0.5\"}} {snap["fabric_place_latency_ms_p50"]}",
                $"fabric_place_latency_ms{{quantile=\"0.95\"}} {snap["fabric_place_latency_ms_p95"]}",
                $"fabric_place_latency_ms{{quantile=\"0.99\"}} {snap["fabric_place_latency_ms_p99"]}",
            };
            return string.Join("\n", lines) + "\n";
        }

        private static double Percentile(double[] sorted, double p)
        {
            if (sorted.Length == 0)
                return 0;
            var idx = (int)Math.Ceiling(p * sorted.Length) - 1;
            if (idx < 0)
                idx = 0;
            if (idx >= sorted.Length)
                idx = sorted.Length - 1;
            return sorted[idx];
        }
    }
}
