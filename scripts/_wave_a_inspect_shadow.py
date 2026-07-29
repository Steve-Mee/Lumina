"""Inspect shadow.py structure for Wave A PR6."""
from __future__ import annotations

from pathlib import Path

p = Path("lumina_core/risk/shadow.py")
lines = p.read_text(encoding="utf-8").splitlines()
for i, l in enumerate(lines, 1):
    if l.startswith("class ") or (l.startswith("def ") and not l.startswith("    ")):
        print(f"{i}: {l[:110]}")
    elif l.startswith("    def ") and not l.startswith("        "):
        print(f"{i}: {l[:110]}")
print("TOTAL", len(lines))
