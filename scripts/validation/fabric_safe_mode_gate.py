#!/usr/bin/env python3
"""T1: Fabric SAFE_MODE / disconnect proof gate (mock CI + optional live SIM).

Usage:
  python scripts/validation/fabric_safe_mode_gate.py              # --mock (default)
  python scripts/validation/fabric_safe_mode_gate.py --mock --json
  python scripts/validation/fabric_safe_mode_gate.py --live       # SIM only; needs host

Never targets REAL capital. Live path requires LUMINA_FABRIC_TOKEN and reachable host.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Unit/chaos paths that prove Brain-side fail-closed SAFE_MODE + disconnect
_MOCK_PYTEST = [
    "tests/broker/test_fabric_safe_mode_brain.py",
    "tests/broker/test_ninjatrader_guards.py::test_fabric_safe_mode_blocks_place_allows_cancel",
    "tests/broker/test_ninjatrader_guards.py::test_disconnect_blocks_orders_in_sim",
    "tests/broker/test_fabric_chaos.py::test_safe_mode_rejects_new_orders",
    "tests/broker/test_fabric_chaos.py::test_disconnect_fail_closed_on_bridge",
    "tests/risk/test_capital_aperture_lineage.py::test_fabric_blocks_place_in_safe_mode",
    "tests/risk/test_capital_aperture_lineage.py::test_fabric_blocks_strict_without_lineage",
]

_OPERATOR_CHECKLIST = [
    "NT8 + LUMINA Fabric AddOn; gRPC 127.0.0.1:50051; token match Core/AddOn",
    "broker.live_provider=ninjatrader, ninjatrader.enabled=true, account Sim101 (SIM only)",
    "Place one market order from Python; observe fill/order event",
    "Stop Brain heartbeats ≥ 5s; confirm working orders cancelled and SAFE_MODE entered",
    "Attempt place while SAFE → reject; cancel/flatten still allowed",
    "Re-auth / reconnect → SAFE clears; place works again",
    "Never run this checklist against REAL account",
]


def _run_mock_pytest() -> dict[str, Any]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *_MOCK_PYTEST,
        "-q",
        "--tb=line",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-1000:],
        "tests": list(_MOCK_PYTEST),
    }


def _run_live_probe() -> dict[str, Any]:
    """Optional SIM-only probe: connect, force local SAFE, assert place blocked.

    Does not stop host heartbeats (that is operator checklist). Never REAL.
    """
    token = str(os.getenv("LUMINA_FABRIC_TOKEN") or "").strip()
    host = str(os.getenv("LUMINA_FABRIC_HOST") or "127.0.0.1").strip()
    port = int(os.getenv("LUMINA_FABRIC_PORT") or "50051")
    if not token:
        return {
            "ok": False,
            "skipped": True,
            "reason": "LUMINA_FABRIC_TOKEN unset — live probe skipped",
        }
    try:
        import grpc  # noqa: F401
    except Exception as exc:
        return {"ok": False, "skipped": True, "reason": f"grpc unavailable: {exc}"}

    try:
        from lumina_core.broker.broker_bridge.schemas import Order
        from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient

        client = FabricGrpcClient(
            FabricConfig(
                host=host,
                port=port,
                auth_token=token,
                heartbeat_interval_ms=0,
                connect_timeout_seconds=3.0,
                command_timeout_seconds=3.0,
            )
        )
        connected = bool(client.connect())
        if not connected:
            return {
                "ok": False,
                "skipped": False,
                "reason": f"connect_failed host={host}:{port}",
            }
        # Force local SAFE (simulates host SAFE / post-disconnect Brain policy)
        with client._lock:  # noqa: SLF001
            try:
                from lumina_core.broker.ninjatrader.generated import fabric_pb2

                client._safe_mode = int(fabric_pb2.SAFE_MODE_STATE_SAFE)  # noqa: SLF001
            except Exception:
                client._safe_mode = 2  # noqa: SLF001
        order = Order(symbol="MNQ", side="BUY", quantity=1, order_type="MARKET")
        order.metadata = {"decision_context_id": "live-probe-safe-mode"}
        resp = client.place_order_sync(order, client_order_id="live-safe-probe")
        client.disconnect()
        code = str(resp.get("code") or "")
        blocked = resp.get("type") == "error" and (
            "SAFE" in code.upper() or "DISCONNECTED" in code.upper()
        )
        return {
            "ok": blocked,
            "skipped": False,
            "connected": True,
            "place_response": {
                "type": resp.get("type"),
                "code": resp.get("code"),
                "message": str(resp.get("message") or "")[:200],
            },
            "note": (
                "Local SAFE forced after connect — proves Brain place block. "
                "Host heartbeat-timeout cancel remains operator checklist."
            ),
        }
    except Exception as exc:
        return {"ok": False, "skipped": False, "reason": f"live_probe_error: {exc}"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fabric SAFE_MODE proof gate (T1)")
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Run automated pytest subset (default)",
    )
    parser.add_argument(
        "--no-mock",
        action="store_true",
        help="Skip pytest subset",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Optional SIM host probe (token required; never REAL)",
    )
    parser.add_argument("--json", action="store_true", help="JSON payload only")
    args = parser.parse_args(argv)

    result: dict[str, Any] = {
        "schema": "fabric_safe_mode_gate_v1",
        "real_capital": False,
        "operator_checklist": list(_OPERATOR_CHECKLIST),
    }

    run_mock = not bool(args.no_mock)
    if run_mock:
        result["mock"] = _run_mock_pytest()
    else:
        result["mock"] = {"ok": True, "skipped": True}

    if args.live:
        result["live"] = _run_live_probe()
    else:
        result["live"] = {"ok": True, "skipped": True, "reason": "not_requested"}

    mock_ok = bool(result["mock"].get("ok"))
    live = result["live"]
    live_ok = bool(live.get("ok")) if not live.get("skipped") else True
    result["ok"] = mock_ok and live_ok

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=True))
    else:
        print(f"fabric_safe_mode_gate ok={result['ok']}")
        if run_mock:
            m = result["mock"]
            print(f"  mock_pytest ok={m.get('ok')} rc={m.get('returncode')}")
            if not m.get("ok"):
                print(m.get("stdout_tail") or "")
                print(m.get("stderr_tail") or "")
        if args.live:
            print(f"  live_probe={json.dumps(result['live'], ensure_ascii=True)}")
        print("  operator_checklist (manual NT SIM):")
        for i, line in enumerate(_OPERATOR_CHECKLIST, 1):
            print(f"    {i}. {line}")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
