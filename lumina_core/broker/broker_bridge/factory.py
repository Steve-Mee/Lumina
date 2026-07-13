"""Broker backend factory."""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.broker.broker_bridge.base import BrokerBridge
from lumina_core.broker.broker_bridge.cross_trade_broker import CrossTradeBroker
from lumina_core.broker.broker_bridge.paper_broker import PaperBroker


def _resolve_live_provider(config: Any) -> str:
    provider = str(getattr(config, "broker_live_provider", "crosstrade") or "crosstrade").strip().lower()
    if provider not in {"crosstrade", "ninjatrader"}:
        return "crosstrade"
    return provider


def broker_factory(
    config: Any | None = None, engine: Any | None = None, logger: logging.Logger | None = None
) -> BrokerBridge:
    backend = "paper"
    if config is not None:
        backend = str(getattr(config, "broker_backend", "paper") or "paper").strip().lower()
        if backend not in {"paper", "live"}:
            backend = "paper"

    if backend == "live":
        trade_mode = str(getattr(config, "trade_mode", "paper") or "paper").strip().lower()
        if trade_mode == "paper":
            raise ValueError(
                "broker_backend=live is incompatible with trade_mode=paper (set broker_backend=paper for paper mode)"
            )
        if trade_mode not in {"sim", "sim_real_guard", "real"}:
            raise ValueError(f"broker_backend=live requires trade_mode in sim/sim_real_guard/real, got {trade_mode!r}")

        provider = _resolve_live_provider(config)
        if provider == "ninjatrader":
            from lumina_core.broker.ninjatrader.broker import NinjaTraderBroker
            from lumina_core.broker.ninjatrader.bridge_service import get_ninjatrader_bridge_service

            bridge = get_ninjatrader_bridge_service(
                configured_account=str(getattr(config, "ninjatrader_account_name", "Sim101") or "Sim101"),
                trade_mode=trade_mode,
                ninjatrader_enabled=bool(getattr(config, "ninjatrader_enabled", False)),
            )
            return NinjaTraderBroker(
                configured_account=str(getattr(config, "ninjatrader_account_name", "Sim101") or "Sim101"),
                ninjatrader_enabled=bool(getattr(config, "ninjatrader_enabled", False)),
                logger=logger,
                engine=engine,
                bridge_service=bridge,
            )

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
            engine=engine,
        )

    return PaperBroker(engine=engine, logger=logger)
