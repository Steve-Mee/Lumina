from __future__ import annotations

import sys
from functools import lru_cache

from lumina_core.bootstrap import create_public_api
from lumina_core.container import ApplicationContainer, create_application_container
from lumina_core.engine.runtime_entrypoint import run_with_mode


@lru_cache(maxsize=1)
def _get_container() -> ApplicationContainer:
    # Lazy container creation keeps import-time compatibility for validators.
    return create_application_container()


def __getattr__(name: str):
    container = _get_container()

    legacy_fn_map = {
        "detect_market_regime": container.engine.detect_market_regime,
    }
    if name in legacy_fn_map:
        return legacy_fn_map[name]

    attr_map = {
        "CONFIG": "config",
        "ENGINE": "engine",
        "engine": "engine",
        "RUNTIME_CONTEXT": "runtime_context",
        "runtime_context": "runtime_context",
        "logger": "logger",
        "SWARM_SYMBOLS": "swarm_symbols",
        "INSTRUMENT": "primary_instrument",
    }
    if name in attr_map:
        return getattr(container, attr_map[name])

    api = create_public_api(container)
    if name in api:
        return api[name]

    raise AttributeError(f"module 'lumina_v45.1.1' has no attribute '{name}'")


def main(argv: list[str] | None = None) -> int:
    # Legacy root command is preserved; centralized launcher owns runtime behavior.
    return run_with_mode("real", argv=argv if argv is not None else sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
