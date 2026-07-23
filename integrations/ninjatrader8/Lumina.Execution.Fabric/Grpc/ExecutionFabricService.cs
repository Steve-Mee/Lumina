using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using Grpc.Core;
using Lumina.Execution.Fabric.Audit;
using Lumina.Execution.Fabric.Execution;
using Lumina.Execution.Fabric.Observability;
using Lumina.Execution.Fabric.Safety;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Grpc
{
    /// <summary>
    /// Fabric gRPC service — Safety + hardening (PR-D/E): risk engine, metrics, state sync, audit.
    /// </summary>
    public sealed class ExecutionFabricService : ExecutionFabric.ExecutionFabricBase
    {
        private readonly FabricConfig _config;
        private readonly IOrderGateway _gateway;
        private readonly SafeModeStateMachine _safeMode;
        private readonly HeartbeatWatchdog _watchdog;
        private readonly IdempotencyStore _idempotency;
        private readonly SessionHub _sessions;
        private readonly OrderRateLimiter _rateLimiter;
        private readonly PreTradeRiskEngine _preTrade;
        private readonly FabricMetrics _metrics;
        private readonly FabricAuditLog? _audit;
        private readonly Action<string>? _log;
        private readonly object _streamWriteGate = new object();

        public ExecutionFabricService(
            FabricConfig config,
            IOrderGateway gateway,
            SafeModeStateMachine safeMode,
            HeartbeatWatchdog watchdog,
            IdempotencyStore idempotency,
            SessionHub sessions,
            OrderRateLimiter rateLimiter,
            PreTradeRiskEngine preTrade,
            FabricMetrics metrics,
            FabricAuditLog? audit = null,
            Action<string>? log = null)
        {
            _config = config ?? throw new ArgumentNullException(nameof(config));
            _gateway = gateway ?? throw new ArgumentNullException(nameof(gateway));
            _safeMode = safeMode ?? throw new ArgumentNullException(nameof(safeMode));
            _watchdog = watchdog ?? throw new ArgumentNullException(nameof(watchdog));
            _idempotency = idempotency ?? throw new ArgumentNullException(nameof(idempotency));
            _sessions = sessions ?? throw new ArgumentNullException(nameof(sessions));
            _rateLimiter = rateLimiter ?? throw new ArgumentNullException(nameof(rateLimiter));
            _preTrade = preTrade ?? throw new ArgumentNullException(nameof(preTrade));
            _metrics = metrics ?? throw new ArgumentNullException(nameof(metrics));
            _audit = audit;
            _log = log;
        }

        public FabricMetrics Metrics => _metrics;

        public override async Task TradingStream(
            IAsyncStreamReader<BrainMessage> requestStream,
            IServerStreamWriter<FabricMessage> responseStream,
            ServerCallContext context)
        {
            var sessionId = Guid.NewGuid().ToString("D");
            var authenticated = false;
            _sessions.Register(sessionId, responseStream);
            _audit?.Record("session_open", "trading_stream_started", new { session_id = sessionId });

            try
            {
                while (await requestStream.MoveNext(context.CancellationToken).ConfigureAwait(false))
                {
                    var brain = requestStream.Current;
                    var replies = HandleBrainMessage(brain, ref authenticated, sessionId);
                    foreach (var reply in replies)
                        await WriteSafeAsync(responseStream, reply).ConfigureAwait(false);
                }
            }
            catch (OperationCanceledException)
            {
                // client disconnected
            }
            finally
            {
                _sessions.Unregister(sessionId);
                _audit?.Record("session_close", "trading_stream_ended", new { session_id = sessionId, authenticated });

                // Disconnect policy only when no Brain sessions remain (multi-session safe).
                if (authenticated && _sessions.SessionCount == 0)
                {
                    Log($"last session {sessionId} disconnected — applying disconnect policy");
                    ApplyDisconnectPolicy("brain_stream_closed");
                }
            }
        }

        public override Task<AccountState> GetAccountState(GetAccountStateRequest request, ServerCallContext context)
        {
            return Task.FromResult(BuildAccountState());
        }

        public override Task<HistoricalDataResponse> RequestHistoricalData(
            HistoricalDataRequest request,
            ServerCallContext context)
        {
            return Task.FromResult(new HistoricalDataResponse
            {
                Instrument = request?.Instrument ?? "",
                CorrelationId = request?.CorrelationId ?? "",
                Code = "NOT_IMPLEMENTED",
                Message = "Historical data deferred past Phase 1",
            });
        }

        public override Task<RiskParametersAck> SetRiskParameters(RiskParameters request, ServerCallContext context)
        {
            _audit?.Record("set_risk_parameters", "phase1_accept_echo", request);
            return Task.FromResult(new RiskParametersAck
            {
                Accepted = true,
                Message = "accepted_echo",
                Applied = request ?? new RiskParameters(),
            });
        }

        public override Task<RiskParameters> GetRiskParameters(GetRiskParametersRequest request, ServerCallContext context)
        {
            return Task.FromResult(new RiskParameters
            {
                MaxPositionSize = _config.MaxPositionSize,
                DailyLossLimit = _config.DailyLossLimit,
                MaxOrdersPerMinute = _config.MaxOrdersPerMinute,
                HeartbeatTimeoutMs = _config.HeartbeatTimeoutMs,
                FlattenGraceMs = _config.FlattenGraceMs,
                FlattenOnTimeout = _config.FlattenOnTimeout,
            });
        }

        public void PublishAlert(SafetyAlert alert)
        {
            if (alert == null)
                return;
            _audit?.Record("safety_alert", alert.Message, new
            {
                type = alert.AlertType.ToString(),
                severity = alert.Severity.ToString(),
                recommended = alert.RecommendedAction,
            });
            _sessions.Broadcast(new FabricMessage { SafetyAlert = alert });
        }

        public void PublishOrderEvents(IEnumerable<OrderEvent> events)
        {
            if (events == null)
                return;
            foreach (var evt in events)
            {
                _audit?.Record("order_event", evt.RejectionReason ?? evt.State.ToString(), new
                {
                    client_order_id = evt.ClientOrderId,
                    nt_order_id = evt.NtOrderId,
                    state = evt.State.ToString(),
                    instrument = evt.Instrument,
                });
                _sessions.Broadcast(new FabricMessage { OrderEvent = evt });
            }
        }

        private async Task WriteSafeAsync(IServerStreamWriter<FabricMessage> stream, FabricMessage message)
        {
            Task writeTask;
            lock (_streamWriteGate)
            {
                writeTask = stream.WriteAsync(message);
            }
            await writeTask.ConfigureAwait(false);
        }

        private List<FabricMessage> HandleBrainMessage(BrainMessage brain, ref bool authenticated, string sessionId)
        {
            var replies = new List<FabricMessage>();
            if (brain == null)
                return replies;

            switch (brain.PayloadCase)
            {
                case BrainMessage.PayloadOneofCase.AuthHello:
                {
                    var authOk = false;
                    replies.AddRange(HandleAuth(brain.AuthHello, sessionId, out authOk));
                    if (authOk)
                        authenticated = true;
                    break;
                }

                case BrainMessage.PayloadOneofCase.Heartbeat:
                    if (!authenticated)
                    {
                        replies.Add(Reject("", "", "UNAUTHENTICATED", "Auth required before heartbeat"));
                        break;
                    }
                    _watchdog.NoteHeartbeat();
                    replies.Add(new FabricMessage
                    {
                        Heartbeat = new Heartbeat
                        {
                            SequenceNumber = brain.Heartbeat.SequenceNumber,
                            TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                            BrainStatus = brain.Heartbeat.BrainStatus,
                            LastKnownStateHash = brain.Heartbeat.LastKnownStateHash,
                            FabricSafeMode = _safeMode.State,
                        },
                    });
                    break;

                case BrainMessage.PayloadOneofCase.PlaceOrder:
                    replies.AddRange(HandlePlace(brain.PlaceOrder, authenticated));
                    break;

                case BrainMessage.PayloadOneofCase.CancelOrder:
                    replies.AddRange(HandleCancel(brain.CancelOrder, authenticated));
                    break;

                case BrainMessage.PayloadOneofCase.ModifyOrder:
                    replies.AddRange(HandleModify(brain.ModifyOrder, authenticated));
                    break;

                case BrainMessage.PayloadOneofCase.Flatten:
                    replies.AddRange(HandleFlatten(brain.Flatten, authenticated));
                    break;

                case BrainMessage.PayloadOneofCase.SubscribeMarketData:
                case BrainMessage.PayloadOneofCase.UnsubscribeMarketData:
                    if (!authenticated)
                        replies.Add(Reject("", "", "UNAUTHENTICATED", "Auth required"));
                    break;

                default:
                    replies.Add(Reject("", "", "UNKNOWN_PAYLOAD", "Unsupported BrainMessage payload"));
                    break;
            }

            return replies;
        }

        private List<FabricMessage> HandleAuth(AuthHello hello, string sessionId, out bool authenticated)
        {
            authenticated = false;
            var expected = _config.ResolveToken();
            var provided = hello?.Token ?? "";
            if (string.IsNullOrEmpty(expected))
            {
                Log("AUTH reject: fabric token not configured");
                _metrics.IncAuthFail();
                _audit?.Record("auth_failed", "TOKEN_NOT_CONFIGURED", null);
                return new List<FabricMessage>
                {
                    new FabricMessage
                    {
                        AuthResult = new AuthResult
                        {
                            Ok = false,
                            Code = "TOKEN_NOT_CONFIGURED",
                            Message = "Set LUMINA_FABRIC_TOKEN (or config AuthToken)",
                        },
                    },
                };
            }

            if (!string.Equals(expected, provided, StringComparison.Ordinal))
            {
                Log("AUTH reject: bad token");
                _metrics.IncAuthFail();
                _audit?.Record("auth_failed", "AUTH_FAILED", new { session_id = sessionId });
                return new List<FabricMessage>
                {
                    new FabricMessage
                    {
                        AuthResult = new AuthResult
                        {
                            Ok = false,
                            Code = "AUTH_FAILED",
                            Message = "Invalid fabric token",
                        },
                    },
                };
            }

            authenticated = true;
            _metrics.IncAuthOk();
            _watchdog.NoteAuthenticatedSession();
            if (_safeMode.State == SafeModeState.Safe)
                _safeMode.ClearToNormal("brain_reauthenticated");

            Log($"AUTH ok session={sessionId} account={_gateway.AccountName} gateway={_gateway.GatewayKind}");
            _audit?.Record("auth_ok", "authenticated", new
            {
                session_id = sessionId,
                account = _gateway.AccountName,
                mode = hello?.ModeContext,
                gateway = _gateway.GatewayKind,
            });

            return new List<FabricMessage>
            {
                new FabricMessage
                {
                    AuthResult = new AuthResult
                    {
                        Ok = true,
                        SessionId = sessionId,
                        AccountName = _gateway.AccountName,
                        Code = "OK",
                        Message = "ok",
                    },
                },
                // Initial StateSync for reconciliation (blueprint §5.3).
                new FabricMessage { StateSync = BuildStateSync() },
            };
        }

        private IEnumerable<FabricMessage> HandlePlace(PlaceOrderCommand cmd, bool authenticated)
        {
            if (!authenticated)
            {
                yield return Reject(cmd?.CorrelationId ?? "", cmd?.ClientOrderId ?? "", "UNAUTHENTICATED", "Auth required");
                yield break;
            }

            if (_safeMode.State == SafeModeState.FullSafe)
            {
                yield return Reject(
                    cmd?.CorrelationId ?? "",
                    cmd?.ClientOrderId ?? "",
                    "FULL_SAFE",
                    "FULL_SAFE: only human/manual override can place orders");
                yield break;
            }

            if (!_safeMode.AcceptsNewOrders)
            {
                yield return Reject(
                    cmd?.CorrelationId ?? "",
                    cmd?.ClientOrderId ?? "",
                    "SAFE_MODE",
                    $"Fabric safe mode blocks new orders: {_safeMode.State}");
                yield break;
            }

            if (cmd == null || string.IsNullOrWhiteSpace(cmd.ClientOrderId))
            {
                yield return Reject(cmd?.CorrelationId ?? "", "", "INVALID", "client_order_id required");
                yield break;
            }

            if (_idempotency.TryGet(cmd.ClientOrderId, out var prior))
            {
                _metrics.IncIdempotentReplay();
                _audit?.Record("place_idempotent_replay", "client_order_id_seen", new { client_order_id = cmd.ClientOrderId });
                yield return new FabricMessage { OrderEvent = prior };
                yield break;
            }

            if (!_rateLimiter.TryAdmit(out var rateReason))
            {
                _metrics.IncPlaceRejected();
                var rateRejected = new OrderEvent
                {
                    ClientOrderId = cmd.ClientOrderId,
                    State = OrderState.Rejected,
                    RejectionReason = rateReason,
                    Instrument = cmd.Instrument,
                    Action = cmd.Action,
                    CorrelationId = cmd.CorrelationId ?? "",
                    TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                };
                _idempotency.Remember(cmd.ClientOrderId, rateRejected);
                _audit?.Record("place_rejected", rateReason, new { client_order_id = cmd.ClientOrderId });
                yield return new FabricMessage { OrderEvent = rateRejected };
                yield break;
            }

            if (!_preTrade.TryAdmitPlace(cmd, _gateway, out var riskReason))
            {
                _metrics.IncPlaceRejected();
                var rejected = new OrderEvent
                {
                    ClientOrderId = cmd.ClientOrderId,
                    State = OrderState.Rejected,
                    RejectionReason = riskReason,
                    Instrument = cmd.Instrument,
                    Action = cmd.Action,
                    CorrelationId = cmd.CorrelationId ?? "",
                    TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                };
                _idempotency.Remember(cmd.ClientOrderId, rejected);
                _audit?.Record("place_rejected", riskReason, new { client_order_id = cmd.ClientOrderId });
                yield return new FabricMessage { OrderEvent = rejected };
                yield break;
            }

            _metrics.IncPlace();
            _audit?.Record("place_order", "accepted_for_gateway", new
            {
                client_order_id = cmd.ClientOrderId,
                instrument = cmd.Instrument,
                qty = cmd.Quantity,
                protected_flag = cmd.Protected,
                reduce_only = cmd.ReduceOnly,
                correlation_id = cmd.CorrelationId,
            });

            var sw = Stopwatch.StartNew();
            var events = _gateway.PlaceOrder(cmd);
            sw.Stop();
            _metrics.ObservePlaceLatencyMs(sw.Elapsed.TotalMilliseconds);

            foreach (var evt in events)
            {
                _idempotency.Remember(cmd.ClientOrderId, evt);
                if (evt.State == OrderState.Rejected)
                    _metrics.IncPlaceRejected();
                else if (evt.State == OrderState.Filled || evt.State == OrderState.PartiallyFilled)
                    _metrics.IncPlaceFilled();
                _audit?.Record("order_event", evt.State.ToString(), new
                {
                    client_order_id = evt.ClientOrderId,
                    nt_order_id = evt.NtOrderId,
                    state = evt.State.ToString(),
                    correlation_id = evt.CorrelationId,
                });
                yield return new FabricMessage { OrderEvent = evt };
            }
        }

        private IEnumerable<FabricMessage> HandleCancel(CancelOrderCommand cmd, bool authenticated)
        {
            if (!authenticated)
            {
                yield return Reject(cmd?.CorrelationId ?? "", cmd?.ClientOrderId ?? "", "UNAUTHENTICATED", "Auth required");
                yield break;
            }

            // Cancel is allowed in SAFE_MODE (risk-reducing); blocked only in FULL_SAFE without emergency path.
            if (_safeMode.State == SafeModeState.FullSafe)
            {
                yield return Reject(cmd?.CorrelationId ?? "", cmd?.ClientOrderId ?? "", "FULL_SAFE", "FULL_SAFE blocks cancel without operator");
                yield break;
            }

            _metrics.IncCancel();
            _audit?.Record("cancel_order", "request", new
            {
                client_order_id = cmd?.ClientOrderId,
                nt_order_id = cmd?.NtOrderId,
            });

            foreach (var evt in _gateway.CancelOrder(cmd ?? new CancelOrderCommand()))
            {
                _audit?.Record("order_event", evt.State.ToString(), new { client_order_id = evt.ClientOrderId, state = evt.State.ToString() });
                yield return new FabricMessage { OrderEvent = evt };
            }
        }

        private IEnumerable<FabricMessage> HandleModify(ModifyOrderCommand cmd, bool authenticated)
        {
            if (!authenticated)
            {
                yield return Reject(cmd?.CorrelationId ?? "", cmd?.ClientOrderId ?? "", "UNAUTHENTICATED", "Auth required");
                yield break;
            }

            if (!_safeMode.AcceptsNewOrders)
            {
                yield return Reject(cmd?.CorrelationId ?? "", cmd?.ClientOrderId ?? "", "SAFE_MODE", "SAFE_MODE blocks modify");
                yield break;
            }

            _metrics.IncModify();
            _audit?.Record("modify_order", "request", new
            {
                client_order_id = cmd?.ClientOrderId,
                qty = cmd?.Quantity,
                price = cmd?.Price,
            });

            foreach (var evt in _gateway.ModifyOrder(cmd ?? new ModifyOrderCommand()))
            {
                if (!string.IsNullOrEmpty(evt.ClientOrderId))
                    _idempotency.Remember(evt.ClientOrderId, evt);
                yield return new FabricMessage { OrderEvent = evt };
            }
        }

        private IEnumerable<FabricMessage> HandleFlatten(FlattenCommand cmd, bool authenticated)
        {
            if (!authenticated)
            {
                yield return Reject(cmd?.CorrelationId ?? "", "", "UNAUTHENTICATED", "Auth required");
                yield break;
            }

            // Flatten is risk-reducing: allowed in SAFE_MODE; allowed in FULL_SAFE only if emergency.
            if (_safeMode.State == SafeModeState.FullSafe && !(cmd?.Emergency ?? false))
            {
                yield return Reject(cmd?.CorrelationId ?? "", "", "FULL_SAFE", "FULL_SAFE requires emergency flatten flag");
                yield break;
            }

            _metrics.IncFlatten();
            _audit?.Record("flatten", cmd?.Emergency == true ? "emergency" : "normal", new
            {
                instrument = cmd?.Instrument,
            });

            foreach (var evt in _gateway.Flatten(cmd ?? new FlattenCommand()))
                yield return new FabricMessage { OrderEvent = evt };
        }

        private void ApplyDisconnectPolicy(string reason)
        {
            _safeMode.EnterSafe(reason);
            _metrics.IncSafeMode();
            _metrics.IncDisconnectPolicy();
            var cancelled = _gateway.CancelNonProtected(reason);
            PublishOrderEvents(cancelled);
            PublishAlert(new SafetyAlert
            {
                AlertType = SafetyAlertType.SafeModeEntered,
                Severity = SafetySeverity.Critical,
                Message = $"Disconnect policy applied: {reason}; cancelled_non_protected={cancelled.Count}",
                RecommendedAction = "cancel_non_protected",
                TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                CorrelationId = Guid.NewGuid().ToString("D"),
            });
            _audit?.Record("disconnect_policy", reason, new { cancelled = cancelled.Count });
        }

        private AccountState BuildAccountState()
        {
            var state = new AccountState
            {
                Account = _gateway.GetAccountMetrics(),
                SafeMode = _safeMode.State,
                TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            };
            state.Positions.AddRange(_gateway.GetPositions());
            state.OpenOrders.AddRange(_gateway.GetWorkingOrders());
            return state;
        }

        private StateSyncResponse BuildStateSync()
        {
            var acct = _gateway.GetAccountMetrics();
            var positions = _gateway.GetPositions();
            var orders = _gateway.GetWorkingOrders();
            var hash = ComputeStateHash(acct, positions, orders);
            var sync = new StateSyncResponse
            {
                Account = acct,
                SafeMode = _safeMode.State,
                TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                StateHash = hash,
            };
            sync.Positions.AddRange(positions);
            sync.OpenOrders.AddRange(orders);
            return sync;
        }

        private static string ComputeStateHash(
            AccountMetrics acct,
            IReadOnlyList<PositionUpdate> positions,
            IReadOnlyList<WorkingOrder> orders)
        {
            var sb = new StringBuilder();
            sb.Append(acct?.AccountName).Append('|').Append(acct?.Equity).Append('|');
            foreach (var p in positions)
                sb.Append(p.Instrument).Append(':').Append(p.Quantity).Append(':').Append(p.Side).Append(';');
            foreach (var o in orders)
                sb.Append(o.ClientOrderId).Append(':').Append(o.Quantity).Append(':').Append(o.State).Append(';');
            using (var sha = SHA256.Create())
            {
                var bytes = sha.ComputeHash(Encoding.UTF8.GetBytes(sb.ToString()));
                var hex = new StringBuilder(bytes.Length * 2);
                foreach (var b in bytes)
                    hex.Append(b.ToString("x2"));
                return hex.ToString().Substring(0, 16);
            }
        }

        private FabricMessage Reject(string correlationId, string clientOrderId, string code, string message)
        {
            _audit?.Record("command_reject", message, new { code, correlation_id = correlationId, client_order_id = clientOrderId });
            return new FabricMessage
            {
                CommandReject = new CommandReject
                {
                    CorrelationId = correlationId ?? "",
                    ClientOrderId = clientOrderId ?? "",
                    Code = code ?? "REJECT",
                    Message = message ?? "",
                    SafeMode = _safeMode.State,
                },
            };
        }

        private void Log(string message) => _log?.Invoke("[Fabric] " + message);
    }
}
