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
        /// <summary>
        /// Order gateway mode:
        /// - "nt" / "ninjatrader" / "account" / "sim101" → NT Account (Sim101 in NT process)
        /// - "memory" / "simhost" / "mock" → in-memory SimOrderGateway (CI / SimHost only)
        /// - "sim" (legacy) → treated as memory in CreateGateway; NT AddOn upgrades to Account bind
        /// </summary>
        public string GatewayMode { get; set; } = "nt";
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

        /// <summary>In-memory gateway (no NT Account, no exchange). SimHost / unit tests only.</summary>
        public bool UseMemoryGateway
        {
            get
            {
                var m = (GatewayMode ?? "").Trim();
                return string.Equals(m, "memory", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(m, "simhost", StringComparison.OrdinalIgnoreCase)
                    || string.Equals(m, "mock", StringComparison.OrdinalIgnoreCase);
            }
        }

        /// <summary>NT Account gateway intent (Sim101 product path; REAL requires promotion ADR).</summary>
        public bool UseNtGateway =>
            !UseMemoryGateway;

        // Hot-reload cache: Brain dual-writes fabric.json; host must not pin a stale
        // in-memory AuthToken across Systems Go / Repair without NT restart.
        private static string _tokenFileCachePath = "";
        private static DateTime _tokenFileCacheMtimeUtc = DateTime.MinValue;
        private static string _tokenFileCacheValue = "";

        /// <summary>
        /// Resolve auth token with live %APPDATA%\LUMINA\fabric.json preference.
        ///
        /// Root cause of "Safe mode - waiting for Lumina Brain heartbeats" at cold
        /// start: host loaded a short/stale AuthToken once, Brain later dual-wrote
        /// the SSOT 43-char token → AUTH_FAILED forever until host restart.
        /// Re-read on mtime change so bootstrap/align succeeds without NT kill.
        /// </summary>
        public string ResolveToken()
        {
            try
            {
                var path = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "LUMINA",
                    "fabric.json");
                if (File.Exists(path))
                {
                    var mtime = File.GetLastWriteTimeUtc(path);
                    if (_tokenFileCachePath != path
                        || _tokenFileCacheMtimeUtc != mtime
                        || string.IsNullOrEmpty(_tokenFileCacheValue))
                    {
                        var live = LoadFromFile(path);
                        var liveToken = (live.AuthToken ?? string.Empty).Trim();
                        if (!string.IsNullOrEmpty(liveToken))
                        {
                            _tokenFileCachePath = path;
                            _tokenFileCacheMtimeUtc = mtime;
                            _tokenFileCacheValue = liveToken;
                            // Keep instance field aligned for diagnostics / logs.
                            AuthToken = liveToken;
                            return liveToken;
                        }
                    }
                    else if (!string.IsNullOrEmpty(_tokenFileCacheValue))
                    {
                        AuthToken = _tokenFileCacheValue;
                        return _tokenFileCacheValue;
                    }
                }
            }
            catch
            {
                // Fall through to instance / env — never block auth on file I/O.
            }

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
