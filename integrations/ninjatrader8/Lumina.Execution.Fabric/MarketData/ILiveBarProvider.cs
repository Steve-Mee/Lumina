using System;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.MarketData
{
    /// <summary>
    /// Live NinjaTrader Last bars (ADR-0053/0054). Null host is fail-closed.
    /// </summary>
    public interface ILiveBarProvider
    {
        string ProviderKind { get; }

        /// <summary>Subscribe native Last bars for one period. Returns ok | TRADING_HOURS_MISSING | BAR_PERIOD_UNSUPPORTED | …</summary>
        string Subscribe(string instrument, string barPeriod, string correlationId, Action<MarketDataUpdate> onUpdate);

        void Unsubscribe(string instrument);

        void UnsubscribeAll();
    }

    /// <summary>Default outside NT — honest fail-closed, never invent bars.</summary>
    public sealed class NullLiveBarProvider : ILiveBarProvider
    {
        public string ProviderKind => "null";

        public string Subscribe(string instrument, string barPeriod, string correlationId, Action<MarketDataUpdate> onUpdate)
        {
            return "HOST_NO_NT_LIVE_DATA";
        }

        public void Unsubscribe(string instrument)
        {
        }

        public void UnsubscribeAll()
        {
        }
    }
}
