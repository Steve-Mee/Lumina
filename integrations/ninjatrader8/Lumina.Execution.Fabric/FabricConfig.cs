using System;
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
        public int HeartbeatTimeoutMs { get; set; } = 5000;
        public int FlattenGraceMs { get; set; } = 15000;
        public bool FlattenOnTimeout { get; set; } = true;
        public bool BindLocalhostOnly { get; set; } = true;
        public int MaxPositionSize { get; set; } = 10;
        public double DailyLossLimit { get; set; } = 0; // 0 = disabled in Phase 0
        public int MaxOrdersPerMinute { get; set; } = 60;

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
