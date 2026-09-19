#!/usr/bin/env python
"""Install Birth PPO physics (torch + stable_baselines3). Never installs vLLM.

Usage (from repo root, same interpreter as Birth):

    python scripts/install_birth_physics_stack.py
    python scripts/install_birth_physics_stack.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Birth physics stack (torch+SB3, no vLLM)")
    parser.add_argument("--dry-run", action="store_true", help="Print pip commands only")
    parser.add_argument(
        "--workspace",
        default=str(ROOT),
        help="Workspace root (unused by physics pip; kept for operator copy/paste)",
    )
    parser.add_argument(
        "--with-vllm",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    if args.with_vllm:
        print("REFUSE: --with-vllm is forbidden. The training engine never installs vLLM.", file=sys.stderr)
        print(
            "REFUSE: vLLM is an optional extra-fast talking server on Linux/WSL2 in its own venv.",
            file=sys.stderr,
        )
        return 2
    from lumina_core.birth.physics_stack_install import HUMAN_SUMMARY_LINES, install_birth_physics_stack

    try:
        result = install_birth_physics_stack(
            python_exe=sys.executable,
            workspace_root=Path(args.workspace),
            dry_run=bool(args.dry_run),
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, default=str))
    for line in HUMAN_SUMMARY_LINES:
        print(line)
    if args.dry_run:
        return 0
    return 0 if bool(result.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
