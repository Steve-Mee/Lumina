using System;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.MarketData
{
    /// <summary>
    /// Live last/bid/ask (or bar) push into the TradingStream.
    /// Null/default provider rejects subscribe fail-closed (no CrossTrade invent).
    /// </summary>
    public interface ILiveMarketDataProvider
    {
        string ProviderKind { get; }

        /// <summary>Subscribe instrument. Returns code: ok | INSTRUMENT_NOT_FOUND | ...</summary>
        string Subscribe(string instrument, string correlationId, Action<MarketDataUpdate> onUpdate);

        void Unsubscribe(string instrument);

        void UnsubscribeAll();
    }

    /// <summary>Default outside NT — honest fail-closed.</summary>
    public sealed class NullLiveMarketDataProvider : ILiveMarketDataProvider
    {
        public string ProviderKind => "null";

        public string Subscribe(string instrument, string correlationId, Action<MarketDataUpdate> onUpdate)
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
