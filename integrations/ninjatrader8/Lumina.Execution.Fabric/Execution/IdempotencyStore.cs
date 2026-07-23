using System;
using System.Collections.Concurrent;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Execution
{
    /// <summary>
    /// Guarantees at-most-once place execution per client_order_id (blueprint §5.4).
    /// </summary>
    public sealed class IdempotencyStore
    {
        private readonly ConcurrentDictionary<string, OrderEvent> _byClientId =
            new ConcurrentDictionary<string, OrderEvent>(StringComparer.Ordinal);

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
        }

        public void Clear() => _byClientId.Clear();
    }
}
