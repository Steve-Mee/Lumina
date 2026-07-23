using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using Grpc.Core;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Grpc
{
    /// <summary>
    /// Tracks authenticated Brain stream writers for alert fan-out.
    /// </summary>
    public sealed class SessionHub
    {
        private readonly ConcurrentDictionary<string, IServerStreamWriter<FabricMessage>> _writers =
            new ConcurrentDictionary<string, IServerStreamWriter<FabricMessage>>(StringComparer.Ordinal);
        private readonly object _writeGate = new object();

        public void Register(string sessionId, IServerStreamWriter<FabricMessage> writer)
        {
            if (string.IsNullOrEmpty(sessionId) || writer == null)
                return;
            _writers[sessionId] = writer;
        }

        public void Unregister(string sessionId)
        {
            if (string.IsNullOrEmpty(sessionId))
                return;
            _writers.TryRemove(sessionId, out _);
        }

        public void Broadcast(FabricMessage message)
        {
            if (message == null)
                return;

            foreach (var kv in _writers)
            {
                try
                {
                    lock (_writeGate)
                    {
                        // Fire-and-forget sync write; Grpc.Core stream writes are not fully concurrent-safe.
                        kv.Value.WriteAsync(message).GetAwaiter().GetResult();
                    }
                }
                catch
                {
                    // drop dead sessions on next unregister
                }
            }
        }

        public int SessionCount => _writers.Count;

        public IEnumerable<string> SessionIds => _writers.Keys;
    }
}
