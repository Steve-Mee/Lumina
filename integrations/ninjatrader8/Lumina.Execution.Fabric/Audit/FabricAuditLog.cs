using System;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Threading;

namespace Lumina.Execution.Fabric.Audit
{
    /// <summary>
    /// Append-only JSONL audit trail for orders, safety actions, reconnects (blueprint §6.5).
    /// File is never rewritten or truncated by this type.
    /// </summary>
    public sealed class FabricAuditLog : IDisposable
    {
        private readonly object _gate = new object();
        private readonly string _path;
        private StreamWriter? _writer;
        private long _sequence;

        public FabricAuditLog(string? path = null)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                var dir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "LUMINA");
                Directory.CreateDirectory(dir);
                path = Path.Combine(dir, "fabric-audit.jsonl");
            }
            else
            {
                var parent = Path.GetDirectoryName(path);
                if (!string.IsNullOrEmpty(parent))
                    Directory.CreateDirectory(parent);
            }

            _path = path!;
            _writer = new StreamWriter(new FileStream(_path, FileMode.Append, FileAccess.Write, FileShare.Read), Encoding.UTF8)
            {
                AutoFlush = true,
            };
        }

        public string FilePath => _path;

        public void Record(string eventType, string rationale, object? details = null)
        {
            var seq = Interlocked.Increment(ref _sequence);
            var row = new
            {
                seq,
                ts_unix_ms = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                event_type = eventType,
                rationale = rationale ?? "",
                details,
            };
            var line = JsonSerializer.Serialize(row);
            lock (_gate)
            {
                _writer?.WriteLine(line);
            }
        }

        public void Dispose()
        {
            lock (_gate)
            {
                _writer?.Dispose();
                _writer = null;
            }
        }
    }
}
