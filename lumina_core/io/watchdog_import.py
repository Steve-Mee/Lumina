"""Import PyPI ``watchdog`` even when repo-root ``watchdog.py`` shadows the package name."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any


def load_watchdog_modules() -> tuple[Any, Any]:
    """Return ``(FileSystemEventHandler, Observer)`` from the PyPI watchdog package."""
    repo_root = Path(__file__).resolve().parents[2]

    for mod_name in list(sys.modules):
        if mod_name == "watchdog" or mod_name.startswith("watchdog."):
            mod = sys.modules.get(mod_name)
            mod_file = getattr(mod, "__file__", "") or ""
            if mod is not None and (not hasattr(mod, "__path__") or mod_file.endswith("watchdog.py")):
                del sys.modules[mod_name]

    filtered_path = [entry for entry in sys.path if Path(entry).resolve() != repo_root]
    previous_path = sys.path
    sys.path = filtered_path
    try:
        events_mod = importlib.import_module("watchdog.events")
        observers_mod = importlib.import_module("watchdog.observers")
    except ImportError as exc:
        raise RuntimeError(
            "watchdog is required for config hot-reload. Install with: pip install watchdog"
        ) from exc
    finally:
        sys.path = previous_path
    return events_mod.FileSystemEventHandler, observers_mod.Observer
