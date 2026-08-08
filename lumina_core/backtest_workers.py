"""Compatibility shim — implementation in `lumina_core.engine.backtest.backtest_workers`."""
from __future__ import annotations

import sys

from lumina_core.engine.backtest import backtest_workers as _impl

sys.modules[__name__] = _impl
