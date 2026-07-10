"""One-shot mechanical split of lumina_core/broker/broker_bridge.py."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "lumina_core" / "broker" / "broker_bridge.py"
PKG = ROOT / "lumina_core" / "broker" / "broker_bridge"


def _slice(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)
    PKG.mkdir(parents=True, exist_ok=True)

    schemas_header = '''"""Broker domain dataclasses and paper position helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

'''
    schemas_body = _slice(lines, 162, 262)
    (PKG / "schemas.py").write_text(schemas_header + schemas_body, encoding="utf-8")

    admission_header = '''"""Pre-submit admission chain wiring for broker order submission."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from lumina_core.engine.errors import ErrorSeverity, LuminaError, log_structured

import lumina_core.broker.broker_bridge as _bb

if TYPE_CHECKING:
    from lumina_core.broker.broker_bridge.schemas import Order

logger = logging.getLogger(__name__)

'''
    admission_body = _slice(lines, 69, 159)
    admission_body = admission_body.replace("enforce_pre_trade_gate", "_bb.enforce_pre_trade_gate")
    (PKG / "admission.py").write_text(admission_header + admission_body, encoding="utf-8")

    base_header = '''"""Abstract broker bridge protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from lumina_core.broker.broker_bridge.schemas import AccountInfo, Fill, Order, OrderResult, Position

'''
    base_body = _slice(lines, 265, 297)
    (PKG / "base.py").write_text(base_header + base_body, encoding="utf-8")

    cross_account_header = '''"""CrossTrade REST account field aliases and warn-once state."""

from __future__ import annotations

'''
    cross_account_body = _slice(lines, 21, 66)
    cross_account_body = cross_account_body.replace(
        "_CROSS_TRADE_BALANCE_WARN_ACCOUNTS", "CROSS_TRADE_BALANCE_WARN_ACCOUNTS"
    ).replace("_ACCOUNT_BALANCE_KEYS", "ACCOUNT_BALANCE_KEYS").replace(
        "_ACCOUNT_EQUITY_KEYS", "ACCOUNT_EQUITY_KEYS"
    ).replace("_ACCOUNT_PNL_KEYS", "ACCOUNT_PNL_KEYS"
    ).replace("_ACCOUNT_AVAILABLE_MARGIN_KEYS", "ACCOUNT_AVAILABLE_MARGIN_KEYS")
    (PKG / "cross_trade_account.py").write_text(cross_account_header + cross_account_body, encoding="utf-8")

    paper_header = '''"""Paper (simulation) broker implementation."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import lumina_core.broker.broker_bridge as _bb
from lumina_core.broker.broker_bridge.admission import run_final_arbitration
from lumina_core.broker.broker_bridge.base import BrokerBridge
from lumina_core.broker.broker_bridge.schemas import Fill, Order, OrderResult, Position, paper_position_from_fills
from lumina_core.risk.cost_model import TradeExecutionCostModel

'''
    paper_body = _slice(lines, 299, 556)
    paper_body = (
        paper_body.replace("class PaperBroker", "@dataclass(slots=True)\nclass PaperBroker", 1)
        .replace("@dataclass(slots=True)\n@dataclass(slots=True)\nclass PaperBroker", "@dataclass(slots=True)\nclass PaperBroker")
        .replace("_run_final_arbitration", "run_final_arbitration")
        .replace("random.gauss", "_bb.random.gauss")
    )
    # Remove duplicate docstring block at class start if slice included @dataclass twice
    paper_body = paper_body.replace(
        '@dataclass(slots=True)\nclass PaperBroker(BrokerBridge):\n    """\n    Paper',
        '@dataclass(slots=True)\nclass PaperBroker(BrokerBridge):\n    """\n    Paper',
    )
    (PKG / "paper_broker.py").write_text(paper_header + paper_body, encoding="utf-8")

    cross_header = '''"""CrossTrade live broker implementation."""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import requests

from lumina_core.broker.broker_bridge.admission import run_final_arbitration
from lumina_core.broker.broker_bridge.base import BrokerBridge
from lumina_core.broker.broker_bridge.cross_trade_account import (
    ACCOUNT_AVAILABLE_MARGIN_KEYS,
    ACCOUNT_BALANCE_KEYS,
    ACCOUNT_EQUITY_KEYS,
    ACCOUNT_PNL_KEYS,
    CROSS_TRADE_BALANCE_WARN_ACCOUNTS,
)
from lumina_core.broker.broker_bridge.schemas import AccountInfo, Fill, Order, OrderResult, Position

'''
    cross_body = _slice(lines, 559, 961)
    cross_body = (
        cross_body.replace("class CrossTradeBroker", "@dataclass(slots=True)\nclass CrossTradeBroker", 1)
        .replace("@dataclass(slots=True)\n@dataclass(slots=True)\nclass CrossTradeBroker", "@dataclass(slots=True)\nclass CrossTradeBroker")
        .replace("_run_final_arbitration", "run_final_arbitration")
        .replace("_CROSS_TRADE_BALANCE_WARN_ACCOUNTS", "CROSS_TRADE_BALANCE_WARN_ACCOUNTS")
        .replace("_ACCOUNT_BALANCE_KEYS", "ACCOUNT_BALANCE_KEYS")
        .replace("_ACCOUNT_EQUITY_KEYS", "ACCOUNT_EQUITY_KEYS")
        .replace("_ACCOUNT_PNL_KEYS", "ACCOUNT_PNL_KEYS")
        .replace("_ACCOUNT_AVAILABLE_MARGIN_KEYS", "ACCOUNT_AVAILABLE_MARGIN_KEYS")
    )
    (PKG / "cross_trade_broker.py").write_text(cross_header + cross_body, encoding="utf-8")

    factory_header = '''"""Broker backend factory."""

from __future__ import annotations

import logging
from typing import Any

from lumina_core.broker.broker_bridge.base import BrokerBridge
from lumina_core.broker.broker_bridge.cross_trade_broker import CrossTradeBroker
from lumina_core.broker.broker_bridge.paper_broker import PaperBroker

'''
    factory_body = _slice(lines, 964, 1001)
    (PKG / "factory.py").write_text(factory_header + factory_body, encoding="utf-8")

    init = '''"""Broker bridge facade (re-exports bounded submodules)."""

from __future__ import annotations

import random

from lumina_core.broker.broker_bridge.admission import audit_final_arbitration_reject
from lumina_core.broker.broker_bridge.base import BrokerBridge
from lumina_core.broker.broker_bridge.cross_trade_broker import CrossTradeBroker
from lumina_core.broker.broker_bridge.factory import broker_factory
from lumina_core.broker.broker_bridge.paper_broker import PaperBroker
from lumina_core.broker.broker_bridge.schemas import (
    AccountInfo,
    Fill,
    Order,
    OrderResult,
    Position,
    paper_position_from_fills,
)
from lumina_core.order_gatekeeper import enforce_pre_trade_gate

__all__ = [
    "AccountInfo",
    "BrokerBridge",
    "CrossTradeBroker",
    "Fill",
    "Order",
    "OrderResult",
    "PaperBroker",
    "Position",
    "audit_final_arbitration_reject",
    "broker_factory",
    "enforce_pre_trade_gate",
    "paper_position_from_fills",
    "random",
]
'''
    (PKG / "__init__.py").write_text(init, encoding="utf-8")
    print(f"Wrote package under {PKG}")


if __name__ == "__main__":
    main()