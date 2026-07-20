#!/usr/bin/env python3
"""Generate Python gRPC stubs from protos/lumina/execution/v1/fabric.proto.

Usage (from repo root):
    python scripts/generate_fabric_proto.py

Requires: grpcio-tools, protobuf (see requirements-trading.txt / requirements-dev.txt).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTO_ROOT = REPO_ROOT / "protos"
PROTO_FILE = PROTO_ROOT / "lumina" / "execution" / "v1" / "fabric.proto"
OUT_DIR = REPO_ROOT / "lumina_core" / "broker" / "ninjatrader" / "generated"
PACKAGE_INIT = OUT_DIR / "__init__.py"


def main() -> int:
    if not PROTO_FILE.is_file():
        print(f"ERROR: proto not found: {PROTO_FILE}", file=sys.stderr)
        return 1

    try:
        from grpc_tools import protoc  # type: ignore[import-untyped]
    except ImportError:
        print(
            "ERROR: grpcio-tools not installed. "
            "pip install grpcio-tools protobuf",
            file=sys.stderr,
        )
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Clear previous generated modules (keep package marker intent).
    for pattern in ("*_pb2.py", "*_pb2.pyi", "*_pb2_grpc.py"):
        for stale in OUT_DIR.glob(pattern):
            stale.unlink()

    args = [
        "grpc_tools.protoc",
        f"--proto_path={PROTO_ROOT}",
        f"--python_out={OUT_DIR}",
        f"--grpc_python_out={OUT_DIR}",
        f"--pyi_out={OUT_DIR}",
        str(PROTO_FILE.relative_to(PROTO_ROOT)).replace("\\", "/"),
    ]
    # protoc expects the path relative to proto_path as last arg.
    # When OUT_DIR receives nested package dirs, flatten is awkward —
    # write into OUT_DIR preserving package, then hoist modules.
    code = protoc.main(args)
    if code != 0:
        print(f"ERROR: protoc failed with exit code {code}", file=sys.stderr)
        return code

    # grpc_tools writes lumina/execution/v1/* under OUT_DIR when package path is used.
    nested = OUT_DIR / "lumina" / "execution" / "v1"
    if nested.is_dir():
        for item in nested.iterdir():
            dest = OUT_DIR / item.name
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))
        # Remove empty package tree
        shutil.rmtree(OUT_DIR / "lumina", ignore_errors=True)

    # Fix absolute imports in grpc stub for flat package layout.
    grpc_mod = OUT_DIR / "fabric_pb2_grpc.py"
    if grpc_mod.is_file():
        text = grpc_mod.read_text(encoding="utf-8")
        text = text.replace(
            "from lumina.execution.v1 import fabric_pb2 as lumina_dot_execution_dot_v1_dot_fabric__pb2",
            "from lumina_core.broker.ninjatrader.generated import fabric_pb2 as lumina_dot_execution_dot_v1_dot_fabric__pb2",
        )
        text = text.replace(
            "import fabric_pb2 as fabric__pb2",
            "from lumina_core.broker.ninjatrader.generated import fabric_pb2 as fabric__pb2",
        )
        grpc_mod.write_text(text, encoding="utf-8")

    PACKAGE_INIT.write_text(
        '"""Generated gRPC stubs for lumina.execution.v1 — do not edit by hand.\n\n'
        "Regenerate: python scripts/generate_fabric_proto.py\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        "from lumina_core.broker.ninjatrader.generated import fabric_pb2 as fabric_pb2\n"
        "from lumina_core.broker.ninjatrader.generated import fabric_pb2_grpc as fabric_pb2_grpc\n\n"
        '__all__ = ["fabric_pb2", "fabric_pb2_grpc"]\n',
        encoding="utf-8",
    )

    # Ensure relative import style works for type checkers on pb2
    pb2 = OUT_DIR / "fabric_pb2.py"
    if not pb2.is_file():
        print("ERROR: fabric_pb2.py was not generated", file=sys.stderr)
        return 1

    print(f"OK: generated stubs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
