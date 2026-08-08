"""Compatibility shim — implementation in `lumina_core.engine.backtest.backtester_engine`."""
from __future__ import annotations

import sys

from lumina_core.engine.backtest import backtester_engine as _impl

sys.modules[__name__] = _impl
