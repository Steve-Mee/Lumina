"""Compatibility shim — implementation in `lumina_core.engine.backtest.backtester_fills`."""
from __future__ import annotations

import sys

from lumina_core.engine.backtest import backtester_fills as _impl

sys.modules[__name__] = _impl
