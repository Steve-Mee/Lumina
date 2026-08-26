// ============================================================
// Intentionally NO AddOnBase in the bridge DLL.
// NT auto-loads every DLL in Custom\ as "vendor" — a second AddOnBase here
// races the source AddOn and historically bound a STALE assembly without FabricNtHost.
//
// Authoritative entry: bin\Custom\AddOns\@LuminaFabricHost.cs (compiled into NinjaTrader.Custom)
// which reflects into FabricNtHost in Lumina.Fabric.NtBridge.dll.
// ============================================================
