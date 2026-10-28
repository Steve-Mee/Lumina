"""Import-forbidden guard: challenger_venue must not import NT/broker (K4)."""

from __future__ import annotations

from pathlib import Path

FORBIDDEN_IMPORT_SNIPPETS = (
    "NtOrderGateway",
    "CrossTradeBroker",
    "lumina_core.broker.ninjatrader",
    "lumina_core.broker.emergency_opt_in",
)


def venue_package_dir() -> Path:
    return Path(__file__).resolve().parent


def scan_forbidden_imports(root: Path | None = None) -> list[str]:
    hits: list[str] = []
    base = root or venue_package_dir()
    for path in base.glob("*.py"):
        if path.name == "imports_guard.py":
            continue
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN_IMPORT_SNIPPETS:
            if token in text:
                hits.append(f"{path.name}:{token}")
    return hits
