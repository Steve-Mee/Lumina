using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Grpc.Core;
using Lumina.Execution.Fabric.Execution;
using Lumina.Execution.Fabric.Safety;
using Lumina.Execution.V1;

namespace Lumina.Execution.Fabric.Grpc
{
    /// <summary>
    /// Fabric gRPC service implementation (server side).
    /// </summary>
    public sealed class ExecutionFabricService : ExecutionFabric.ExecutionFabricBase
    {
        private readonly FabricConfig _config;
        private readonly IOrderGateway _gateway;
        private readonly SafeModeStateMachine _safeMode;
        private readonly HeartbeatWatchdog _watchdog;
        private readonly IdempotencyStore _idempotency;
        private readonly SessionHub _sessions;
        private readonly Action<string>? _log;
        private readonly object _streamWriteGate = new object();

        public ExecutionFabricService(
            FabricConfig config,
            IOrderGateway gateway,
            SafeModeStateMachine safeMode,
            HeartbeatWatchdog watchdog,
            IdempotencyStore idempotency,
            SessionHub sessions,
            Action<string>? log = null)
        {
            _config = config ?? throw new ArgumentNullException(nameof(config));
            _gateway = gateway ?? throw new ArgumentNullException(nameof(gateway));
            _safeMode = safeMode ?? throw new ArgumentNullException(nameof(safeMode));
            _watchdog = watchdog ?? throw new ArgumentNullException(nameof(watchdog));
            _idempotency = idempotency ?? throw new ArgumentNullException(nameof(idempotency));
            _sessions = sessions ?? throw new ArgumentNullException(nameof(sessions));
            _log = log;
        }

        public override async Task TradingStream(
            IAsyncStreamReader<BrainMessage> requestStream,
            IServerStreamWriter<FabricMessage> responseStream,
            ServerCallContext context)
        {
            var sessionId = Guid.NewGuid().ToString("D");
            var authenticated = false;
            _sessions.Register(sessionId, responseStream);

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
                if (authenticated)
                {
                    Log($"session {sessionId} disconnected — applying disconnect policy");
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
                Message = "Historical data deferred past Phase 0",
            });
        }

        public override Task<RiskParametersAck> SetRiskParameters(RiskParameters request, ServerCallContext context)
        {
            return Task.FromResult(new RiskParametersAck
            {
                Accepted = true,
                Message = "accepted_phase0_noop",
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
            _sessions.Broadcast(new FabricMessage { SafetyAlert = alert });
        }

        public void PublishOrderEvents(IEnumerable<OrderEvent> events)
        {
            if (events == null)
                return;
            foreach (var evt in events)
                _sessions.Broadcast(new FabricMessage { OrderEvent = evt });
        }

        private async Task WriteSafeAsync(IServerStreamWriter<FabricMessage> stream, FabricMessage message)
        {
            // Serialize stream writes for this session.
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
                    replies.Add(HandleAuth(brain.AuthHello, ref authenticated, sessionId));
                    break;

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

                case BrainMessage.PayloadOneofCase.Flatten:
                    replies.AddRange(HandleFlatten(brain.Flatten, authenticated));
                    break;

                case BrainMessage.PayloadOneofCase.ModifyOrder:
                    replies.Add(Reject(
                        brain.ModifyOrder?.CorrelationId ?? "",
                        brain.ModifyOrder?.ClientOrderId ?? "",
                        "NOT_IMPLEMENTED",
                        "ModifyOrder deferred past Phase 0"));
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

        private FabricMessage HandleAuth(AuthHello hello, ref bool authenticated, string sessionId)
        {
            var expected = _config.ResolveToken();
            var provided = hello?.Token ?? "";
            if (string.IsNullOrEmpty(expected))
            {
                Log("AUTH reject: fabric token not configured");
                return new FabricMessage
                {
                    AuthResult = new AuthResult
                    {
                        Ok = false,
                        Code = "TOKEN_NOT_CONFIGURED",
                        Message = "Set LUMINA_FABRIC_TOKEN (or config AuthToken)",
                    },
                };
            }

            if (!string.Equals(expected, provided, StringComparison.Ordinal))
            {
                Log("AUTH reject: bad token");
                return new FabricMessage
                {
                    AuthResult = new AuthResult
                    {
                        Ok = false,
                        Code = "AUTH_FAILED",
                        Message = "Invalid fabric token",
                    },
                };
            }

            authenticated = true;
            _watchdog.NoteAuthenticatedSession();
            if (_safeMode.State == SafeModeState.Safe)
                _safeMode.ClearToNormal("brain_reauthenticated");

            Log($"AUTH ok session={sessionId} account={_gateway.AccountName}");
            return new FabricMessage
            {
                AuthResult = new AuthResult
                {
                    Ok = true,
                    SessionId = sessionId,
                    AccountName = _gateway.AccountName,
                    Code = "OK",
                    Message = "ok",
                },
            };
        }

        private IEnumerable<FabricMessage> HandlePlace(PlaceOrderCommand cmd, bool authenticated)
        {
            if (!authenticated)
            {
                yield return Reject(cmd?.CorrelationId ?? "", cmd?.ClientOrderId ?? "", "UNAUTHENTICATED", "Auth required");
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
                yield return new FabricMessage { OrderEvent = prior };
                yield break;
            }

            if (_config.MaxPositionSize > 0 && cmd.Quantity > _config.MaxPositionSize)
            {
                var rejected = new OrderEvent
                {
                    ClientOrderId = cmd.ClientOrderId,
                    State = OrderState.Rejected,
                    RejectionReason = $"max_position_size:{_config.MaxPositionSize}",
                    Instrument = cmd.Instrument,
                    Action = cmd.Action,
                    CorrelationId = cmd.CorrelationId ?? "",
                    TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                };
                _idempotency.Remember(cmd.ClientOrderId, rejected);
                yield return new FabricMessage { OrderEvent = rejected };
                yield break;
            }

            foreach (var evt in _gateway.PlaceOrder(cmd))
            {
                _idempotency.Remember(cmd.ClientOrderId, evt);
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

            foreach (var evt in _gateway.CancelOrder(cmd ?? new CancelOrderCommand()))
                yield return new FabricMessage { OrderEvent = evt };
        }

        private IEnumerable<FabricMessage> HandleFlatten(FlattenCommand cmd, bool authenticated)
        {
            if (!authenticated)
            {
                yield return Reject(cmd?.CorrelationId ?? "", "", "UNAUTHENTICATED", "Auth required");
                yield break;
            }

            foreach (var evt in _gateway.Flatten(cmd ?? new FlattenCommand()))
                yield return new FabricMessage { OrderEvent = evt };
        }

        private void ApplyDisconnectPolicy(string reason)
        {
            _safeMode.EnterSafe(reason);
            PublishOrderEvents(_gateway.CancelNonProtected(reason));
            PublishAlert(new SafetyAlert
            {
                AlertType = SafetyAlertType.SafeModeEntered,
                Severity = SafetySeverity.Critical,
                Message = $"Disconnect policy applied: {reason}",
                RecommendedAction = "cancel_non_protected",
                TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                CorrelationId = Guid.NewGuid().ToString("D"),
            });
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

        private FabricMessage Reject(string correlationId, string clientOrderId, string code, string message)
        {
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
