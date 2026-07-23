using System;
using System.Collections.Generic;
using System.Linq;
using Lumina.Execution.Fabric.Execution;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Safety
{
    /// <summary>
    /// Fabric-side pre-trade checks independent of Brain admission (defense in depth).
    /// </summary>
    public sealed class PreTradeRiskEngine
    {
        private readonly FabricConfig _config;

        public PreTradeRiskEngine(FabricConfig config)
        {
            _config = config ?? throw new ArgumentNullException(nameof(config));
        }

        public bool TryAdmitPlace(PlaceOrderCommand cmd, IOrderGateway gateway, out string reason)
        {
            if (cmd == null)
            {
                reason = "null_command";
                return false;
            }

            if (_config.MaxPositionSize > 0 && cmd.Quantity > _config.MaxPositionSize)
            {
                reason = $"max_position_size:{_config.MaxPositionSize}";
                return false;
            }

            var instrument = cmd.Instrument ?? "";
            if (_config.MaxPositionByInstrument != null &&
                !string.IsNullOrEmpty(instrument) &&
                _config.MaxPositionByInstrument.TryGetValue(instrument, out var instMax) &&
                instMax > 0 &&
                cmd.Quantity > instMax)
            {
                reason = $"max_position_instrument:{instrument}:{instMax}";
                return false;
            }

            // Projected net size vs instrument cap (if configured).
            if (_config.MaxPositionByInstrument != null &&
                !string.IsNullOrEmpty(instrument) &&
                _config.MaxPositionByInstrument.TryGetValue(instrument, out var cap) &&
                cap > 0)
            {
                var projected = ProjectedAbsPosition(gateway, instrument, cmd.Action, cmd.Quantity);
                if (projected > cap)
                {
                    reason = $"projected_position_exceeds:{instrument}:{projected}>{cap}";
                    return false;
                }
            }

            if (_config.DailyLossLimit > 0)
            {
                var acct = gateway.GetAccountMetrics();
                // RealizedPnlToday negative = loss. Block when loss exceeds limit.
                if (acct.RealizedPnlToday <= -Math.Abs(_config.DailyLossLimit))
                {
                    reason = $"daily_loss_limit:{_config.DailyLossLimit}";
                    return false;
                }
            }

            reason = "ok";
            return true;
        }

        private static int ProjectedAbsPosition(
            IOrderGateway gateway,
            string instrument,
            OrderAction action,
            int qty)
        {
            var pos = gateway.GetPositions()
                .FirstOrDefault(p => string.Equals(p.Instrument, instrument, StringComparison.OrdinalIgnoreCase));
            var net = 0;
            if (pos != null)
            {
                net = string.Equals(pos.Side, "SHORT", StringComparison.OrdinalIgnoreCase) ||
                      string.Equals(pos.Side, "SELL", StringComparison.OrdinalIgnoreCase)
                    ? -Math.Abs(pos.Quantity)
                    : Math.Abs(pos.Quantity);
            }

            var delta = action == OrderAction.Buy ? qty : -qty;
            return Math.Abs(net + delta);
        }
    }
}
