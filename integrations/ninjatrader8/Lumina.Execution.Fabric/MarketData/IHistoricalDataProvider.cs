using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.MarketData
{
    /// <summary>
    /// Native historical bar source for RequestHistoricalData.
    /// SimHost has no NT data feed — use <see cref="NullHistoricalDataProvider"/>.
    /// NT8 AddOn injects a BarsRequest-backed implementation.
    /// </summary>
    public interface IHistoricalDataProvider
    {
        /// <summary>Provider kind for diagnostics (e.g. "nt", "null", "sim").</summary>
        string ProviderKind { get; }

        /// <summary>
        /// Fetch historical bars. Fail-closed: never invent prices.
        /// Returns response with Code=ok and Bars populated, or a non-ok Code.
        /// </summary>
        HistoricalDataResponse GetHistoricalBars(HistoricalDataRequest request);
    }

    /// <summary>
    /// Default when Fabric runs outside NinjaTrader (SimHost / unit tests).
    /// Honest fail-closed — never synthetic market bars for Birth/GREEN.
    /// </summary>
    public sealed class NullHistoricalDataProvider : IHistoricalDataProvider
    {
        public string ProviderKind => "null";

        public HistoricalDataResponse GetHistoricalBars(HistoricalDataRequest request)
        {
            return new HistoricalDataResponse
            {
                Instrument = request?.Instrument ?? "",
                CorrelationId = request?.CorrelationId ?? "",
                Code = "HOST_NO_NT_DATA",
                Message =
                    "This Fabric host has no NinjaTrader market-data feed (SimHost is execution-only). " +
                    "Start the NT8 LUMINA Execution Fabric AddOn with a connected data provider " +
                    "(Continuum/Kinetick/etc.) for historical bars.",
            };
        }
    }
}
