from google.protobuf.internal import containers as _containers
from google.protobuf.internal import enum_type_wrapper as _enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class SafeModeState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SAFE_MODE_STATE_UNSPECIFIED: _ClassVar[SafeModeState]
    SAFE_MODE_STATE_NORMAL: _ClassVar[SafeModeState]
    SAFE_MODE_STATE_SAFE: _ClassVar[SafeModeState]
    SAFE_MODE_STATE_FULL_SAFE: _ClassVar[SafeModeState]

class SafetyAlertType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SAFETY_ALERT_TYPE_UNSPECIFIED: _ClassVar[SafetyAlertType]
    SAFETY_ALERT_TYPE_HEARTBEAT_TIMEOUT: _ClassVar[SafetyAlertType]
    SAFETY_ALERT_TYPE_ORDER_REJECTED: _ClassVar[SafetyAlertType]
    SAFETY_ALERT_TYPE_POSITION_LIMIT_BREACHED: _ClassVar[SafetyAlertType]
    SAFETY_ALERT_TYPE_SAFE_MODE_ENTERED: _ClassVar[SafetyAlertType]
    SAFETY_ALERT_TYPE_FLATTEN_ISSUED: _ClassVar[SafetyAlertType]
    SAFETY_ALERT_TYPE_NT_CONNECTION_LOST: _ClassVar[SafetyAlertType]
    SAFETY_ALERT_TYPE_AUTH_FAILED: _ClassVar[SafetyAlertType]

class SafetySeverity(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    SAFETY_SEVERITY_UNSPECIFIED: _ClassVar[SafetySeverity]
    SAFETY_SEVERITY_INFO: _ClassVar[SafetySeverity]
    SAFETY_SEVERITY_WARNING: _ClassVar[SafetySeverity]
    SAFETY_SEVERITY_CRITICAL: _ClassVar[SafetySeverity]

class OrderAction(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ORDER_ACTION_UNSPECIFIED: _ClassVar[OrderAction]
    ORDER_ACTION_BUY: _ClassVar[OrderAction]
    ORDER_ACTION_SELL: _ClassVar[OrderAction]

class OrderType(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ORDER_TYPE_UNSPECIFIED: _ClassVar[OrderType]
    ORDER_TYPE_MARKET: _ClassVar[OrderType]
    ORDER_TYPE_LIMIT: _ClassVar[OrderType]
    ORDER_TYPE_STOP: _ClassVar[OrderType]
    ORDER_TYPE_STOP_LIMIT: _ClassVar[OrderType]

class TimeInForce(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    TIME_IN_FORCE_UNSPECIFIED: _ClassVar[TimeInForce]
    TIME_IN_FORCE_DAY: _ClassVar[TimeInForce]
    TIME_IN_FORCE_GTC: _ClassVar[TimeInForce]
    TIME_IN_FORCE_IOC: _ClassVar[TimeInForce]
    TIME_IN_FORCE_FOK: _ClassVar[TimeInForce]

class OrderState(int, metaclass=_enum_type_wrapper.EnumTypeWrapper):
    __slots__ = ()
    ORDER_STATE_UNSPECIFIED: _ClassVar[OrderState]
    ORDER_STATE_SUBMITTED: _ClassVar[OrderState]
    ORDER_STATE_WORKING: _ClassVar[OrderState]
    ORDER_STATE_PARTIALLY_FILLED: _ClassVar[OrderState]
    ORDER_STATE_FILLED: _ClassVar[OrderState]
    ORDER_STATE_CANCELLED: _ClassVar[OrderState]
    ORDER_STATE_REJECTED: _ClassVar[OrderState]
SAFE_MODE_STATE_UNSPECIFIED: SafeModeState
SAFE_MODE_STATE_NORMAL: SafeModeState
SAFE_MODE_STATE_SAFE: SafeModeState
SAFE_MODE_STATE_FULL_SAFE: SafeModeState
SAFETY_ALERT_TYPE_UNSPECIFIED: SafetyAlertType
SAFETY_ALERT_TYPE_HEARTBEAT_TIMEOUT: SafetyAlertType
SAFETY_ALERT_TYPE_ORDER_REJECTED: SafetyAlertType
SAFETY_ALERT_TYPE_POSITION_LIMIT_BREACHED: SafetyAlertType
SAFETY_ALERT_TYPE_SAFE_MODE_ENTERED: SafetyAlertType
SAFETY_ALERT_TYPE_FLATTEN_ISSUED: SafetyAlertType
SAFETY_ALERT_TYPE_NT_CONNECTION_LOST: SafetyAlertType
SAFETY_ALERT_TYPE_AUTH_FAILED: SafetyAlertType
SAFETY_SEVERITY_UNSPECIFIED: SafetySeverity
SAFETY_SEVERITY_INFO: SafetySeverity
SAFETY_SEVERITY_WARNING: SafetySeverity
SAFETY_SEVERITY_CRITICAL: SafetySeverity
ORDER_ACTION_UNSPECIFIED: OrderAction
ORDER_ACTION_BUY: OrderAction
ORDER_ACTION_SELL: OrderAction
ORDER_TYPE_UNSPECIFIED: OrderType
ORDER_TYPE_MARKET: OrderType
ORDER_TYPE_LIMIT: OrderType
ORDER_TYPE_STOP: OrderType
ORDER_TYPE_STOP_LIMIT: OrderType
TIME_IN_FORCE_UNSPECIFIED: TimeInForce
TIME_IN_FORCE_DAY: TimeInForce
TIME_IN_FORCE_GTC: TimeInForce
TIME_IN_FORCE_IOC: TimeInForce
TIME_IN_FORCE_FOK: TimeInForce
ORDER_STATE_UNSPECIFIED: OrderState
ORDER_STATE_SUBMITTED: OrderState
ORDER_STATE_WORKING: OrderState
ORDER_STATE_PARTIALLY_FILLED: OrderState
ORDER_STATE_FILLED: OrderState
ORDER_STATE_CANCELLED: OrderState
ORDER_STATE_REJECTED: OrderState

class BrainMessage(_message.Message):
    __slots__ = ("heartbeat", "place_order", "cancel_order", "modify_order", "flatten", "subscribe_market_data", "unsubscribe_market_data", "auth_hello")
    HEARTBEAT_FIELD_NUMBER: _ClassVar[int]
    PLACE_ORDER_FIELD_NUMBER: _ClassVar[int]
    CANCEL_ORDER_FIELD_NUMBER: _ClassVar[int]
    MODIFY_ORDER_FIELD_NUMBER: _ClassVar[int]
    FLATTEN_FIELD_NUMBER: _ClassVar[int]
    SUBSCRIBE_MARKET_DATA_FIELD_NUMBER: _ClassVar[int]
    UNSUBSCRIBE_MARKET_DATA_FIELD_NUMBER: _ClassVar[int]
    AUTH_HELLO_FIELD_NUMBER: _ClassVar[int]
    heartbeat: Heartbeat
    place_order: PlaceOrderCommand
    cancel_order: CancelOrderCommand
    modify_order: ModifyOrderCommand
    flatten: FlattenCommand
    subscribe_market_data: SubscribeMarketData
    unsubscribe_market_data: UnsubscribeMarketData
    auth_hello: AuthHello
    def __init__(self, heartbeat: _Optional[_Union[Heartbeat, _Mapping]] = ..., place_order: _Optional[_Union[PlaceOrderCommand, _Mapping]] = ..., cancel_order: _Optional[_Union[CancelOrderCommand, _Mapping]] = ..., modify_order: _Optional[_Union[ModifyOrderCommand, _Mapping]] = ..., flatten: _Optional[_Union[FlattenCommand, _Mapping]] = ..., subscribe_market_data: _Optional[_Union[SubscribeMarketData, _Mapping]] = ..., unsubscribe_market_data: _Optional[_Union[UnsubscribeMarketData, _Mapping]] = ..., auth_hello: _Optional[_Union[AuthHello, _Mapping]] = ...) -> None: ...

class FabricMessage(_message.Message):
    __slots__ = ("heartbeat", "order_event", "position_update", "market_data", "state_sync", "safety_alert", "auth_result", "command_reject")
    HEARTBEAT_FIELD_NUMBER: _ClassVar[int]
    ORDER_EVENT_FIELD_NUMBER: _ClassVar[int]
    POSITION_UPDATE_FIELD_NUMBER: _ClassVar[int]
    MARKET_DATA_FIELD_NUMBER: _ClassVar[int]
    STATE_SYNC_FIELD_NUMBER: _ClassVar[int]
    SAFETY_ALERT_FIELD_NUMBER: _ClassVar[int]
    AUTH_RESULT_FIELD_NUMBER: _ClassVar[int]
    COMMAND_REJECT_FIELD_NUMBER: _ClassVar[int]
    heartbeat: Heartbeat
    order_event: OrderEvent
    position_update: PositionUpdate
    market_data: MarketDataUpdate
    state_sync: StateSyncResponse
    safety_alert: SafetyAlert
    auth_result: AuthResult
    command_reject: CommandReject
    def __init__(self, heartbeat: _Optional[_Union[Heartbeat, _Mapping]] = ..., order_event: _Optional[_Union[OrderEvent, _Mapping]] = ..., position_update: _Optional[_Union[PositionUpdate, _Mapping]] = ..., market_data: _Optional[_Union[MarketDataUpdate, _Mapping]] = ..., state_sync: _Optional[_Union[StateSyncResponse, _Mapping]] = ..., safety_alert: _Optional[_Union[SafetyAlert, _Mapping]] = ..., auth_result: _Optional[_Union[AuthResult, _Mapping]] = ..., command_reject: _Optional[_Union[CommandReject, _Mapping]] = ...) -> None: ...

class AuthHello(_message.Message):
    __slots__ = ("token", "client_name", "client_version", "mode_context")
    TOKEN_FIELD_NUMBER: _ClassVar[int]
    CLIENT_NAME_FIELD_NUMBER: _ClassVar[int]
    CLIENT_VERSION_FIELD_NUMBER: _ClassVar[int]
    MODE_CONTEXT_FIELD_NUMBER: _ClassVar[int]
    token: str
    client_name: str
    client_version: str
    mode_context: str
    def __init__(self, token: _Optional[str] = ..., client_name: _Optional[str] = ..., client_version: _Optional[str] = ..., mode_context: _Optional[str] = ...) -> None: ...

class AuthResult(_message.Message):
    __slots__ = ("ok", "session_id", "code", "message", "account_name")
    OK_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_NAME_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    session_id: str
    code: str
    message: str
    account_name: str
    def __init__(self, ok: bool = ..., session_id: _Optional[str] = ..., code: _Optional[str] = ..., message: _Optional[str] = ..., account_name: _Optional[str] = ...) -> None: ...

class Heartbeat(_message.Message):
    __slots__ = ("sequence_number", "timestamp_unix_ms", "brain_status", "last_known_state_hash", "fabric_safe_mode")
    SEQUENCE_NUMBER_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    BRAIN_STATUS_FIELD_NUMBER: _ClassVar[int]
    LAST_KNOWN_STATE_HASH_FIELD_NUMBER: _ClassVar[int]
    FABRIC_SAFE_MODE_FIELD_NUMBER: _ClassVar[int]
    sequence_number: int
    timestamp_unix_ms: int
    brain_status: str
    last_known_state_hash: str
    fabric_safe_mode: SafeModeState
    def __init__(self, sequence_number: _Optional[int] = ..., timestamp_unix_ms: _Optional[int] = ..., brain_status: _Optional[str] = ..., last_known_state_hash: _Optional[str] = ..., fabric_safe_mode: _Optional[_Union[SafeModeState, str]] = ...) -> None: ...

class SafetyAlert(_message.Message):
    __slots__ = ("alert_type", "severity", "message", "recommended_action", "timestamp_unix_ms", "correlation_id")
    ALERT_TYPE_FIELD_NUMBER: _ClassVar[int]
    SEVERITY_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    RECOMMENDED_ACTION_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    alert_type: SafetyAlertType
    severity: SafetySeverity
    message: str
    recommended_action: str
    timestamp_unix_ms: int
    correlation_id: str
    def __init__(self, alert_type: _Optional[_Union[SafetyAlertType, str]] = ..., severity: _Optional[_Union[SafetySeverity, str]] = ..., message: _Optional[str] = ..., recommended_action: _Optional[str] = ..., timestamp_unix_ms: _Optional[int] = ..., correlation_id: _Optional[str] = ...) -> None: ...

class PlaceOrderCommand(_message.Message):
    __slots__ = ("client_order_id", "instrument", "action", "quantity", "order_type", "price", "stop_price", "time_in_force", "reduce_only", "protected", "correlation_id", "mode_context")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    STOP_PRICE_FIELD_NUMBER: _ClassVar[int]
    TIME_IN_FORCE_FIELD_NUMBER: _ClassVar[int]
    REDUCE_ONLY_FIELD_NUMBER: _ClassVar[int]
    PROTECTED_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    MODE_CONTEXT_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    instrument: str
    action: OrderAction
    quantity: int
    order_type: OrderType
    price: float
    stop_price: float
    time_in_force: TimeInForce
    reduce_only: bool
    protected: bool
    correlation_id: str
    mode_context: str
    def __init__(self, client_order_id: _Optional[str] = ..., instrument: _Optional[str] = ..., action: _Optional[_Union[OrderAction, str]] = ..., quantity: _Optional[int] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., price: _Optional[float] = ..., stop_price: _Optional[float] = ..., time_in_force: _Optional[_Union[TimeInForce, str]] = ..., reduce_only: bool = ..., protected: bool = ..., correlation_id: _Optional[str] = ..., mode_context: _Optional[str] = ...) -> None: ...

class CancelOrderCommand(_message.Message):
    __slots__ = ("client_order_id", "nt_order_id", "correlation_id")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    NT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    nt_order_id: str
    correlation_id: str
    def __init__(self, client_order_id: _Optional[str] = ..., nt_order_id: _Optional[str] = ..., correlation_id: _Optional[str] = ...) -> None: ...

class ModifyOrderCommand(_message.Message):
    __slots__ = ("client_order_id", "nt_order_id", "quantity", "price", "stop_price", "correlation_id")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    NT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    STOP_PRICE_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    nt_order_id: str
    quantity: int
    price: float
    stop_price: float
    correlation_id: str
    def __init__(self, client_order_id: _Optional[str] = ..., nt_order_id: _Optional[str] = ..., quantity: _Optional[int] = ..., price: _Optional[float] = ..., stop_price: _Optional[float] = ..., correlation_id: _Optional[str] = ...) -> None: ...

class FlattenCommand(_message.Message):
    __slots__ = ("instrument", "correlation_id", "emergency")
    INSTRUMENT_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    EMERGENCY_FIELD_NUMBER: _ClassVar[int]
    instrument: str
    correlation_id: str
    emergency: bool
    def __init__(self, instrument: _Optional[str] = ..., correlation_id: _Optional[str] = ..., emergency: bool = ...) -> None: ...

class OrderEvent(_message.Message):
    __slots__ = ("client_order_id", "nt_order_id", "state", "filled_qty", "avg_fill_price", "timestamp_unix_ms", "rejection_reason", "instrument", "action", "leaves_qty", "correlation_id")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    NT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    FILLED_QTY_FIELD_NUMBER: _ClassVar[int]
    AVG_FILL_PRICE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    REJECTION_REASON_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    LEAVES_QTY_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    nt_order_id: str
    state: OrderState
    filled_qty: int
    avg_fill_price: float
    timestamp_unix_ms: int
    rejection_reason: str
    instrument: str
    action: OrderAction
    leaves_qty: int
    correlation_id: str
    def __init__(self, client_order_id: _Optional[str] = ..., nt_order_id: _Optional[str] = ..., state: _Optional[_Union[OrderState, str]] = ..., filled_qty: _Optional[int] = ..., avg_fill_price: _Optional[float] = ..., timestamp_unix_ms: _Optional[int] = ..., rejection_reason: _Optional[str] = ..., instrument: _Optional[str] = ..., action: _Optional[_Union[OrderAction, str]] = ..., leaves_qty: _Optional[int] = ..., correlation_id: _Optional[str] = ...) -> None: ...

class CommandReject(_message.Message):
    __slots__ = ("correlation_id", "client_order_id", "code", "message", "safe_mode")
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    SAFE_MODE_FIELD_NUMBER: _ClassVar[int]
    correlation_id: str
    client_order_id: str
    code: str
    message: str
    safe_mode: SafeModeState
    def __init__(self, correlation_id: _Optional[str] = ..., client_order_id: _Optional[str] = ..., code: _Optional[str] = ..., message: _Optional[str] = ..., safe_mode: _Optional[_Union[SafeModeState, str]] = ...) -> None: ...

class PositionUpdate(_message.Message):
    __slots__ = ("instrument", "quantity", "avg_price", "side", "timestamp_unix_ms")
    INSTRUMENT_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    AVG_PRICE_FIELD_NUMBER: _ClassVar[int]
    SIDE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    instrument: str
    quantity: int
    avg_price: float
    side: str
    timestamp_unix_ms: int
    def __init__(self, instrument: _Optional[str] = ..., quantity: _Optional[int] = ..., avg_price: _Optional[float] = ..., side: _Optional[str] = ..., timestamp_unix_ms: _Optional[int] = ...) -> None: ...

class WorkingOrder(_message.Message):
    __slots__ = ("client_order_id", "nt_order_id", "instrument", "action", "quantity", "filled_qty", "order_type", "price", "stop_price", "state", "protected", "reduce_only")
    CLIENT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    NT_ORDER_ID_FIELD_NUMBER: _ClassVar[int]
    INSTRUMENT_FIELD_NUMBER: _ClassVar[int]
    ACTION_FIELD_NUMBER: _ClassVar[int]
    QUANTITY_FIELD_NUMBER: _ClassVar[int]
    FILLED_QTY_FIELD_NUMBER: _ClassVar[int]
    ORDER_TYPE_FIELD_NUMBER: _ClassVar[int]
    PRICE_FIELD_NUMBER: _ClassVar[int]
    STOP_PRICE_FIELD_NUMBER: _ClassVar[int]
    STATE_FIELD_NUMBER: _ClassVar[int]
    PROTECTED_FIELD_NUMBER: _ClassVar[int]
    REDUCE_ONLY_FIELD_NUMBER: _ClassVar[int]
    client_order_id: str
    nt_order_id: str
    instrument: str
    action: OrderAction
    quantity: int
    filled_qty: int
    order_type: OrderType
    price: float
    stop_price: float
    state: OrderState
    protected: bool
    reduce_only: bool
    def __init__(self, client_order_id: _Optional[str] = ..., nt_order_id: _Optional[str] = ..., instrument: _Optional[str] = ..., action: _Optional[_Union[OrderAction, str]] = ..., quantity: _Optional[int] = ..., filled_qty: _Optional[int] = ..., order_type: _Optional[_Union[OrderType, str]] = ..., price: _Optional[float] = ..., stop_price: _Optional[float] = ..., state: _Optional[_Union[OrderState, str]] = ..., protected: bool = ..., reduce_only: bool = ...) -> None: ...

class AccountMetrics(_message.Message):
    __slots__ = ("balance", "equity", "available_margin", "realized_pnl_today", "currency", "account_name")
    BALANCE_FIELD_NUMBER: _ClassVar[int]
    EQUITY_FIELD_NUMBER: _ClassVar[int]
    AVAILABLE_MARGIN_FIELD_NUMBER: _ClassVar[int]
    REALIZED_PNL_TODAY_FIELD_NUMBER: _ClassVar[int]
    CURRENCY_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_NAME_FIELD_NUMBER: _ClassVar[int]
    balance: float
    equity: float
    available_margin: float
    realized_pnl_today: float
    currency: str
    account_name: str
    def __init__(self, balance: _Optional[float] = ..., equity: _Optional[float] = ..., available_margin: _Optional[float] = ..., realized_pnl_today: _Optional[float] = ..., currency: _Optional[str] = ..., account_name: _Optional[str] = ...) -> None: ...

class StateSyncResponse(_message.Message):
    __slots__ = ("open_orders", "positions", "account", "safe_mode", "timestamp_unix_ms", "state_hash")
    OPEN_ORDERS_FIELD_NUMBER: _ClassVar[int]
    POSITIONS_FIELD_NUMBER: _ClassVar[int]
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    SAFE_MODE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    STATE_HASH_FIELD_NUMBER: _ClassVar[int]
    open_orders: _containers.RepeatedCompositeFieldContainer[WorkingOrder]
    positions: _containers.RepeatedCompositeFieldContainer[PositionUpdate]
    account: AccountMetrics
    safe_mode: SafeModeState
    timestamp_unix_ms: int
    state_hash: str
    def __init__(self, open_orders: _Optional[_Iterable[_Union[WorkingOrder, _Mapping]]] = ..., positions: _Optional[_Iterable[_Union[PositionUpdate, _Mapping]]] = ..., account: _Optional[_Union[AccountMetrics, _Mapping]] = ..., safe_mode: _Optional[_Union[SafeModeState, str]] = ..., timestamp_unix_ms: _Optional[int] = ..., state_hash: _Optional[str] = ...) -> None: ...

class GetAccountStateRequest(_message.Message):
    __slots__ = ("correlation_id",)
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    correlation_id: str
    def __init__(self, correlation_id: _Optional[str] = ...) -> None: ...

class AccountState(_message.Message):
    __slots__ = ("account", "positions", "open_orders", "safe_mode", "timestamp_unix_ms")
    ACCOUNT_FIELD_NUMBER: _ClassVar[int]
    POSITIONS_FIELD_NUMBER: _ClassVar[int]
    OPEN_ORDERS_FIELD_NUMBER: _ClassVar[int]
    SAFE_MODE_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    account: AccountMetrics
    positions: _containers.RepeatedCompositeFieldContainer[PositionUpdate]
    open_orders: _containers.RepeatedCompositeFieldContainer[WorkingOrder]
    safe_mode: SafeModeState
    timestamp_unix_ms: int
    def __init__(self, account: _Optional[_Union[AccountMetrics, _Mapping]] = ..., positions: _Optional[_Iterable[_Union[PositionUpdate, _Mapping]]] = ..., open_orders: _Optional[_Iterable[_Union[WorkingOrder, _Mapping]]] = ..., safe_mode: _Optional[_Union[SafeModeState, str]] = ..., timestamp_unix_ms: _Optional[int] = ...) -> None: ...

class SubscribeMarketData(_message.Message):
    __slots__ = ("instruments", "include_ticks", "include_bars", "bar_period")
    INSTRUMENTS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_TICKS_FIELD_NUMBER: _ClassVar[int]
    INCLUDE_BARS_FIELD_NUMBER: _ClassVar[int]
    BAR_PERIOD_FIELD_NUMBER: _ClassVar[int]
    instruments: _containers.RepeatedScalarFieldContainer[str]
    include_ticks: bool
    include_bars: bool
    bar_period: str
    def __init__(self, instruments: _Optional[_Iterable[str]] = ..., include_ticks: bool = ..., include_bars: bool = ..., bar_period: _Optional[str] = ...) -> None: ...

class UnsubscribeMarketData(_message.Message):
    __slots__ = ("instruments",)
    INSTRUMENTS_FIELD_NUMBER: _ClassVar[int]
    instruments: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, instruments: _Optional[_Iterable[str]] = ...) -> None: ...

class MarketDataUpdate(_message.Message):
    __slots__ = ("instrument", "timestamp_unix_ms", "last", "bid", "ask", "volume", "open", "high", "low", "close", "is_bar")
    INSTRUMENT_FIELD_NUMBER: _ClassVar[int]
    TIMESTAMP_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    LAST_FIELD_NUMBER: _ClassVar[int]
    BID_FIELD_NUMBER: _ClassVar[int]
    ASK_FIELD_NUMBER: _ClassVar[int]
    VOLUME_FIELD_NUMBER: _ClassVar[int]
    OPEN_FIELD_NUMBER: _ClassVar[int]
    HIGH_FIELD_NUMBER: _ClassVar[int]
    LOW_FIELD_NUMBER: _ClassVar[int]
    CLOSE_FIELD_NUMBER: _ClassVar[int]
    IS_BAR_FIELD_NUMBER: _ClassVar[int]
    instrument: str
    timestamp_unix_ms: int
    last: float
    bid: float
    ask: float
    volume: int
    open: float
    high: float
    low: float
    close: float
    is_bar: bool
    def __init__(self, instrument: _Optional[str] = ..., timestamp_unix_ms: _Optional[int] = ..., last: _Optional[float] = ..., bid: _Optional[float] = ..., ask: _Optional[float] = ..., volume: _Optional[int] = ..., open: _Optional[float] = ..., high: _Optional[float] = ..., low: _Optional[float] = ..., close: _Optional[float] = ..., is_bar: bool = ...) -> None: ...

class HistoricalDataRequest(_message.Message):
    __slots__ = ("instrument", "bar_period", "start_unix_ms", "end_unix_ms", "max_bars", "correlation_id")
    INSTRUMENT_FIELD_NUMBER: _ClassVar[int]
    BAR_PERIOD_FIELD_NUMBER: _ClassVar[int]
    START_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    END_UNIX_MS_FIELD_NUMBER: _ClassVar[int]
    MAX_BARS_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    instrument: str
    bar_period: str
    start_unix_ms: int
    end_unix_ms: int
    max_bars: int
    correlation_id: str
    def __init__(self, instrument: _Optional[str] = ..., bar_period: _Optional[str] = ..., start_unix_ms: _Optional[int] = ..., end_unix_ms: _Optional[int] = ..., max_bars: _Optional[int] = ..., correlation_id: _Optional[str] = ...) -> None: ...

class HistoricalDataResponse(_message.Message):
    __slots__ = ("instrument", "bars", "correlation_id", "code", "message")
    INSTRUMENT_FIELD_NUMBER: _ClassVar[int]
    BARS_FIELD_NUMBER: _ClassVar[int]
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    CODE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    instrument: str
    bars: _containers.RepeatedCompositeFieldContainer[MarketDataUpdate]
    correlation_id: str
    code: str
    message: str
    def __init__(self, instrument: _Optional[str] = ..., bars: _Optional[_Iterable[_Union[MarketDataUpdate, _Mapping]]] = ..., correlation_id: _Optional[str] = ..., code: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class RiskParameters(_message.Message):
    __slots__ = ("max_position_size", "daily_loss_limit", "max_orders_per_minute", "heartbeat_timeout_ms", "flatten_grace_ms", "flatten_on_timeout", "max_position_by_instrument")
    class MaxPositionByInstrumentEntry(_message.Message):
        __slots__ = ("key", "value")
        KEY_FIELD_NUMBER: _ClassVar[int]
        VALUE_FIELD_NUMBER: _ClassVar[int]
        key: str
        value: int
        def __init__(self, key: _Optional[str] = ..., value: _Optional[int] = ...) -> None: ...
    MAX_POSITION_SIZE_FIELD_NUMBER: _ClassVar[int]
    DAILY_LOSS_LIMIT_FIELD_NUMBER: _ClassVar[int]
    MAX_ORDERS_PER_MINUTE_FIELD_NUMBER: _ClassVar[int]
    HEARTBEAT_TIMEOUT_MS_FIELD_NUMBER: _ClassVar[int]
    FLATTEN_GRACE_MS_FIELD_NUMBER: _ClassVar[int]
    FLATTEN_ON_TIMEOUT_FIELD_NUMBER: _ClassVar[int]
    MAX_POSITION_BY_INSTRUMENT_FIELD_NUMBER: _ClassVar[int]
    max_position_size: int
    daily_loss_limit: float
    max_orders_per_minute: int
    heartbeat_timeout_ms: int
    flatten_grace_ms: int
    flatten_on_timeout: bool
    max_position_by_instrument: _containers.ScalarMap[str, int]
    def __init__(self, max_position_size: _Optional[int] = ..., daily_loss_limit: _Optional[float] = ..., max_orders_per_minute: _Optional[int] = ..., heartbeat_timeout_ms: _Optional[int] = ..., flatten_grace_ms: _Optional[int] = ..., flatten_on_timeout: bool = ..., max_position_by_instrument: _Optional[_Mapping[str, int]] = ...) -> None: ...

class RiskParametersAck(_message.Message):
    __slots__ = ("accepted", "message", "applied")
    ACCEPTED_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    APPLIED_FIELD_NUMBER: _ClassVar[int]
    accepted: bool
    message: str
    applied: RiskParameters
    def __init__(self, accepted: bool = ..., message: _Optional[str] = ..., applied: _Optional[_Union[RiskParameters, _Mapping]] = ...) -> None: ...

class GetRiskParametersRequest(_message.Message):
    __slots__ = ("correlation_id",)
    CORRELATION_ID_FIELD_NUMBER: _ClassVar[int]
    correlation_id: str
    def __init__(self, correlation_id: _Optional[str] = ...) -> None: ...
