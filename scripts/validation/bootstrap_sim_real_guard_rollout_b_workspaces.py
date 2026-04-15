from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

IGNORE_NAMES = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "logs",
    "state",
    "lumina_vector_db",
}


def _ignore_filter(_src: str, names: list[str]) -> set[str]:
    return {name for name in names if name in IGNORE_NAMES or name.endswith(".pyc")}


def _write_env_file(path: Path, updates: dict[str, str]) -> None:
    merged: dict[str, str] = {}
    if path.exists():
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            merged[key.strip()] = value.strip()
    merged.update({key: str(value) for key, value in updates.items() if value != ""})
    content = "\n".join(f"{key}={merged[key]}" for key in sorted(merged)) + "\n"
    path.write_text(content, encoding="utf-8")


def bootstrap_workspace(
    *,
    source_root: Path,
    target_root: Path,
    role: str,
    trade_mode: str,
    enable_sim_real_guard: bool,
    broker: str,
    crosstrade_token: str,
    crosstrade_account: str,
    shared_python_exe: str,
) -> dict[str, Any]:
    shutil.copytree(source_root, target_root, dirs_exist_ok=True, ignore=_ignore_filter)
    for relative_dir in (
        Path("state"),
        Path("logs"),
        Path("state/validation"),
        Path("state/validation/sim_real_guard_rollout_b"),
    ):
        (target_root / relative_dir).mkdir(parents=True, exist_ok=True)

    env_updates = {
        "TRADE_MODE": trade_mode,
        "LUMINA_MODE": trade_mode,
        "BROKER_BACKEND": broker,
        "TRADERLEAGUE_ACCOUNT_MODE": "sim",
        "ENABLE_SIM_REAL_GUARD": "true" if enable_sim_real_guard else "false",
        "ENABLE_SIM_REAL_GUARD_PILOT": "false",
        "ENABLE_SIM_REAL_GUARD_PUBLIC": "false",
        "ALLOW_SIM_REAL_GUARD_REAL_PROMOTION": "false",
        "TRADE_RECONCILER_STATUS_FILE": "state/trade_reconciler_status.json",
        "TRADE_RECONCILER_AUDIT_LOG": "logs/trade_fill_audit.jsonl",
        "CROSSTRADE_TOKEN": crosstrade_token,
        "CROSSTRADE_ACCOUNT": crosstrade_account,
    }
    _write_env_file(target_root / ".env", env_updates)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "role": role,
        "source_root": str(source_root),
        "target_root": str(target_root),
        "trade_mode": trade_mode,
        "broker": broker,
        "shared_python_exe": shared_python_exe,
        "uses_shared_python": bool(shared_python_exe),
    }
    manifest_path = target_root / "state" / "validation" / "sim_real_guard_rollout_b" / "bootstrap_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap isolated Rollout B workspaces for sim vs sim_real_guard parity runs.")
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--control-root", required=True)
    parser.add_argument("--candidate-root", required=True)
    parser.add_argument("--broker", choices=["paper", "live"], default="live")
    parser.add_argument("--crosstrade-token", default="")
    parser.add_argument("--crosstrade-account", default="")
    parser.add_argument("--shared-python-exe", default="")
    args = parser.parse_args()

    source_root = Path(args.source_root).resolve()
    control_root = Path(args.control_root).resolve()
    candidate_root = Path(args.candidate_root).resolve()
    if not source_root.exists():
        raise SystemExit(f"Source root not found: {source_root}")

    manifests = [
        bootstrap_workspace(
            source_root=source_root,
            target_root=control_root,
            role="control",
            trade_mode="sim",
            enable_sim_real_guard=False,
            broker=args.broker,
            crosstrade_token=args.crosstrade_token,
            crosstrade_account=args.crosstrade_account,
            shared_python_exe=args.shared_python_exe,
        ),
        bootstrap_workspace(
            source_root=source_root,
            target_root=candidate_root,
            role="candidate",
            trade_mode="sim_real_guard",
            enable_sim_real_guard=True,
            broker=args.broker,
            crosstrade_token=args.crosstrade_token,
            crosstrade_account=args.crosstrade_account,
            shared_python_exe=args.shared_python_exe,
        ),
    ]
    print(json.dumps({"status": "ok", "workspaces": manifests}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())