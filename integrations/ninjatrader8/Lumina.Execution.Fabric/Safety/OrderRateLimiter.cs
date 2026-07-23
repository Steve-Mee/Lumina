using System;
using System.Collections.Generic;

namespace Lumina.Execution.Fabric.Safety
{
    /// <summary>Sliding 60s window order rate limit (Fabric pre-trade).</summary>
    public sealed class OrderRateLimiter
    {
        private readonly object _gate = new object();
        private readonly Queue<long> _timestampsMs = new Queue<long>();
        private readonly int _maxPerMinute;

        public OrderRateLimiter(int maxPerMinute)
        {
            _maxPerMinute = Math.Max(0, maxPerMinute);
        }

        public bool TryAdmit(out string reason)
        {
            if (_maxPerMinute <= 0)
            {
                reason = "ok";
                return true;
            }

            var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            lock (_gate)
            {
                while (_timestampsMs.Count > 0 && now - _timestampsMs.Peek() > 60_000)
                    _timestampsMs.Dequeue();

                if (_timestampsMs.Count >= _maxPerMinute)
                {
                    reason = $"max_orders_per_minute:{_maxPerMinute}";
                    return false;
                }

                _timestampsMs.Enqueue(now);
                reason = "ok";
                return true;
            }
        }
    }
}
