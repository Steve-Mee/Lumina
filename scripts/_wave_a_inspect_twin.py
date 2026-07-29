"""Inspect approval_twin_agent structure for Wave A split."""
from __future__ import annotations

from pathlib import Path

p = Path("lumina_core/evolution/approval_twin_agent.py")
lines = p.read_text(encoding="utf-8").splitlines()
for i, l in enumerate(lines, 1):
    if l.startswith("class ") or (l.startswith("    def ") and not l.startswith("        ")):
        print(f"{i}: {l[:100]}")
print("TOTAL", len(lines))
