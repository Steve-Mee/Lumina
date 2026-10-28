"""Seal public names so evolution/agent code cannot rebind the Risk Core API."""

from __future__ import annotations

import sys
import types


class RiskCoreSealError(AttributeError):
    """Attempt to mutate a sealed research Risk Core symbol."""


def install_module_seal(module_name: str, frozen_names: tuple[str, ...]) -> None:
    module = sys.modules[module_name]
    frozen = frozenset(frozen_names)

    class SealedModule(types.ModuleType):
        def __setattr__(self, name: str, value: object) -> None:
            if name in frozen:
                raise RiskCoreSealError(f"cannot mutate sealed Risk Core name {name!r}")
            super().__setattr__(name, value)

        def __delattr__(self, name: str) -> None:
            if name in frozen:
                raise RiskCoreSealError(f"cannot delete sealed Risk Core name {name!r}")
            super().__delattr__(name)

    module.__class__ = SealedModule
