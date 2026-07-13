// Skeleton — see docs/ninjatrader-integration.md §3 for full implementation plan.

namespace LuminaNt8AddOn
{
    /// <summary>
    /// NT8 AddOn entry point. Connects to Core WS /ws/ninjatrader/v1 on State.Active.
    /// </summary>
    public class AddOn : NinjaTrader.NinjaScript.AddOnBase
    {
        private LuminaWebSocketClient _client;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "LUMINA NT8 Add-on";
                Description = "LUMINA Core execution and market-data bridge";
            }
            else if (State == State.Active)
            {
                _client = new LuminaWebSocketClient();
                _client.Connect();
            }
            else if (State == State.Terminated)
            {
                _client?.Disconnect();
                _client = null;
            }
        }
    }
}
