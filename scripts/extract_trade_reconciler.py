"""Mechanical split of lumina_core/engine/trade_reconciler.py into mixin package."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "lumina_core" / "engine" / "trade_reconciler.py"
PKG = ROOT / "lumina_core" / "engine" / "trade_reconciler"

COMMON_HEADER = '''from __future__ import annotations

import logging

from lumina_core.engine.trade_reconciler.schemas import FillEvent, PendingTradeClose

logger = logging.getLogger(__name__)

'''

SCHEMAS_HEADER = '''"""Trade reconciliation domain models."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

'''

RECONCILER_HEADER = '''"""TradeReconciler orchestrator (mixin composition)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

from lumina_core.engine.lumina_engine import LuminaEngine
from lumina_core.engine.trade_reconciler.audit_status_mixin import AuditStatusMixin
from lumina_core.engine.trade_reconciler.fill_ingest_mixin import FillIngestMixin
from lumina_core.engine.trade_reconciler.fill_matching_mixin import FillMatchingMixin
from lumina_core.engine.trade_reconciler.fill_normalization_mixin import FillNormalizationMixin
from lumina_core.engine.trade_reconciler.finalize_mixin import FinalizeMixin
from lumina_core.engine.trade_reconciler.lifecycle_mixin import LifecycleMixin
from lumina_core.engine.trade_reconciler.transport_mixin import TransportMixin
from lumina_core.engine.valuation_engine import ValuationEngine

'''

INIT = '''"""Trade reconciler facade (re-exports bounded submodules)."""

from __future__ import annotations

from lumina_core.engine.trade_reconciler.reconciler import TradeReconciler
from lumina_core.engine.trade_reconciler.schemas import FillEvent, PendingTradeClose

__all__ = ["FillEvent", "PendingTradeClose", "TradeReconciler"]
'''

GROUPS: list[tuple[str, str, int, int, str]] = [
    (
        "lifecycle_mixin.py",
        "LifecycleMixin",
        99,
        210,
        '''from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from lumina_core.risk.mode_capabilities import resolve_mode_capabilities
from lumina_core.engine.trade_reconciler.schemas import PendingTradeClose

logger = logging.getLogger(__name__)

''',
    ),
    (
        "fill_ingest_mixin.py",
        "FillIngestMixin",
        212,
        302,
        COMMON_HEADER,
    ),
    (
        "transport_mixin.py",
        "TransportMixin",
        304,
        432,
        '''from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any

import requests
import websockets

from lumina_core.engine.errors import format_error_code
from lumina_core.engine.trade_reconciler.schemas import FillEvent

logger = logging.getLogger(__name__)

''',
    ),
    (
        "fill_matching_mixin.py",
        "FillMatchingMixin",
        434,
        542,
        '''from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone

from lumina_core.engine.trade_reconciler.schemas import FillEvent, PendingTradeClose

logger = logging.getLogger(__name__)

''',
    ),
    (
        "finalize_mixin.py",
        "FinalizeMixin",
        544,
        746,
        '''from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from lumina_core.engine.economic_pnl_service import EconomicPnLService
from lumina_core.engine.errors import format_error_code
from lumina_core.engine.trade_reconciler.schemas import FillEvent, PendingTradeClose

logger = logging.getLogger(__name__)

''',
    ),
    (
        "audit_status_mixin.py",
        "AuditStatusMixin",
        748,
        812,
        '''from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lumina_core.audit import get_audit_logger
from lumina_core.risk.mode_capabilities import resolve_mode_capabilities
from lumina_core.engine.trade_reconciler.schemas import PendingTradeClose

logger = logging.getLogger(__name__)

''',
    ),
    (
        "fill_normalization_mixin.py",
        "FillNormalizationMixin",
        814,
        976,
        '''from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from lumina_core.engine.trade_reconciler.schemas import FillEvent

logger = logging.getLogger(__name__)

''',
    ),
]


def _slice(lines: list[str], start: int, end: int) -> str:
    return "".join(lines[start - 1 : end])


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    PKG.mkdir(parents=True, exist_ok=True)

    schemas_body = _slice(lines, 29, 83)
    (PKG / "schemas.py").write_text(SCHEMAS_HEADER + schemas_body, encoding="utf-8")

    for filename, class_name, start, end, header in GROUPS:
        body = _slice(lines, start, end)
        content = f'"""{class_name} methods for TradeReconciler."""\n\n{header}\nclass {class_name}:\n{body}'
        (PKG / filename).write_text(content, encoding="utf-8")

    class_fields = _slice(lines, 90, 98)
    reconciler = (
        RECONCILER_HEADER
        + "@dataclass(slots=True)\nclass TradeReconciler(\n"
        + "    LifecycleMixin,\n"
        + "    FillIngestMixin,\n"
        + "    TransportMixin,\n"
        + "    FillMatchingMixin,\n"
        + "    FinalizeMixin,\n"
        + "    AuditStatusMixin,\n"
        + "    FillNormalizationMixin,\n"
        + "):\n"
        + '    """Reconciles broker fill events against locally detected close snapshots."""\n\n'
        + class_fields
    )
    (PKG / "reconciler.py").write_text(reconciler, encoding="utf-8")
    (PKG / "__init__.py").write_text(INIT, encoding="utf-8")
    print(f"Wrote package under {PKG}")


if __name__ == "__main__":
    main()