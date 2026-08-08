"""Compatibility shim — implementation in `lumina_core.rl.ppo_device`."""
from __future__ import annotations

import sys

from lumina_core.rl import ppo_device as _impl

sys.modules[__name__] = _impl
