using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading;

namespace Lumina.Execution.Fabric.Observability
{
    /// <summary>
    /// In-process + on-disk health snapshot for the LUMINA Link status window (status-only).
    /// Fail-closed: GREEN only when host is running AND ≥1 authenticated Brain session.
    /// </summary>
    public sealed class FabricRuntimeStatus
    {
        public static FabricRuntimeStatus Instance { get; } = new FabricRuntimeStatus();

        private readonly object _gate = new object();
        private readonly ConcurrentDictionary<string, byte> _authSessions =
            new ConcurrentDictionary<string, byte>(StringComparer.Ordinal);

        private string _hostState = "stopped";
        private string _hostCode = "not_started";
        private string? _detail;
        private string _bindHost = "127.0.0.1";
        private int _port = 50051;
        private string _gateway = "nt";
        private string _account = "Sim101";
        private string _historical = "none";
        private string _hostKind = "unknown";
        private string _safeMode = "NORMAL";
        private bool _accountBound = true;
        private DateTime? _lastAuthUtc;
        private string? _lastHistInstrument;
        private int _lastHistBars;
        private string? _lastHistCode;
        private DateTime? _lastHistUtc;
        private long _updatedUtcTicks = DateTime.UtcNow.Ticks;
        /// <summary>Non-secret token identity (sha256 hex first 16) for Brain match-proof.</summary>
        private string _tokenFp = "";

        private FabricRuntimeStatus() { }

        /// <summary>
        /// Publish token fingerprint so Brain can detect dual-truth without reading the secret.
        /// </summary>
        public void SetTokenFingerprint(string? tokenOrFingerprint)
        {
            var raw = (tokenOrFingerprint ?? "").Trim();
            if (string.IsNullOrEmpty(raw))
                return;
            // Accept precomputed 16-hex fingerprint or hash the raw token.
            var fp = raw.Length == 16 && IsHex(raw)
                ? raw.ToLowerInvariant()
                : TokenFingerprint(raw);
            lock (_gate)
            {
                _tokenFp = fp;
                TouchUnlocked();
            }
            Persist();
        }

        public static string TokenFingerprint(string token)
        {
            var tok = (token ?? "").Trim();
            if (string.IsNullOrEmpty(tok))
                return "";
            using var sha = SHA256.Create();
            var hash = sha.ComputeHash(Encoding.UTF8.GetBytes(tok));
            var sb = new StringBuilder(16);
            for (var i = 0; i < 8; i++)
                sb.Append(hash[i].ToString("x2"));
            return sb.ToString();
        }

        private static bool IsHex(string s)
        {
            foreach (var c in s)
            {
                var ok = (c >= '0' && c <= '9')
                    || (c >= 'a' && c <= 'f')
                    || (c >= 'A' && c <= 'F');
                if (!ok)
                    return false;
            }
            return true;
        }

        public void SetHostRunning(
            string hostKind,
            string bindHost,
            int port,
            string gateway,
            string account,
            string historicalProvider,
            string code = "ok",
            string? detail = null)
        {
            lock (_gate)
            {
                _hostState = "running";
                _hostCode = code ?? "ok";
                _detail = detail;
                _hostKind = hostKind ?? "unknown";
                _bindHost = string.IsNullOrWhiteSpace(bindHost) ? "127.0.0.1" : bindHost.Trim();
                _port = port > 0 ? port : 50051;
                _gateway = string.IsNullOrWhiteSpace(gateway) ? "nt" : gateway.Trim();
                _account = string.IsNullOrWhiteSpace(account) ? "Sim101" : account.Trim();
                _historical = string.IsNullOrWhiteSpace(historicalProvider) ? "none" : historicalProvider.Trim();
                TouchUnlocked();
            }
            Persist();
        }

        public void SetHostStopped(string code = "clean", string? detail = null)
        {
            lock (_gate)
            {
                _hostState = "stopped";
                _hostCode = code ?? "clean";
                _detail = detail;
                _authSessions.Clear();
                TouchUnlocked();
            }
            Persist();
        }

        public void SetHostError(string code, string? detail)
        {
            lock (_gate)
            {
                _hostState = "error";
                _hostCode = code ?? "error";
                _detail = detail;
                TouchUnlocked();
            }
            Persist();
        }

        public void NoteAuthOk(string sessionId)
        {
            if (!string.IsNullOrEmpty(sessionId))
                _authSessions[sessionId] = 1;
            lock (_gate)
            {
                _lastAuthUtc = DateTime.UtcNow;
                TouchUnlocked();
            }
            Persist();
        }

        public void NoteSessionClosed(string sessionId)
        {
            if (!string.IsNullOrEmpty(sessionId))
                _authSessions.TryRemove(sessionId, out _);
            lock (_gate)
            {
                TouchUnlocked();
            }
            Persist();
        }

        public void NoteAuthFail()
        {
            lock (_gate)
            {
                TouchUnlocked();
            }
            // no persist spam on every fail — light touch only
        }

        public void NoteHistorical(string? instrument, int bars, string? code)
        {
            lock (_gate)
            {
                _lastHistInstrument = instrument ?? "";
                _lastHistBars = bars;
                _lastHistCode = code ?? "";
                _lastHistUtc = DateTime.UtcNow;
                TouchUnlocked();
            }
            Persist();
        }

        public void NoteSafeMode(string safeMode)
        {
            lock (_gate)
            {
                _safeMode = string.IsNullOrWhiteSpace(safeMode) ? "NORMAL" : safeMode.Trim().ToUpperInvariant();
                TouchUnlocked();
            }
            Persist();
        }

        public void NoteBound(bool bound)
        {
            lock (_gate)
            {
                _accountBound = bound;
                TouchUnlocked();
            }
            Persist();
        }

        /// <summary>Thread-safe snapshot for UI / JSON.</summary>
        public IReadOnlyDictionary<string, object?> Snapshot()
        {
            lock (_gate)
            {
                var sessions = _authSessions.Count;
                double? ageSec = null;
                try
                {
                    var updated = new DateTime(Interlocked.Read(ref _updatedUtcTicks), DateTimeKind.Utc);
                    ageSec = Math.Max(0.0, (DateTime.UtcNow - updated).TotalSeconds);
                }
                catch { /* ignore */ }
                var level = ComputeLevel(_hostState, sessions, _safeMode, _hostCode, ageSec);
                var meaning = ComputeMeaning(
                    _hostState, _hostCode, sessions, _safeMode, _account, _detail, ageSec);
                return new Dictionary<string, object?>
                {
                    ["state"] = _hostState,
                    ["code"] = _hostCode,
                    ["detail"] = _detail,
                    ["level"] = level,
                    ["meaning"] = meaning,
                    ["bind_host"] = _bindHost,
                    ["port"] = _port,
                    ["grpc"] = _bindHost + ":" + _port,
                    ["gateway"] = _gateway,
                    ["account"] = _account,
                    ["bound"] = _accountBound,
                    ["historical"] = _historical,
                    ["host"] = _hostKind,
                    ["active_sessions"] = sessions,
                    ["safe_mode"] = _safeMode,
                    ["last_auth_utc"] = _lastAuthUtc?.ToString("o"),
                    ["last_hist_instrument"] = _lastHistInstrument,
                    ["last_hist_bars"] = _lastHistBars,
                    ["last_hist_code"] = _lastHistCode,
                    ["last_hist_utc"] = _lastHistUtc?.ToString("o"),
                    ["updated_utc"] = new DateTime(Interlocked.Read(ref _updatedUtcTicks), DateTimeKind.Utc).ToString("o"),
                    ["pid"] = System.Diagnostics.Process.GetCurrentProcess().Id,
                    ["token_fp"] = string.IsNullOrEmpty(_tokenFp) ? null : _tokenFp,
                };
            }
        }

        public string ToJson()
        {
            return JsonSerializer.Serialize(Snapshot());
        }

        public void Persist()
        {
            try
            {
                var dir = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "LUMINA");
                Directory.CreateDirectory(dir);
                var path = Path.Combine(dir, "fabric-nt-host.json");
                File.WriteAllText(path, ToJson());
            }
            catch
            {
                /* never throw from status */
            }
        }

        /// <summary>
        /// GREEN = host running + ≥1 auth session and not FULL_SAFE.
        /// AMBER = host running, waiting for Brain and/or SAFE mode.
        /// RED = host stopped/error.
        /// </summary>
        /// <summary>
        /// Shared color dictionary with Python fabric_link_health.compute_level.
        /// GREEN = running + session + not SAFE/FULL_SAFE.
        /// RESTARTING = clean stop within grace (seconds) — not permanent RED.
        /// </summary>
        public static string ComputeLevel(
            string hostState,
            int authSessions,
            string safeMode,
            string? hostCode = null,
            double? updatedAgeSec = null)
        {
            if (!string.Equals(hostState, "running", StringComparison.OrdinalIgnoreCase))
            {
                var code = (hostCode ?? "").Trim();
                if (string.Equals(hostState, "stopped", StringComparison.OrdinalIgnoreCase)
                    && (string.IsNullOrEmpty(code)
                        || string.Equals(code, "clean", StringComparison.OrdinalIgnoreCase)
                        || string.Equals(code, "not_running", StringComparison.OrdinalIgnoreCase))
                    && updatedAgeSec.HasValue
                    && updatedAgeSec.Value <= 8.0)
                {
                    return "RESTARTING";
                }
                return "RED";
            }

            var sm = (safeMode ?? "NORMAL").ToUpperInvariant();
            if (sm == "FULL_SAFE")
                return "AMBER";
            if (authSessions > 0)
                return sm == "SAFE" ? "AMBER" : "GREEN";
            return "AMBER";
        }

        public static string ComputeMeaning(
            string hostState,
            string hostCode,
            int authSessions,
            string safeMode,
            string account,
            string? detail,
            double? updatedAgeSec = null)
        {
            // ASCII punctuation only (NT Link window JSON unescape is simple).
            if (string.Equals(hostState, "error", StringComparison.OrdinalIgnoreCase))
            {
                if (string.Equals(hostCode, "port_in_use", StringComparison.OrdinalIgnoreCase))
                    return "Bridge failed - port in use (stop SimHost / Repair in Lumina)";
                if (string.Equals(hostCode, "no_token", StringComparison.OrdinalIgnoreCase))
                    return "Bridge failed - fabric token missing (Repair in Lumina app)";
                return "Bridge error - open Lumina -> Setup -> Repair connection"
                    + (string.IsNullOrWhiteSpace(detail) ? "" : " (" + detail + ")");
            }

            if (!string.Equals(hostState, "running", StringComparison.OrdinalIgnoreCase))
            {
                var code = hostCode ?? "";
                if (string.Equals(hostState, "stopped", StringComparison.OrdinalIgnoreCase)
                    && (string.IsNullOrEmpty(code)
                        || string.Equals(code, "clean", StringComparison.OrdinalIgnoreCase)
                        || string.Equals(code, "not_running", StringComparison.OrdinalIgnoreCase))
                    && updatedAgeSec.HasValue
                    && updatedAgeSec.Value <= 8.0)
                {
                    return "Host restarting - wait a few seconds (do not Repair yet)";
                }
                return "Bridge not running - open Lumina -> Setup -> Repair connection";
            }

            var sm = (safeMode ?? "NORMAL").ToUpperInvariant();
            if (sm == "FULL_SAFE")
                return "Full safe mode - new orders blocked (Brain heartbeat / recover)";
            if (sm == "SAFE")
                return "Safe mode - new orders blocked until Brain heartbeats";

            if (authSessions > 0)
                return "Lumina Brain connected · " + (string.IsNullOrWhiteSpace(account) ? "Sim101" : account);

            return "Bridge ready - open Lumina to trade / train";
        }

        private void TouchUnlocked()
        {
            Interlocked.Exchange(ref _updatedUtcTicks, DateTime.UtcNow.Ticks);
        }
    }
}
