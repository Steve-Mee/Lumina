from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def main() -> int:
    evolution_rows = _read_jsonl(Path("state/evolution_log.jsonl"))
    lifecycle_rows = _read_jsonl(Path("state/evolution_lifecycle.jsonl"))

    proposed = [
        r
        for r in evolution_rows
        if str(r.get("status", "")).lower() in {"proposed", "applied", "awaiting_human_approval"}
    ]
    promoted = [r for r in lifecycle_rows if str(r.get("state", "")).lower() == "promoted"]
    rolled_back = [r for r in lifecycle_rows if str(r.get("state", "")).lower() == "rolled_back"]

    readiness = len(proposed) >= 1 and len(promoted) >= 1 and len(rolled_back) == 0

    report = {
        "status": "green" if readiness else "amber",
        "ready_for_promotion": readiness,
        "proposals_seen": len(proposed),
        "promotions_seen": len(promoted),
        "rollbacks_seen": len(rolled_back),
        "notes": "Shadow rollout requires at least one promoted lifecycle without rollback in current evidence set.",
    }

    out_dir = Path("state/validation")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "shadow_rollout_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": str(out_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
