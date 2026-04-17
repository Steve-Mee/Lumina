from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests


@dataclass(slots=True)
class Order:
    symbol: str
    side: str
    quantity: int
    order_type: str = "MARKET"
    stop_loss: float = 0.0
    take_profit: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OrderResult:
    accepted: bool
    order_id: str
    status: str
    filled_qty: int = 0
    fill_price: float = 0.0
    message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AccountInfo:
    balance: float
    equity: float
    realized_pnl_today: float = 0.0
    currency: str = "USD"
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Position:
    symbol: str
    quantity: int
    avg_price: float
    side: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Fill:
    fill_id: str
    order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: str
    commission: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


class BrokerBridge(ABC):
    @abstractmethod
    def connect(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def submit_order(self, order: Order) -> OrderResult:
        raise NotImplementedError

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        raise NotImplementedError

    @abstractmethod
    def get_positions(self) -> list[Position]:
        raise NotImplementedError

    @abstractmethod
    def get_fills(self) -> list[Fill]:
        raise NotImplementedError

    @abstractmethod
    def subscribe_to_websocket(self) -> None:
        raise NotImplementedError


@dataclass(slots=True)
class PaperBroker(BrokerBridge):
    engine: Any | None = None
    logger: logging.Logger | None = None
    starting_balance: float = 50000.0
    _connected: bool = field(default=False, init=False)
    _positions: dict[str, Position] = field(default_factory=dict, init=False)
    _fills: list[Fill] = field(default_factory=list, init=False)

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self) -> None:
        self._connected = False

    def submit_order(self, order: Order) -> OrderResult:
        if not self._connected:
            self.connect()

        side = str(order.side).upper()
        if side not in {"BUY", "SELL"}:
            return OrderResult(
                accepted=False,
                order_id="",
                status="rejected",
                message=f"Unsupported side: {order.side}",
            )

        fill_price = 0.0
        if self.engine is not None:
            try:
                with self.engine.live_data_lock:
                    if self.engine.live_quotes:
                        fill_price = float(self.engine.live_quotes[-1]["last"])
                    elif len(self.engine.ohlc_1min) > 0:
                        fill_price = float(self.engine.ohlc_1min["close"].iloc[-1])
            except Exception:
                fill_price = 0.0

        order_id = f"paper-{uuid.uuid4()}"
        signed_qty = int(order.quantity) if side == "BUY" else -int(order.quantity)
        self._positions[order.symbol] = Position(
            symbol=order.symbol,
            quantity=signed_qty,
            avg_price=fill_price,
            side=side,
        )

        fill = Fill(
            fill_id=f"fill-{uuid.uuid4()}",
            order_id=order_id,
            symbol=order.symbol,
            side=side,
            quantity=int(order.quantity),
            price=fill_price,
            timestamp=datetime.now(timezone.utc).isoformat(),
            commission=0.0,
            raw={"broker": "paper"},
        )
        self._fills.append(fill)

        return OrderResult(
            accepted=True,
            order_id=order_id,
            status="filled",
            filled_qty=int(order.quantity),
            fill_price=fill_price,
            message="paper fill",
            raw={"broker": "paper", "fill_id": fill.fill_id},
        )

    def get_account_info(self) -> AccountInfo:
        if self.engine is None:
            return AccountInfo(balance=self.starting_balance, equity=self.starting_balance)

        return AccountInfo(
            balance=float(getattr(self.engine, "account_balance", self.starting_balance)),
            equity=float(getattr(self.engine, "account_equity", self.starting_balance)),
            realized_pnl_today=float(getattr(self.engine, "realized_pnl_today", 0.0)),
        )

    def get_positions(self) -> list[Position]:
        return list(self._positions.values())

    def get_fills(self) -> list[Fill]:
        return list(self._fills)

    def subscribe_to_websocket(self) -> None:
        # Paper mode has no external websocket stream.
        return


@dataclass(slots=True)
class CrossTradeBroker(BrokerBridge):
    api_key: str
    account: str
    websocket_url: str = "wss://app.crosstrade.io/ws/stream"
    base_url: str = "https://app.crosstrade.io"
    fill_poll_url: str = ""
    logger: logging.Logger | None = None
    timeout_seconds: float = 10.0
    _session: requests.Session | None = field(default=None, init=False)

    def connect(self) -> bool:
        if self._session is None:
            self._session = requests.Session()
        return True

    def disconnect(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key or ''}"}

    def _client(self) -> requests.Session:
        if self._session is None:
            self.connect()
        assert self._session is not None
        return self._session

    def submit_order(self, order: Order) -> OrderResult:
        payload = {
            "instrument": order.symbol,
            "action": str(order.side).upper(),
            "orderType": str(order.order_type).upper(),
            "quantity": int(order.quantity),
            "stopLoss": float(order.stop_loss),
            "takeProfit": float(order.take_profit),
        }

        try:
            response = self._client().post(
                f"{self.base_url}/v1/api/accounts/{self.account}/orders/place",
                headers=self._headers(),
                json=payload,
                timeout=self.timeout_seconds,
            )
            body = response.json() if response.content else {}
            accepted = response.status_code in (200, 201)
            return OrderResult(
                accepted=accepted,
                order_id=str(body.get("orderId", "")),
                status="accepted" if accepted else "rejected",
                filled_qty=int(body.get("filledQuantity", 0) or 0),
                fill_price=float(body.get("fillPrice", 0.0) or 0.0),
                message=str(body.get("message", "")),
                raw=body if isinstance(body, dict) else {"raw": body},
            )
        except Exception as exc:
            if self.logger is not None:
                self.logger.error(f"CrossTrade submit_order failed: {exc}")
            return OrderResult(
                accepted=False,
                order_id="",
                status="error",
                message=str(exc),
            )

    def get_account_info(self) -> AccountInfo:
        try:
            response = self._client().get(
                f"{self.base_url}/v1/api/accounts/{self.account}",
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            data = response.json() if response.content else {}
            return AccountInfo(
                balance=float(data.get("balance", 0.0) or 0.0),
                equity=float(data.get("equity", 0.0) or 0.0),
                realized_pnl_today=float(data.get("realizedPnlToday", 0.0) or 0.0),
                raw=data if isinstance(data, dict) else {"raw": data},
            )
        except Exception as exc:
            if self.logger is not None:
                self.logger.error(f"CrossTrade get_account_info failed: {exc}")
            return AccountInfo(balance=0.0, equity=0.0)

    def get_positions(self) -> list[Position]:
        try:
            response = self._client().get(
                f"{self.base_url}/v1/api/accounts/{self.account}/positions",
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            payload = response.json() if response.content else []
            rows = payload if isinstance(payload, list) else payload.get("positions", [])
            result: list[Position] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                qty = int(row.get("quantity", 0) or 0)
                side = "BUY" if qty >= 0 else "SELL"
                result.append(
                    Position(
                        symbol=str(row.get("instrument", "")),
                        quantity=qty,
                        avg_price=float(row.get("avgPrice", 0.0) or 0.0),
                        side=side,
                        raw=row,
                    )
                )
            return result
        except Exception as exc:
            if self.logger is not None:
                self.logger.error(f"CrossTrade get_positions failed: {exc}")
            return []

    def get_fills(self) -> list[Fill]:
        if not self.fill_poll_url:
            return []
        try:
            response = self._client().get(
                self.fill_poll_url,
                headers=self._headers(),
                timeout=self.timeout_seconds,
            )
            payload = response.json() if response.content else []
            rows = payload if isinstance(payload, list) else payload.get("fills", [])
            fills: list[Fill] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                fills.append(
                    Fill(
                        fill_id=str(row.get("fillId", "")),
                        order_id=str(row.get("orderId", "")),
                        symbol=str(row.get("instrument", "")),
                        side=str(row.get("action", "")).upper(),
                        quantity=int(row.get("quantity", 0) or 0),
                        price=float(row.get("fillPrice", 0.0) or 0.0),
                        timestamp=str(row.get("timestamp", datetime.now(timezone.utc).isoformat())),
                        commission=float(row.get("commission", 0.0) or 0.0),
                        raw=row,
                    )
                )
            return fills
        except Exception as exc:
            if self.logger is not None:
                self.logger.error(f"CrossTrade get_fills failed: {exc}")
            return []

    def subscribe_to_websocket(self) -> None:
        # Non-blocking probe so startup can validate credentials/endpoint without owning a long-lived loop.
        try:
            import websocket  # type: ignore

            ws = websocket.create_connection(
                self.websocket_url,
                header=[f"Authorization: Bearer {self.api_key}"],
                timeout=self.timeout_seconds,
            )
            subscribe_payload = {
                "action": "subscribe",
                "accounts": [self.account],
                "channels": ["fills", "executions"],
            }
            ws.send(json.dumps(subscribe_payload))
            ws.settimeout(0.2)
            try:
                ws.recv()
            except Exception:
                pass
            ws.close()
        except Exception as exc:
            if self.logger is not None:
                self.logger.warning(f"CrossTrade websocket subscribe probe failed: {exc}")


def broker_factory(
    config: Any | None = None, engine: Any | None = None, logger: logging.Logger | None = None
) -> BrokerBridge:
    backend = "paper"
    if config is not None:
        backend = str(getattr(config, "broker_backend", "paper") or "paper").strip().lower()
        if backend not in {"paper", "live"}:
            backend = "paper"

    if backend == "live":
        api_key = str(
            getattr(config, "broker_crosstrade_api_key", None) or getattr(config, "crosstrade_token", "") or ""
        ).strip()
        account = str(getattr(config, "crosstrade_account", "DEMO5042070")).strip()
        websocket_url = str(
            getattr(config, "broker_crosstrade_websocket_url", None)
            or getattr(config, "crosstrade_fill_ws_url", "wss://app.crosstrade.io/ws/stream")
        ).strip()
        base_url = str(getattr(config, "broker_crosstrade_base_url", "https://app.crosstrade.io")).strip()
        fill_poll_url = str(getattr(config, "crosstrade_fill_poll_url", "")).strip()
        return CrossTradeBroker(
            api_key=api_key,
            account=account,
            websocket_url=websocket_url,
            base_url=base_url,
            fill_poll_url=fill_poll_url,
            logger=logger,
        )

    return PaperBroker(engine=engine, logger=logger)
