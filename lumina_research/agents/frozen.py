"""Fail-closed frozen instances. Mutation after construction is refused."""

from __future__ import annotations


class Frozen:
    """Instance attributes may be assigned only until ``_freeze()``."""

    _frozen: bool = False

    def __setattr__(self, name: str, value: object) -> None:
        if object.__getattribute__(self, "_frozen") is True:
            raise AttributeError(f"{type(self).__name__} attributes are frozen")
        object.__setattr__(self, name, value)

    def _freeze(self) -> None:
        object.__setattr__(self, "_frozen", True)
