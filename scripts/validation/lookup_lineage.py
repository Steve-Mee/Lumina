from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _iter_rows(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            yield row


def _matches(
    row: dict[str, Any],
    *,
    prompt_hash: str | None,
    context_id: str | None,
    agent_id: str | None,
    config_hash: str | None,
) -> bool:
    if prompt_hash and str(row.get("prompt_hash", "")) != prompt_hash:
        return False
    if context_id and str(row.get("decision_context_id", "")) != context_id:
        return False
    if agent_id and str(row.get("agent_id", "")) != agent_id:
        return False
    if config_hash:
        top_level = str(row.get("config_snapshot_hash", ""))
        lineage_hash = (
            str((row.get("lineage") or {}).get("config_snapshot_hash", ""))
            if isinstance(row.get("lineage"), dict)
            else ""
        )
        if top_level != config_hash and lineage_hash != config_hash:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Lookup lineage rows in agent decision log")
    parser.add_argument("--log", default="state/agent_decision_log.jsonl", help="Path to decision log")
    parser.add_argument("--prompt-hash", default=None)
    parser.add_argument("--context-id", default=None)
    parser.add_argument("--agent-id", default=None)
    parser.add_argument("--config-hash", default=None)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    path = Path(args.log)
    rows = [
        row
        for row in _iter_rows(path)
        if _matches(
            row,
            prompt_hash=args.prompt_hash,
            context_id=args.context_id,
            agent_id=args.agent_id,
            config_hash=args.config_hash,
        )
    ]

    rows = rows[-max(1, int(args.limit)) :]
    print(json.dumps({"count": len(rows), "matches": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
