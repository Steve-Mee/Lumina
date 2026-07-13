# Lumina NT8 Add-on (skeleton)

Native NinjaTrader 8 add-on that connects to LUMINA Core at `ws://127.0.0.1:8000/ws/ninjatrader/v1`.

## Status

Skeleton only — implement C# sources under this directory per [ninjatrader-integration.md](../../docs/ninjatrader-integration.md).

## Build (planned)

1. Open `LuminaNt8AddOn.csproj` in Visual Studio targeting .NET Framework compatible with NT8.
2. Build Release.
3. Copy output `.dll` to `%USERPROFILE%\Documents\NinjaTrader 8\bin\Custom\AddOns\`.
4. Restart NinjaTrader 8 and enable **LUMINA NT8 Add-on** in Control Center.

## Configuration

Local config: `%APPDATA%\LUMINA\nt8-addon.json` (not committed):

```json
{
  "core_ws_url": "ws://127.0.0.1:8000/ws/ninjatrader/v1",
  "api_key_ref": "lumina_nt8_key",
  "account_name": "Sim101"
}
```

Set `LUMINA_NT8_API_KEY` in the Core `.env` to match the add-on token.

## Manual checklist

- [ ] Add-on authenticates within 5 seconds (`auth` frame)
- [ ] `connection_status` published every 500 ms while connected
- [ ] Inbound `submit_order` executed on configured sim account only
- [ ] Reconnect uses exponential backoff (1 s → 30 s cap)
