"""Compatibility shim — implementation in `lumina_core.rl.ppo_trainer`."""
from __future__ import annotations

import sys

from lumina_core.rl import ppo_trainer as _impl

sys.modules[__name__] = _impl
