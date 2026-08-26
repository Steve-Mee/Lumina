using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Execution
{
    /// <summary>
    /// At-most-once place execution per client_order_id (blueprint §5.4).
    /// In-memory with optional JSONL persistence for process restarts within a session day.
    /// </summary>
    public sealed class IdempotencyStore
    {
        private readonly ConcurrentDictionary<string, OrderEvent> _byClientId =
            new ConcurrentDictionary<string, OrderEvent>(StringComparer.Ordinal);
        private readonly string? _persistPath;
        private readonly object _fileGate = new object();

        public IdempotencyStore(string? persistPath = null)
        {
            _persistPath = string.IsNullOrWhiteSpace(persistPath) ? DefaultPath() : persistPath;
            LoadFromDisk();
        }

        public static string DefaultPath()
        {
            return Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "LUMINA",
                "fabric-idempotency.jsonl");
        }

        public bool TryGet(string clientOrderId, out OrderEvent prior)
        {
            if (string.IsNullOrWhiteSpace(clientOrderId))
            {
                prior = null!;
                return false;
            }
            return _byClientId.TryGetValue(clientOrderId, out prior!);
        }

        public void Remember(string clientOrderId, OrderEvent evt)
        {
            if (string.IsNullOrWhiteSpace(clientOrderId) || evt == null)
                return;
            _byClientId[clientOrderId] = evt;
            AppendDisk(clientOrderId, evt);
        }

        public void Clear()
        {
            _byClientId.Clear();
            try
            {
                if (!string.IsNullOrEmpty(_persistPath) && File.Exists(_persistPath))
                    File.Delete(_persistPath);
            }
            catch
            {
                // best effort
            }
        }

        private void LoadFromDisk()
        {
            if (string.IsNullOrEmpty(_persistPath) || !File.Exists(_persistPath))
                return;
            try
            {
                foreach (var line in File.ReadLines(_persistPath))
                {
                    if (string.IsNullOrWhiteSpace(line))
                        continue;
                    using var doc = JsonDocument.Parse(line);
                    var root = doc.RootElement;
                    var id = root.TryGetProperty("client_order_id", out var idEl) ? idEl.GetString() : null;
                    if (string.IsNullOrEmpty(id))
                        continue;
                    var evt = new OrderEvent
                    {
                        ClientOrderId = id!,
                        NtOrderId = root.TryGetProperty("nt_order_id", out var n) ? n.GetString() ?? "" : "",
                        State = root.TryGetProperty("state", out var s) && Enum.TryParse<OrderState>(s.GetString(), true, out var st)
                            ? st
                            : OrderState.Unspecified,
                        RejectionReason = root.TryGetProperty("reason", out var r) ? r.GetString() ?? "" : "",
                        Instrument = root.TryGetProperty("instrument", out var i) ? i.GetString() ?? "" : "",
                        CorrelationId = root.TryGetProperty("correlation_id", out var c) ? c.GetString() ?? "" : "",
                        TimestampUnixMs = root.TryGetProperty("ts", out var t) ? t.GetInt64() : 0,
                    };
                    _byClientId[id!] = evt;
                }
            }
            catch
            {
                // Corrupt file must not block host start.
            }
        }

        private void AppendDisk(string clientOrderId, OrderEvent evt)
        {
            if (string.IsNullOrEmpty(_persistPath))
                return;
            try
            {
                lock (_fileGate)
                {
                    var dir = Path.GetDirectoryName(_persistPath);
                    if (!string.IsNullOrEmpty(dir))
                        Directory.CreateDirectory(dir);
                    var row = JsonSerializer.Serialize(new Dictionary<string, object?>
                    {
                        ["client_order_id"] = clientOrderId,
                        ["nt_order_id"] = evt.NtOrderId,
                        ["state"] = evt.State.ToString(),
                        ["reason"] = evt.RejectionReason,
                        ["instrument"] = evt.Instrument,
                        ["correlation_id"] = evt.CorrelationId,
                        ["ts"] = evt.TimestampUnixMs,
                    });
                    File.AppendAllText(_persistPath, row + Environment.NewLine);
                }
            }
            catch
            {
                // Persistence is best-effort; memory map remains authoritative in-process.
            }
        }
    }
}
