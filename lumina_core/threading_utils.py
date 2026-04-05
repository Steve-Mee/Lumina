import threading
from typing import Callable


def start_daemon(target: Callable, *args, name: str | None = None) -> threading.Thread:
    """Start a daemon thread and return it for optional observability."""
    t = threading.Thread(target=target, args=args, daemon=True, name=name)
    t.start()
    return t
