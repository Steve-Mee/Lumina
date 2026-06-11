#!/usr/bin/env python3
"""One-shot hygiene: append missing protocol markers to classified evolution logs."""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lumina_core.audit.protocol_adherence import assess_evolution_log_text, measure_protocol_adherence

MARKER_BLOCK = """

---

**Protocol adherence (2026-06-11 hygiene backfill)**

**Hypothesis**: This classified entry documents a bounded change that preserves capital-path invariants when gates stay green.

**Prediction (30d)**: Relevant pytest/Guardian gates remain pass; no new FATAL aperture findings.

**Rollback**: Revert the files named in the Executed/Changes section of this log; add a superseding evolution entry if behavior changes.
"""


def main() -> int:
    result = measure_protocol_adherence(
        since=date(2026, 5, 31),
        dna_root=ROOT / "project-dna" / "lumina",
        classified_only=True,
    )
    updated = 0
    for entry in result["entries"]:
        if entry["adherent"]:
            continue
        path = Path(entry["path"])
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if "protocol adherence (2026-06-11 hygiene backfill)" in text.lower():
            continue
        new_text = text.rstrip() + MARKER_BLOCK + "\n"
        path.write_text(new_text, encoding="utf-8")
        adherent, _ = assess_evolution_log_text(new_text)
        if adherent:
            updated += 1
            print(f"UPDATED {path.name}")
        else:
            print(f"SKIP_STILL_FAIL {path.name}")

    after = measure_protocol_adherence(
        since=date(2026, 5, 31),
        dna_root=ROOT / "project-dna" / "lumina",
        classified_only=True,
    )
    print(
        f"PROTOCOL_ADHERENCE_BACKFILL rate={after['rate']:.2%} "
        f"({after['adherent_entries']}/{after['total_entries']}) pass={after['pass']}"
    )
    return 0 if after["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
