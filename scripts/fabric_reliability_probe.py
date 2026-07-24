#!/usr/bin/env python3
"""48h boring-reliability probe: connect → account → place → flatten against Fabric SIM.

Requires:
  - LUMINA_FABRIC_TOKEN in env
  - Fabric host on 127.0.0.1:50051 (SimHost or NT8 AddOn, not both)

Writes:
  state/fabric_reliability/probes.jsonl
  state/fabric_reliability/summary.json
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from lumina_core.broker.broker_bridge.schemas import Order
from lumina_core.broker.ninjatrader.fabric_client import FabricConfig, FabricGrpcClient

OUT = Path("state/fabric_reliability")
LOG = OUT / "probes.jsonl"
WINDOW_HOURS = float(os.getenv("FABRIC_RELIABILITY_HOURS", "48"))
INTERVAL = int(os.getenv("FABRIC_RELIABILITY_INTERVAL_SEC", "300"))


def probe(token: str) -> dict[str, object]:
    ts = datetime.now(timezone.utc).isoformat()
    row: dict[str, object] = {"ts": ts, "ok": False}
    try:
        client = FabricGrpcClient(
            FabricConfig(
                host="127.0.0.1",
                port=50051,
                auth_token=token,
                mode_context="sim",
                heartbeat_interval_ms=500,
                connect_timeout_seconds=5,
                command_timeout_seconds=8,
            )
        )
        if not client.connect():
            row["error"] = "connect_failed"
            return row
        account, _positions, code = client.get_account_state()
        row["account_code"] = code
        row["equity"] = getattr(account, "equity", None)
        row["safe_mode"] = int(getattr(client, "safe_mode", 0) or 0)
        cid = f"rel-{uuid.uuid4().hex[:8]}"
        place = client.place_order_sync(
            Order(symbol="MES", side="BUY", quantity=1, order_type="MARKET"),
            client_order_id=cid,
        )
        flat = client.flatten_sync(instrument="MES")
        client.disconnect()
        row["place_type"] = place.get("type")
        row["place_code"] = place.get("code")
        row["flatten_type"] = flat.get("type")
        row["ok"] = place.get("type") != "error" and flat.get("type") != "error" and code == "ok"
        if not row["ok"]:
            row["place"] = place
            row["flatten"] = flat
    except Exception as exc:  # noqa: BLE001 — probe must never crash the loop
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def main() -> int:
    token = str(os.environ.get("LUMINA_FABRIC_TOKEN") or "").strip()
    if not token:
        print("LUMINA_FABRIC_TOKEN missing", flush=True)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    end = time.time() + WINDOW_HOURS * 3600
    n = 0
    fails = 0
    while time.time() < end:
        row = probe(token)
        n += 1
        if not row.get("ok"):
            fails += 1
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        summary = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "probes": n,
            "fails": fails,
            "success_rate": round((n - fails) / n, 4) if n else 0,
            "last": row,
            "window_ends_unix": end,
        }
        (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(row), flush=True)
        time.sleep(INTERVAL)
    print(json.dumps({"status": "completed", "probes": n, "fails": fails}), flush=True)
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
