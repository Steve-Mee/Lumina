// ============================================================
// LUMINA — NT8 Account order gateway (PR-F)
// Real Sim101 / Account place-cancel-fills. Fail-closed if unbound.
// Capital preservation: REAL accounts require separate promotion ADR.
// ============================================================

#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Lumina.Execution.Fabric.Execution;
using Lumina.Execution.V1;
using OrderAction = Lumina.Execution.V1.OrderAction;
using OrderType = Lumina.Execution.V1.OrderType;
using OrderState = Lumina.Execution.V1.OrderState;
#if !FABRIC_STANDALONE
using NinjaTrader.Cbi;
using NinjaTrader.Core;
using NtOrderAction = NinjaTrader.Cbi.OrderAction;
using NtOrderType = NinjaTrader.Cbi.OrderType;
using NtOrderState = NinjaTrader.Cbi.OrderState;
using NtTimeInForce = NinjaTrader.Cbi.TimeInForce;
#endif
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
    /// <summary>
    /// Live NinjaTrader Account gateway. Bound to Sim101 (or configured name) for SIM learning.
    /// Emits async OrderEvents via <see cref="IOrderEventSource"/> for fills/cancels.
    /// </summary>
    public sealed class NtAccountOrderGateway : IOrderGateway, IOrderEventSource, IDisposable
    {
        private readonly object _gate = new object();
        private readonly Action<string>? _log;
        private readonly ConcurrentDictionary<string, bool> _protectedByClient =
            new ConcurrentDictionary<string, bool>(StringComparer.Ordinal);
        private readonly ConcurrentDictionary<string, string> _clientByNtOrderId =
            new ConcurrentDictionary<string, string>(StringComparer.Ordinal);
        private readonly ConcurrentDictionary<string, string> _ntByClientOrderId =
            new ConcurrentDictionary<string, string>(StringComparer.Ordinal);
        private string _accountName;
#if !FABRIC_STANDALONE
        private Account? _account;
#endif
        private bool _disposed;

        public NtAccountOrderGateway(string accountName = "Sim101", Action<string>? log = null)
        {
            _accountName = string.IsNullOrWhiteSpace(accountName) ? "Sim101" : accountName.Trim();
            _log = log;
        }

        public string AccountName
        {
            get { lock (_gate) return _accountName; }
        }

        public string GatewayKind => "nt";

        public bool IsBound
        {
            get
            {
#if FABRIC_STANDALONE
                return false;
#else
                lock (_gate) return _account != null;
#endif
            }
        }

        public event Action<IReadOnlyList<OrderEvent>>? OrderEventsProduced;
        public event Action<IReadOnlyList<PositionUpdate>>? PositionUpdatesProduced;

#if FABRIC_STANDALONE
        public bool TryBindFromNtAccounts()
        {
            Log("FATAL: FABRIC_STANDALONE build — cannot bind NT Account");
            return false;
        }

        public void BindAccount(object account, string? accountName = null)
        {
            throw new InvalidOperationException("FABRIC_STANDALONE: NtAccountOrderGateway cannot bind");
        }
#else
        /// <summary>Resolve Account by name from Account.All and subscribe to updates.</summary>
        public bool TryBindFromNtAccounts()
        {
            lock (_gate)
            {
                if (_account != null)
                    return true;

                Account? found = null;
                var wanted = _accountName;
                try
                {
                    foreach (Account a in Account.All)
                    {
                        if (a == null) continue;
                        var name = a.Name ?? "";
                        if (string.Equals(name, wanted, StringComparison.OrdinalIgnoreCase))
                        {
                            found = a;
                            break;
                        }
                    }

                    // Prefer any Sim* if exact name missing (operator renames)
                    if (found == null && wanted.StartsWith("Sim", StringComparison.OrdinalIgnoreCase))
                    {
                        foreach (Account a in Account.All)
                        {
                            if (a?.Name != null &&
                                a.Name.StartsWith("Sim", StringComparison.OrdinalIgnoreCase))
                            {
                                found = a;
                                Log($"account '{wanted}' not found — using '{a.Name}'");
                                break;
                            }
                        }
                    }
                }
                catch (Exception ex)
                {
                    Log("Account.All scan failed: " + ex.Message);
                    return false;
                }

                if (found == null)
                {
                    Log("FATAL: no NT Account matching '" + wanted + "'. Connect a SIM account (Sim101) in Control Center.");
                    return false;
                }

                return BindAccountInternal(found);
            }
        }

        public void BindAccount(object account, string? accountName = null)
        {
            if (account is not Account acct)
                throw new ArgumentException("Expected NinjaTrader.Cbi.Account", nameof(account));
            lock (_gate)
            {
                if (!string.IsNullOrWhiteSpace(accountName))
                    _accountName = accountName!.Trim();
                BindAccountInternal(acct);
            }
        }

        private bool BindAccountInternal(Account account)
        {
            UnhookUnlocked();
            _account = account ?? throw new ArgumentNullException(nameof(account));
            _accountName = string.IsNullOrWhiteSpace(account.Name) ? _accountName : account.Name;
            try
            {
                _account.OrderUpdate += OnOrderUpdate;
                _account.ExecutionUpdate += OnExecutionUpdate;
                _account.PositionUpdate += OnPositionUpdate;
            }
            catch (Exception ex)
            {
                Log("Subscribe account events failed: " + ex.Message);
                _account = null;
                return false;
            }

            Log("Bound NT Account='" + _accountName + "' connection=" + (_account.Connection?.Options?.Name ?? "?"));
            return true;
        }

        private void UnhookUnlocked()
        {
            if (_account == null)
                return;
            try { _account.OrderUpdate -= OnOrderUpdate; } catch { /* ignore */ }
            try { _account.ExecutionUpdate -= OnExecutionUpdate; } catch { /* ignore */ }
            try { _account.PositionUpdate -= OnPositionUpdate; } catch { /* ignore */ }
        }
#endif

        public void Unbind()
        {
            lock (_gate)
            {
#if !FABRIC_STANDALONE
                UnhookUnlocked();
                _account = null;
#endif
            }
        }

        public AccountMetrics GetAccountMetrics()
        {
#if FABRIC_STANDALONE
            return EmptyMetrics();
#else
            Account? acct;
            lock (_gate) acct = _account;
            if (acct == null)
                return EmptyMetrics();

            try
            {
                double cash = GetAccountItem(acct, AccountItem.CashValue);
                double nl = GetAccountItem(acct, AccountItem.NetLiquidation);
                double realized = GetAccountItem(acct, AccountItem.RealizedProfitLoss);
                double buying = GetAccountItem(acct, AccountItem.BuyingPower);
                if (nl <= 0 && cash > 0)
                    nl = cash;
                return new AccountMetrics
                {
                    AccountName = acct.Name ?? AccountName,
                    Currency = "USD",
                    Balance = cash,
                    Equity = nl > 0 ? nl : cash,
                    AvailableMargin = buying > 0 ? buying : Math.Max(0, cash),
                    RealizedPnlToday = realized,
                };
            }
            catch (Exception ex)
            {
                Log("GetAccountMetrics: " + ex.Message);
                return EmptyMetrics();
            }
#endif
        }

        public IReadOnlyList<PositionUpdate> GetPositions()
        {
#if FABRIC_STANDALONE
            return Array.Empty<PositionUpdate>();
#else
            Account? acct;
            lock (_gate) acct = _account;
            if (acct == null)
                return Array.Empty<PositionUpdate>();

            var list = new List<PositionUpdate>();
            try
            {
                foreach (Position p in acct.Positions)
                {
                    if (p == null || p.MarketPosition == MarketPosition.Flat || p.Quantity == 0)
                        continue;
                    var inst = p.Instrument?.FullName ?? p.Instrument?.MasterInstrument?.Name ?? "";
                    list.Add(new PositionUpdate
                    {
                        Instrument = inst,
                        Quantity = Math.Abs(p.Quantity),
                        AvgPrice = p.AveragePrice,
                        Side = p.MarketPosition == MarketPosition.Short ? "SHORT" : "LONG",
                        TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                    });
                }
            }
            catch (Exception ex)
            {
                Log("GetPositions: " + ex.Message);
            }
            return list;
#endif
        }

        public IReadOnlyList<WorkingOrder> GetWorkingOrders()
        {
#if FABRIC_STANDALONE
            return Array.Empty<WorkingOrder>();
#else
            Account? acct;
            lock (_gate) acct = _account;
            if (acct == null)
                return Array.Empty<WorkingOrder>();

            var list = new List<WorkingOrder>();
            try
            {
                foreach (Order o in acct.Orders)
                {
                    if (o == null || !IsWorkingState(o.OrderState))
                        continue;
                    var clientId = ResolveClientId(o);
                    list.Add(new WorkingOrder
                    {
                        ClientOrderId = clientId,
                        NtOrderId = o.OrderId ?? o.Id.ToString(CultureInfo.InvariantCulture),
                        Instrument = o.Instrument?.FullName ?? "",
                        Action = MapActionOut(o.OrderAction),
                        Quantity = o.Quantity,
                        FilledQty = o.Filled,
                        OrderType = MapOrderTypeOut(o.OrderType),
                        Price = o.LimitPrice,
                        StopPrice = o.StopPrice,
                        State = MapOrderStateOut(o.OrderState),
                        Protected = _protectedByClient.TryGetValue(clientId, out var prot) && prot,
                    });
                }
            }
            catch (Exception ex)
            {
                Log("GetWorkingOrders: " + ex.Message);
            }
            return list;
#endif
        }

        public IReadOnlyList<OrderEvent> PlaceOrder(PlaceOrderCommand command)
        {
#if FABRIC_STANDALONE
            return new[] { Reject(command, "nt_standalone_build") };
#else
            if (command == null)
                return new[] { Reject(null, "null_command") };

            Account? acct;
            lock (_gate) acct = _account;
            if (acct == null)
                return new[] { Reject(command, "nt_account_not_bound") };

            if (command.Quantity <= 0 || command.Action == OrderAction.Unspecified ||
                string.IsNullOrWhiteSpace(command.Instrument))
            {
                return new[] { Reject(command, "invalid_order_fields") };
            }

            // REAL capital hard gate: only Sim* accounts until promotion ADR.
            var acctName = acct.Name ?? "";
            var mode = (command.ModeContext ?? "").Trim().ToLowerInvariant();
            if (mode == "real" && !IsSimAccountName(acctName))
            {
                return new[] { Reject(command, "real_account_blocked_pending_promotion_adr") };
            }
            if (!IsSimAccountName(acctName) && mode != "real")
            {
                // Still allow non-sim only when explicitly real+promoted later; for now fail-closed.
                Log("Reject place on non-SIM account '" + acctName + "' (PR-F SIM-only)");
                return new[] { Reject(command, "only_sim_accounts_allowed") };
            }

            Instrument? instrument;
            try
            {
                instrument = ResolveInstrument(command.Instrument);
            }
            catch (Exception ex)
            {
                return new[] { Reject(command, "instrument_resolve_error:" + ex.Message) };
            }

            if (instrument == null)
                return new[] { Reject(command, "instrument_not_found:" + command.Instrument) };

            var ntAction = MapActionIn(command.Action);
            var ntType = MapOrderTypeIn(command.OrderType);
            var limit = command.Price > 0 ? command.Price : 0.0;
            var stop = command.StopPrice > 0 ? command.StopPrice : 0.0;
            var clientId = command.ClientOrderId ?? "";
            var signal = string.IsNullOrWhiteSpace(clientId) ? "LUMINA" : ("LUMINA|" + clientId);

            if (command.Protected && !string.IsNullOrEmpty(clientId))
                _protectedByClient[clientId] = true;

            try
            {
                Order order = acct.CreateOrder(
                    instrument,
                    ntAction,
                    ntType,
                    OrderEntry.Automated,
                    NtTimeInForce.Day,
                    command.Quantity,
                    limit,
                    stop,
                    string.Empty, // oco
                    signal,
                    Globals.MaxDate,
                    null);

                if (!string.IsNullOrEmpty(clientId))
                {
                    try { order.Name = signal; } catch { /* ignore */ }
                    try { order.ClientId = StableClientId(clientId); } catch { /* ignore */ }
                }

                acct.Submit(new[] { order });

                var ntId = order.OrderId ?? order.Id.ToString(CultureInfo.InvariantCulture);
                if (!string.IsNullOrEmpty(clientId) && !string.IsNullOrEmpty(ntId))
                {
                    _ntByClientOrderId[clientId] = ntId;
                    _clientByNtOrderId[ntId] = clientId;
                }

                var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
                var submitted = new OrderEvent
                {
                    ClientOrderId = clientId,
                    NtOrderId = ntId,
                    State = MapOrderStateOut(order.OrderState),
                    Instrument = instrument.FullName ?? command.Instrument,
                    Action = command.Action,
                    LeavesQty = Math.Max(0, command.Quantity - order.Filled),
                    CorrelationId = command.CorrelationId ?? "",
                    TimestampUnixMs = now,
                };
                // If already working/filled synchronously, map accurately.
                if (order.OrderState == NtOrderState.Filled)
                {
                    submitted.State = OrderState.Filled;
                    submitted.FilledQty = order.Filled;
                    submitted.AvgFillPrice = order.AverageFillPrice;
                    submitted.LeavesQty = 0;
                }
                else if (IsWorkingState(order.OrderState))
                {
                    submitted.State = OrderState.Working;
                }
                else if (order.OrderState == NtOrderState.Rejected)
                {
                    submitted.State = OrderState.Rejected;
                    submitted.RejectionReason = "nt_rejected";
                }
                else
                {
                    submitted.State = OrderState.Submitted;
                }

                Log($"PlaceOrder client={clientId} nt={ntId} {command.Action} {command.Quantity}x {instrument.FullName} state={order.OrderState}");
                return new[] { submitted };
            }
            catch (Exception ex)
            {
                Log("PlaceOrder exception: " + ex.Message);
                return new[] { Reject(command, "nt_submit_error:" + ex.Message) };
            }
#endif
        }

        public IReadOnlyList<OrderEvent> CancelOrder(CancelOrderCommand command)
        {
#if FABRIC_STANDALONE
            return new[] { RejectCancel(command, "nt_standalone_build") };
#else
            Account? acct;
            lock (_gate) acct = _account;
            if (acct == null)
                return new[] { RejectCancel(command, "nt_account_not_bound") };

            try
            {
                var target = FindOrder(acct, command?.ClientOrderId, command?.NtOrderId);
                if (target == null)
                    return new[] { RejectCancel(command, "order_not_found") };

                acct.Cancel(new[] { target });
                var clientId = ResolveClientId(target);
                return new[]
                {
                    new OrderEvent
                    {
                        ClientOrderId = clientId,
                        NtOrderId = target.OrderId ?? "",
                        State = OrderState.Cancelled,
                        Instrument = target.Instrument?.FullName ?? "",
                        Action = MapActionOut(target.OrderAction),
                        CorrelationId = command?.CorrelationId ?? "",
                        TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                        RejectionReason = "cancel_submitted",
                    },
                };
            }
            catch (Exception ex)
            {
                return new[] { RejectCancel(command, "nt_cancel_error:" + ex.Message) };
            }
#endif
        }

        public IReadOnlyList<OrderEvent> ModifyOrder(ModifyOrderCommand command)
        {
#if FABRIC_STANDALONE
            return new[] { RejectModify(command, "nt_standalone_build") };
#else
            Account? acct;
            lock (_gate) acct = _account;
            if (acct == null)
                return new[] { RejectModify(command, "nt_account_not_bound") };

            try
            {
                var target = FindOrder(acct, command?.ClientOrderId, command?.NtOrderId);
                if (target == null)
                    return new[] { RejectModify(command, "order_not_found") };

                if (command!.Quantity > 0)
                    target.QuantityChanged = command.Quantity;
                if (command.Price > 0)
                    target.LimitPriceChanged = command.Price;
                if (command.StopPrice > 0)
                    target.StopPriceChanged = command.StopPrice;

                acct.Change(new[] { target });
                var clientId = ResolveClientId(target);
                return new[]
                {
                    new OrderEvent
                    {
                        ClientOrderId = clientId,
                        NtOrderId = target.OrderId ?? "",
                        State = OrderState.Working,
                        Instrument = target.Instrument?.FullName ?? "",
                        Action = MapActionOut(target.OrderAction),
                        LeavesQty = Math.Max(0, target.Quantity - target.Filled),
                        CorrelationId = command.CorrelationId ?? "",
                        TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                        RejectionReason = "modified",
                    },
                };
            }
            catch (Exception ex)
            {
                return new[] { RejectModify(command, "nt_modify_error:" + ex.Message) };
            }
#endif
        }

        public IReadOnlyList<OrderEvent> Flatten(FlattenCommand command)
        {
#if FABRIC_STANDALONE
            return new[] { Reject(new PlaceOrderCommand { ClientOrderId = "flatten", CorrelationId = command?.CorrelationId }, "nt_standalone_build") };
#else
            Account? acct;
            lock (_gate) acct = _account;
            if (acct == null)
            {
                return new[]
                {
                    Reject(new PlaceOrderCommand
                    {
                        ClientOrderId = "flatten",
                        CorrelationId = command?.CorrelationId,
                        Instrument = command?.Instrument,
                    }, "nt_account_not_bound"),
                };
            }

            var events = new List<OrderEvent>();
            var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            try
            {
                var filter = (command?.Instrument ?? "").Trim();
                if (string.IsNullOrEmpty(filter))
                {
                    Account.FlattenEverything();
                    events.Add(new OrderEvent
                    {
                        ClientOrderId = "flatten",
                        NtOrderId = "flatten-all",
                        State = OrderState.Submitted,
                        CorrelationId = command?.CorrelationId ?? "",
                        TimestampUnixMs = now,
                        RejectionReason = "flatten_everything",
                    });
                }
                else
                {
                    var inst = ResolveInstrument(filter);
                    if (inst == null)
                    {
                        return new[]
                        {
                            Reject(new PlaceOrderCommand
                            {
                                ClientOrderId = "flatten",
                                CorrelationId = command?.CorrelationId,
                                Instrument = filter,
                            }, "instrument_not_found"),
                        };
                    }

                    acct.Flatten(new[] { inst });
                    events.Add(new OrderEvent
                    {
                        ClientOrderId = "flatten",
                        NtOrderId = "flatten-" + (inst.FullName ?? filter),
                        State = OrderState.Submitted,
                        Instrument = inst.FullName ?? filter,
                        CorrelationId = command?.CorrelationId ?? "",
                        TimestampUnixMs = now,
                        RejectionReason = "flatten_instrument",
                    });
                }

                events.AddRange(CancelNonProtected("flatten"));
            }
            catch (Exception ex)
            {
                Log("Flatten error: " + ex.Message);
                events.Add(Reject(new PlaceOrderCommand
                {
                    ClientOrderId = "flatten",
                    CorrelationId = command?.CorrelationId,
                }, "nt_flatten_error:" + ex.Message));
            }

            return events;
#endif
        }

        public IReadOnlyList<OrderEvent> CancelNonProtected(string reason)
        {
#if FABRIC_STANDALONE
            return Array.Empty<OrderEvent>();
#else
            Account? acct;
            lock (_gate) acct = _account;
            if (acct == null)
                return Array.Empty<OrderEvent>();

            var toCancel = new List<Order>();
            var events = new List<OrderEvent>();
            var now = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
            try
            {
                foreach (Order o in acct.Orders)
                {
                    if (o == null || !IsWorkingState(o.OrderState))
                        continue;
                    var clientId = ResolveClientId(o);
                    if (_protectedByClient.TryGetValue(clientId, out var prot) && prot)
                        continue;
                    toCancel.Add(o);
                }

                if (toCancel.Count > 0)
                    acct.Cancel(toCancel);

                foreach (var o in toCancel)
                {
                    var clientId = ResolveClientId(o);
                    events.Add(new OrderEvent
                    {
                        ClientOrderId = clientId,
                        NtOrderId = o.OrderId ?? "",
                        State = OrderState.Cancelled,
                        Instrument = o.Instrument?.FullName ?? "",
                        Action = MapActionOut(o.OrderAction),
                        RejectionReason = reason ?? "cancel_non_protected",
                        TimestampUnixMs = now,
                    });
                }
            }
            catch (Exception ex)
            {
                Log("CancelNonProtected: " + ex.Message);
            }

            return events;
#endif
        }

#if !FABRIC_STANDALONE
        private void OnOrderUpdate(object? sender, OrderEventArgs e)
        {
            try
            {
                var order = e?.Order;
                if (order == null)
                    return;

                var clientId = ResolveClientId(order);
                var ntId = order.OrderId ?? e.OrderId ?? "";
                if (!string.IsNullOrEmpty(clientId) && !string.IsNullOrEmpty(ntId))
                {
                    _ntByClientOrderId[clientId] = ntId;
                    _clientByNtOrderId[ntId] = clientId;
                }

                var evt = new OrderEvent
                {
                    ClientOrderId = clientId,
                    NtOrderId = ntId,
                    State = MapOrderStateOut(e.OrderState),
                    Instrument = order.Instrument?.FullName ?? "",
                    Action = MapActionOut(order.OrderAction),
                    FilledQty = e.Filled,
                    AvgFillPrice = e.AverageFillPrice,
                    LeavesQty = Math.Max(0, e.Quantity - e.Filled),
                    TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                    RejectionReason = e.Error != ErrorCode.NoError ? (e.Comment ?? e.Error.ToString()) : "",
                };

                if (e.OrderState == NtOrderState.Rejected && string.IsNullOrEmpty(evt.RejectionReason))
                    evt.RejectionReason = "nt_rejected";

                Emit(new[] { evt });
            }
            catch (Exception ex)
            {
                Log("OnOrderUpdate: " + ex.Message);
            }
        }

        private void OnExecutionUpdate(object? sender, ExecutionEventArgs e)
        {
            try
            {
                // Fills are also covered by OrderUpdate; emit partial fill signal for stream consumers.
                if (e == null || e.Quantity <= 0)
                    return;
                var orderId = e.OrderId ?? "";
                _clientByNtOrderId.TryGetValue(orderId, out var clientId);
                var evt = new OrderEvent
                {
                    ClientOrderId = clientId ?? "",
                    NtOrderId = orderId,
                    State = OrderState.PartiallyFilled,
                    Instrument = e.Execution?.Instrument?.FullName ?? "",
                    FilledQty = e.Quantity,
                    AvgFillPrice = e.Price,
                    TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                    RejectionReason = "execution",
                };
                Emit(new[] { evt });
            }
            catch (Exception ex)
            {
                Log("OnExecutionUpdate: " + ex.Message);
            }
        }

        private void OnPositionUpdate(object? sender, PositionEventArgs e)
        {
            try
            {
                var pos = e?.Position;
                if (pos == null)
                    return;
                var inst = pos.Instrument?.FullName ?? pos.Instrument?.MasterInstrument?.Name ?? "";
                var qty = Math.Abs(e.Quantity != 0 ? e.Quantity : pos.Quantity);
                var side = e.MarketPosition == MarketPosition.Short
                    ? "SHORT"
                    : (e.MarketPosition == MarketPosition.Long ? "LONG" : "FLAT");
                if (e.MarketPosition == MarketPosition.Flat || qty == 0)
                {
                    side = "FLAT";
                    qty = 0;
                }
                var update = new PositionUpdate
                {
                    Instrument = inst,
                    Quantity = qty,
                    AvgPrice = e.AveragePrice > 0 ? e.AveragePrice : pos.AveragePrice,
                    Side = side,
                    TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
                };
                try
                {
                    PositionUpdatesProduced?.Invoke(new[] { update });
                }
                catch (Exception ex)
                {
                    Log("PositionUpdatesProduced: " + ex.Message);
                }
            }
            catch (Exception ex)
            {
                Log("OnPositionUpdate: " + ex.Message);
            }
        }

        private Order? FindOrder(Account acct, string? clientOrderId, string? ntOrderId)
        {
            if (!string.IsNullOrWhiteSpace(ntOrderId))
            {
                foreach (Order o in acct.Orders)
                {
                    if (o == null) continue;
                    if (string.Equals(o.OrderId, ntOrderId, StringComparison.OrdinalIgnoreCase))
                        return o;
                    if (string.Equals(o.Id.ToString(CultureInfo.InvariantCulture), ntOrderId, StringComparison.Ordinal))
                        return o;
                }
            }

            if (!string.IsNullOrWhiteSpace(clientOrderId))
            {
                if (_ntByClientOrderId.TryGetValue(clientOrderId!, out var mappedNt))
                {
                    foreach (Order o in acct.Orders)
                    {
                        if (o != null && string.Equals(o.OrderId, mappedNt, StringComparison.OrdinalIgnoreCase))
                            return o;
                    }
                }

                var needle = "LUMINA|" + clientOrderId;
                foreach (Order o in acct.Orders)
                {
                    if (o == null) continue;
                    if (string.Equals(o.Name, needle, StringComparison.OrdinalIgnoreCase) ||
                        string.Equals(o.Name, clientOrderId, StringComparison.OrdinalIgnoreCase))
                        return o;
                    try
                    {
                        if (o.ClientId == StableClientId(clientOrderId!))
                            return o;
                    }
                    catch { /* ignore */ }
                }
            }

            return null;
        }

        private string ResolveClientId(Order order)
        {
            var ntId = order.OrderId ?? order.Id.ToString(CultureInfo.InvariantCulture);
            if (!string.IsNullOrEmpty(ntId) && _clientByNtOrderId.TryGetValue(ntId, out var mapped))
                return mapped;

            var name = order.Name ?? "";
            if (name.StartsWith("LUMINA|", StringComparison.OrdinalIgnoreCase))
                return name.Substring("LUMINA|".Length);

            try
            {
                if (order.ClientId != 0)
                {
                    // Reverse lookup not stored; keep name if present.
                }
            }
            catch { /* ignore */ }

            return name;
        }

        private static Instrument? ResolveInstrument(string instrumentName)
        {
            var raw = (instrumentName ?? "").Trim();
            if (string.IsNullOrEmpty(raw))
                return null;

            try
            {
                var inst = Instrument.GetInstrument(raw);
                if (inst != null && (!string.IsNullOrWhiteSpace(inst.FullName) || inst.MasterInstrument != null))
                    return inst;
            }
            catch { /* try next */ }

            try
            {
                var fuzzy = Instrument.GetInstrumentFuzzy(raw);
                if (fuzzy != null)
                    return fuzzy;
            }
            catch { /* ignore */ }

            // Root + quarterly expansion for "MES"
            var parts = raw.Split(new[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
            if (parts.Length == 1 && parts[0].Length <= 5)
            {
                var root = parts[0].ToUpperInvariant();
                int[] months = { 3, 6, 9, 12 };
                var now = DateTime.Now;
                for (var i = 0; i < 12; i++)
                {
                    var dt = new DateTime(now.Year, now.Month, 1).AddMonths(i);
                    if (Array.IndexOf(months, dt.Month) < 0)
                        continue;
                    if (dt.AddDays(45) < now)
                        continue;
                    var full = $"{root} {dt.Month:D2}-{(dt.Year % 100):D2}";
                    try
                    {
                        var inst = Instrument.GetInstrument(full);
                        if (inst != null)
                            return inst;
                    }
                    catch { /* continue */ }
                }
            }

            return null;
        }

        private static double GetAccountItem(Account acct, AccountItem item)
        {
            try
            {
                var ev = acct.GetAccountItem(item, Currency.UsDollar);
                return ev?.Value ?? 0;
            }
            catch
            {
                return 0;
            }
        }

        private static bool IsWorkingState(NtOrderState state)
        {
            return state == NtOrderState.Working
                || state == NtOrderState.Accepted
                || state == NtOrderState.AcceptedByRisk
                || state == NtOrderState.Submitted
                || state == NtOrderState.TriggerPending
                || state == NtOrderState.ChangePending
                || state == NtOrderState.CancelPending
                || state == NtOrderState.PartFilled;
        }

        private static NtOrderAction MapActionIn(OrderAction action)
        {
            // Proto has Buy/Sell only; map to NT Buy/Sell (Sell covers short for futures).
            switch (action)
            {
                case OrderAction.Buy: return NtOrderAction.Buy;
                case OrderAction.Sell: return NtOrderAction.Sell;
                default: return NtOrderAction.Buy;
            }
        }

        private static OrderAction MapActionOut(NtOrderAction action)
        {
            switch (action)
            {
                case NtOrderAction.Buy:
                case NtOrderAction.BuyToCover:
                    return OrderAction.Buy;
                case NtOrderAction.Sell:
                case NtOrderAction.SellShort:
                    return OrderAction.Sell;
                default:
                    return OrderAction.Unspecified;
            }
        }

        private static NtOrderType MapOrderTypeIn(OrderType type)
        {
            switch (type)
            {
                case OrderType.Limit: return NtOrderType.Limit;
                case OrderType.Stop: return NtOrderType.StopMarket;
                case OrderType.StopLimit: return NtOrderType.StopLimit;
                case OrderType.Market: return NtOrderType.Market;
                default: return NtOrderType.Market;
            }
        }

        private static OrderType MapOrderTypeOut(NtOrderType type)
        {
            switch (type)
            {
                case NtOrderType.Limit: return OrderType.Limit;
                case NtOrderType.StopMarket: return OrderType.Stop;
                case NtOrderType.StopLimit: return OrderType.StopLimit;
                case NtOrderType.Market: return OrderType.Market;
                default: return OrderType.Unspecified;
            }
        }

        private static OrderState MapOrderStateOut(NtOrderState state)
        {
            switch (state)
            {
                case NtOrderState.Filled: return OrderState.Filled;
                case NtOrderState.PartFilled: return OrderState.PartiallyFilled;
                case NtOrderState.Cancelled: return OrderState.Cancelled;
                case NtOrderState.Rejected: return OrderState.Rejected;
                case NtOrderState.Working:
                case NtOrderState.Accepted:
                case NtOrderState.AcceptedByRisk:
                case NtOrderState.CancelSubmitted:
                case NtOrderState.ChangeSubmitted:
                case NtOrderState.TriggerPending:
                case NtOrderState.ChangePending:
                case NtOrderState.CancelPending:
                    return OrderState.Working;
                case NtOrderState.Submitted:
                case NtOrderState.Initialized:
                    return OrderState.Submitted;
                default:
                    return OrderState.Unspecified;
            }
        }
#endif

        private static bool IsSimAccountName(string name)
        {
            if (string.IsNullOrWhiteSpace(name))
                return false;
            return name.StartsWith("Sim", StringComparison.OrdinalIgnoreCase)
                || name.IndexOf("Sim101", StringComparison.OrdinalIgnoreCase) >= 0
                || name.IndexOf("Playback", StringComparison.OrdinalIgnoreCase) >= 0
                || name.IndexOf("Backtest", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private static int StableClientId(string clientOrderId)
        {
            // NT ClientId is int — stable hash, non-zero.
            unchecked
            {
                var h = clientOrderId.GetHashCode();
                if (h == 0) h = 1;
                return h;
            }
        }

        private AccountMetrics EmptyMetrics()
        {
            return new AccountMetrics
            {
                AccountName = AccountName,
                Currency = "USD",
                Balance = 0,
                Equity = 0,
            };
        }

        private static OrderEvent Reject(PlaceOrderCommand? command, string reason)
        {
            return new OrderEvent
            {
                ClientOrderId = command?.ClientOrderId ?? "",
                State = OrderState.Rejected,
                RejectionReason = reason,
                Instrument = command?.Instrument ?? "",
                Action = command?.Action ?? OrderAction.Unspecified,
                CorrelationId = command?.CorrelationId ?? "",
                TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            };
        }

        private static OrderEvent RejectCancel(CancelOrderCommand? command, string reason)
        {
            return new OrderEvent
            {
                ClientOrderId = command?.ClientOrderId ?? "",
                NtOrderId = command?.NtOrderId ?? "",
                State = OrderState.Rejected,
                RejectionReason = reason,
                CorrelationId = command?.CorrelationId ?? "",
                TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            };
        }

        private static OrderEvent RejectModify(ModifyOrderCommand? command, string reason)
        {
            return new OrderEvent
            {
                ClientOrderId = command?.ClientOrderId ?? "",
                NtOrderId = command?.NtOrderId ?? "",
                State = OrderState.Rejected,
                RejectionReason = reason,
                CorrelationId = command?.CorrelationId ?? "",
                TimestampUnixMs = DateTimeOffset.UtcNow.ToUnixTimeMilliseconds(),
            };
        }

        private void Emit(IReadOnlyList<OrderEvent> events)
        {
            try
            {
                OrderEventsProduced?.Invoke(events);
            }
            catch (Exception ex)
            {
                Log("Emit events failed: " + ex.Message);
            }
        }

        private void Log(string message) => _log?.Invoke("[NtGateway] " + message);

        public void Dispose()
        {
            if (_disposed)
                return;
            _disposed = true;
            Unbind();
        }
    }
}
