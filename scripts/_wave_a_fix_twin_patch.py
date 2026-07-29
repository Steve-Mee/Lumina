"""Wire twin_attr for monkeypatch-compatible monitoring calls."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYMS = [
    "record_shadow_twin_alignment_monitoring",
    "record_twin_decision_monitoring",
    "record_twin_steve_accuracy_monitoring",
    "record_twin_training_metrics_monitoring",
]


def wire(path: Path) -> None:
    t = path.read_text(encoding="utf-8")
    if "approval_twin_patch_bridge" not in t:
        t = t.replace(
            "from __future__ import annotations\n",
            "from __future__ import annotations\n\n"
            "from lumina_core.evolution.approval_twin_patch_bridge import twin_attr\n",
            1,
        )
    for sym in SYMS:
        pattern = rf"(?<![.\w]){sym}\("
        edits: list[tuple[int, int, str]] = []
        for m in re.finditer(pattern, t):
            start = m.start()
            look = t[max(0, start - 50) : start]
            if f'twin_attr("{sym}"' in look or f"twin_attr('{sym}'" in look:
                continue
            line_start = t.rfind("\n", 0, start) + 1
            line = t[line_start : t.find("\n", start)]
            if line.lstrip().startswith(("from ", "import ")):
                continue
            edits.append((start, m.end(), f'twin_attr("{sym}", {sym})('))
        for start, end, r in reversed(edits):
            t = t[:start] + r + t[end:]
    path.write_text(t, encoding="utf-8")
    print(path.name, "wired")


def main() -> None:
    for rel in (
        "lumina_core/evolution/approval_twin_evaluators.py",
        "lumina_core/evolution/approval_twin_bus.py",
        "lumina_core/evolution/approval_twin_training.py",
    ):
        wire(ROOT / rel)


if __name__ == "__main__":
    main()
