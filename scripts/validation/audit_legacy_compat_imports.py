from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT_FILE = ROOT / "state" / "legacy_import_audit.json"

TARGETS = {
    "lumina_core.engine.FastPathEngine": [],
    "lumina_core.engine.TapeReadingAgent": [],
    "lumina_core.engine.AdvancedBacktesterEngine": [],
    "lumina_core.engine.RealisticBacktesterEngine": [],
}

DEPRECATION_SCHEDULE = {
    "lumina_core.engine.FastPathEngine": {
        "tracker_id": "B2-legacy-compat",
        "deadline_utc": "2026-06-30T00:00:00Z",
    },
    "lumina_core.engine.TapeReadingAgent": {
        "tracker_id": "B2-legacy-compat",
        "deadline_utc": "2026-06-30T00:00:00Z",
    },
    "lumina_core.engine.AdvancedBacktesterEngine": {
        "tracker_id": "B2-legacy-compat",
        "deadline_utc": "2026-06-30T00:00:00Z",
    },
    "lumina_core.engine.RealisticBacktesterEngine": {
        "tracker_id": "B2-legacy-compat",
        "deadline_utc": "2026-06-30T00:00:00Z",
    },
}

IMPORT_RE = re.compile(r"^\s*(?:from\s+([\w\.]+)\s+import\s+([\w\*,\s]+)|import\s+([\w\.,\s]+))\s*$")


def _scan_file(path: Path) -> None:
    text = path.read_text(encoding="utf-8", errors="replace")
    for idx, line in enumerate(text.splitlines(), start=1):
        m = IMPORT_RE.match(line)
        if not m:
            continue
        from_mod = m.group(1)
        from_syms = m.group(2)
        import_list = m.group(3)

        if from_mod and from_syms:
            for key in TARGETS:
                if from_mod == key:
                    TARGETS[key].append(
                        {"file": str(path.relative_to(ROOT)).replace("\\\\", "/"), "line": idx, "import": line.strip()}
                    )
        elif import_list:
            chunks = [item.strip() for item in import_list.split(",") if item.strip()]
            for chunk in chunks:
                for key in TARGETS:
                    if chunk == key:
                        TARGETS[key].append(
                            {
                                "file": str(path.relative_to(ROOT)).replace("\\\\", "/"),
                                "line": idx,
                                "import": line.strip(),
                            }
                        )


def main() -> int:
    for path in ROOT.rglob("*.py"):
        rel = str(path.relative_to(ROOT)).replace("\\\\", "/")
        if rel.startswith(".venv/") or rel.startswith("state/"):
            continue
        _scan_file(path)

    summary = {k: len(v) for k, v in TARGETS.items()}
    payload = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "deprecation_schedule": DEPRECATION_SCHEDULE,
        "occurrences": TARGETS,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Legacy import audit written: {OUT_FILE}")
    for key, count in summary.items():
        print(f"- {key}: {count}")

    fail_on_hits = str(os.getenv("LUMINA_FAIL_ON_LEGACY_IMPORTS", "false")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    total_hits = sum(summary.values())
    if fail_on_hits and total_hits > 0:
        print(f"Legacy import audit failed: {total_hits} compat imports remain")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
