using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;

namespace Lumina.Execution.Fabric
{
    /// <summary>
    /// Local Fabric host configuration. Prefer %APPDATA%\LUMINA\fabric.json (never commit secrets).
    /// </summary>
    public sealed class FabricConfig
    {
        public string BindHost { get; set; } = "127.0.0.1";
        public int BindPort { get; set; } = 50051;
        public string AuthTokenEnv { get; set; } = "LUMINA_FABRIC_TOKEN";
        public string AuthToken { get; set; } = "";
        public string AccountName { get; set; } = "Sim101";
        /// <summary>Order gateway: "sim" (default) or "nt" (live Account gateway when bound).</summary>
        public string GatewayMode { get; set; } = "sim";
        public int HeartbeatTimeoutMs { get; set; } = 5000;
        public int FlattenGraceMs { get; set; } = 15000;
        public bool FlattenOnTimeout { get; set; } = true;
        public bool BindLocalhostOnly { get; set; } = true;
        public int MaxPositionSize { get; set; } = 10;
        public double DailyLossLimit { get; set; } = 0; // 0 = disabled
        public int MaxOrdersPerMinute { get; set; } = 60;
        /// <summary>Per-instrument max absolute position (0/absent = use MaxPositionSize only).</summary>
        public Dictionary<string, int>? MaxPositionByInstrument { get; set; }
        /// <summary>Optional path for append-only fabric-audit.jsonl (default %APPDATA%\LUMINA\).</summary>
        public string? AuditLogPath { get; set; }

        public bool UseNtGateway =>
            string.Equals(GatewayMode, "nt", StringComparison.OrdinalIgnoreCase) ||
            string.Equals(GatewayMode, "ninjatrader", StringComparison.OrdinalIgnoreCase);

        public string ResolveToken()
        {
            if (!string.IsNullOrWhiteSpace(AuthToken))
                return AuthToken.Trim();

            var envName = string.IsNullOrWhiteSpace(AuthTokenEnv) ? "LUMINA_FABRIC_TOKEN" : AuthTokenEnv.Trim();
            var token = Environment.GetEnvironmentVariable(envName);
            if (string.IsNullOrWhiteSpace(token))
                token = Environment.GetEnvironmentVariable("LUMINA_NT8_API_KEY");
            return (token ?? string.Empty).Trim();
        }

        public void EnforceLocalhostOnly()
        {
            if (!BindLocalhostOnly)
                return;
            if (BindHost != "127.0.0.1" && BindHost != "localhost" && BindHost != "::1")
                throw new InvalidOperationException(
                    $"Fabric bind host '{BindHost}' rejected: bind_localhost_only=true (ADR-0035).");
        }

        public static FabricConfig LoadDefault()
        {
            var path = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "LUMINA",
                "fabric.json");
            if (File.Exists(path))
                return LoadFromFile(path);
            return new FabricConfig();
        }

        public static FabricConfig LoadFromFile(string path)
        {
            var json = File.ReadAllText(path);
            var cfg = JsonSerializer.Deserialize<FabricConfig>(json, new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
            }) ?? new FabricConfig();
            return cfg;
        }
    }
}
