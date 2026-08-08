"""Compatibility shim — implementation in `lumina_core.rl.infinite_simulator`."""
from __future__ import annotations

import sys

from lumina_core.rl import infinite_simulator as _impl

sys.modules[__name__] = _impl
