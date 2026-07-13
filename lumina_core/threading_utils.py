import threading
from typing import Callable


def start_daemon(
    target: Callable,
    *args,
    name: str | None = None,
    register: bool = True,
    target_factory: Callable[[], None] | None = None,
) -> threading.Thread:
    """Start a daemon thread and return it for optional observability."""
    t = threading.Thread(target=target, args=args, daemon=True, name=name)
    t.start()
    if register and name:
        from lumina_core.runtime.daemon_registry import RuntimeDaemonRegistry

        factory = target_factory
        if factory is None and not args:

            def _factory() -> None:
                target()

            factory = _factory
        RuntimeDaemonRegistry.get().register(name, t, target_factory=factory)
    return t
