from __future__ import annotations

import sys
import threading
from functools import lru_cache

from lumina_core.bootstrap import bootstrap_runtime, create_public_api
from lumina_core.container import ApplicationContainer, create_application_container
from lumina_core.engine.runtime_entrypoint import run_with_mode


@lru_cache(maxsize=1)
def get_container() -> ApplicationContainer:
    # Lazy container creation keeps import-time compatibility for validators.
    return create_application_container()


def get_public_api() -> dict[str, object]:
    return create_public_api(get_container())


def __getattr__(name: str):
    container = get_container()

    _compat_fn_map = {
        "detect_market_regime": container.engine.detect_market_regime,
    }
    if name in _compat_fn_map:
        return _compat_fn_map[name]

    attr_map = {
        "CONFIG": "config",
        "ENGINE": "engine",
        "ANALYSIS_SERVICE": "analysis_service",
        "engine": "engine",
        "RUNTIME_CONTEXT": "runtime_context",
        "runtime_context": "runtime_context",
        "logger": "logger",
        "SWARM_SYMBOLS": "swarm_symbols",
        "INSTRUMENT": "primary_instrument",
    }
    if name in attr_map:
        return getattr(container, attr_map[name])

    api = get_public_api()
    if name in api:
        return api[name]

    raise AttributeError(f"module 'lumina_runtime' has no attribute '{name}'")


def main(argv: list[str] | None = None) -> int:
    runtime_argv = argv if argv is not None else sys.argv[1:]
    if runtime_argv:
        return run_with_mode("real", argv=runtime_argv)

    container = get_container()
    bootstrap_runtime(container)

    if bool(getattr(container.config, "use_human_main_loop", False)):
        threading.Thread(target=container.analysis_service.run_main_loop, daemon=True).start()

    container.operations_service.run_forever_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
